import pandas as pd
from sklearn.cluster import KMeans
from datetime import datetime


class AdaptiveTradingBot:

    def __init__(
        self,
        symbol,
        initial_balance=10000,
        lot_size=0.01,
        risk_reward_ratio=2,
        contract_size=100000,
    ):
        self.symbol = symbol  # 交易兌
        self.balance = initial_balance  # 初始餘額
        self.lot_size = lot_size  # 每次交易手數
        self.risk_reward_ratio = risk_reward_ratio  # 風險報酬比
        self.position = 0  # 0: 無持倉, 1: 多單, -1: 空單
        self.entry_price = 0  # 進場價格
        self.trades = []  # 交易記錄
        self.contract_size = contract_size  # 外匯標準合約大小為 100,000

    def calculate_indicators(self, data):
        """計算技術指標：SMA、EMA、ATR、RSI"""
        data["SMA"] = data["Close"].rolling(window=20).mean()
        data["EMA"] = data["Close"].ewm(span=15, adjust=False).mean()

        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data["RSI"] = 100 - (100 / (1 + rs))

        # ATR 計算
        data["High-Low"] = data["High"] - data["Low"]
        data["High-Close"] = abs(data["High"] - data["Close"].shift(1))
        data["Low-Close"] = abs(data["Low"] - data["Close"].shift(1))
        data["TR"] = data[["High-Low", "High-Close", "Low-Close"]].max(axis=1)
        data["ATR"] = data["TR"].rolling(window=14).mean()

        return data

    def dynamic_rsi_threshold(self, data):
        """使用 KMeans 群集分析找出適合的 RSI 超買 / 超賣區間"""
        rsi_values = data[["RSI"]].dropna()
        kmeans = KMeans(n_clusters=3, random_state=42)
        kmeans.fit(rsi_values)

        clusters = sorted(kmeans.cluster_centers_.flatten())
        oversold, neutral, overbought = clusters

        return oversold, overbought

    def should_enter_trade(self, current_row, previous_row, oversold, overbought):
        """根據動態 RSI & ATR 訊號決定進場"""
        if (
            pd.isna(current_row["SMA"])
            or pd.isna(current_row["RSI"])
            or pd.isna(current_row["ATR"])
        ):
            return 0, 0, 0

        atr = current_row["ATR"]
        stop_loss = atr * 1.5
        take_profit = stop_loss * self.risk_reward_ratio

        # 多頭訊號
        if (
            current_row["SMA"] > current_row["EMA"]
            and previous_row["RSI"] < oversold
            and current_row["RSI"] > previous_row["RSI"]
        ):
            return 1, stop_loss, take_profit  # 多單

        # 空頭訊號
        elif (
            current_row["SMA"] < current_row["EMA"]
            and previous_row["RSI"] > overbought
            and current_row["RSI"] < previous_row["RSI"]
        ):
            return -1, stop_loss, take_profit  # 空單

        return 0, 0, 0

    def should_exit_trade(self, current_row):
        """動態平倉邏輯"""
        if self.position == 1 and current_row["RSI"] > 70:
            return 0
        elif self.position == -1 and current_row["RSI"] < 30:
            return 0
        return self.position

    def execute_trade(self, price, signal, stop_loss, take_profit):
        """執行交易"""
        if self.position == 0 and signal != 0:
            self.position = signal
            self.entry_price = price
            print(
                f"{datetime.now()} - {self.symbol} 進場: {'買' if signal == 1 else '賣'}，價格: {price}，手數: {self.lot_size:.4f}"
            )
        elif self.position != 0 and signal == 0:
            profit_loss = (
                (price - self.entry_price) * self.lot_size * self.contract_size
                if self.position == 1
                else (self.entry_price - price) * self.lot_size * self.contract_size
            )
            self.balance += profit_loss
            print(
                f"{datetime.now()} - {self.symbol} {'止盈' if profit_loss > 0 else '止損'} 平倉，價格: {price}，盈虧: ${profit_loss:.2f}，餘額: ${self.balance:.2f}"
            )

            self.position = 0
            self.entry_price = 0
        elif self.position != 0:
            price_diff = (
                price - self.entry_price
                if self.position == 1
                else self.entry_price - price
            )
            if price_diff <= -stop_loss:
                print(
                    f"止損平倉 @ {self.entry_price - stop_loss if self.position == 1 else self.entry_price + stop_loss}"
                )
                self.trades.append(
                    {
                        "symbol": self.symbol,
                        "entry_price": self.entry_price,
                        "exit_price": price,
                        "profit_loss": -stop_loss * self.lot_size * self.contract_size,
                        "lot_size": self.lot_size,
                        "timestamp": datetime.now(),
                    }
                )
                self.position = 0
            elif price_diff >= take_profit:
                print(
                    f"獲利平倉 @ {self.entry_price + take_profit if self.position == 1 else self.entry_price - take_profit}"
                )
                self.trades.append(
                    {
                        "symbol": self.symbol,
                        "entry_price": self.entry_price,
                        "exit_price": price,
                        "profit_loss": take_profit * self.lot_size * self.contract_size,
                        "lot_size": self.lot_size,
                        "timestamp": datetime.now(),
                    }
                )
                self.position = 0

    def run(self, price_data):
        """運行交易機器人"""
        data_with_indicators = self.calculate_indicators(price_data.copy())
        oversold, overbought = self.dynamic_rsi_threshold(data_with_indicators)

        for i in range(1, len(data_with_indicators)):
            current_row = data_with_indicators.iloc[i]
            previous_row = data_with_indicators.iloc[i - 1]

            entry_signal, stop_loss, take_profit = self.should_enter_trade(
                current_row, previous_row, oversold, overbought
            )
            exit_signal = self.should_exit_trade(current_row)

            if self.position != 0:
                self.execute_trade(
                    current_row["Close"], exit_signal, stop_loss, take_profit
                )
            else:
                self.execute_trade(
                    current_row["Close"], entry_signal, stop_loss, take_profit
                )

    def get_trades_history(self):
        return pd.DataFrame(self.trades)


# 示例使用
if __name__ == "__main__":
    # 讀取 EURUSD 歷史數據 CSV 文件
    csv_file_path = "EURUSD_historical_data.csv"  # 替換為你的 CSV 文件路徑
    data = pd.read_csv(csv_file_path)
    price_data = data[["Close", "High", "Low"]]

    # 初始化交易機器人: 初始餘額 $10,000, 每次交易手數 0.01, 風險報酬比 2
    bot = AdaptiveTradingBot(
        symbol="EURUSD", initial_balance=10000, lot_size=0.01, risk_reward_ratio=2
    )
    bot.run(price_data)
    trades_history = bot.get_trades_history()
    print("\n交易歷史：")
    print(trades_history)
    print("\n結餘：", bot.balance)
