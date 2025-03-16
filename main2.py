import pandas as pd
import numpy as np
from datetime import datetime


# 沒有止損機制的交易機器人
class QuantTradingBot:
    def __init__(self, symbol, initial_balance=10000, risk_per_trade=0.01):
        self.symbol = symbol
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade  # 每筆交易風險 %
        self.position = 0
        self.entry_price = 0
        self.stop_loss = 0
        self.take_profit = 0
        self.trades = []
        self.lot_size = 0.01

    def calculate_indicators(self, data):
        """計算技術指標"""
        data["SMA20"] = data["Close"].rolling(window=20).mean()
        data["SMA50"] = data["Close"].rolling(window=50).mean()

        delta = data["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=10).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=10).mean()
        rs = gain / loss
        data["RSI"] = 100 - (100 / (1 + rs))

        data["EMA12"] = data["Close"].ewm(span=12, adjust=False).mean()
        data["EMA26"] = data["Close"].ewm(span=26, adjust=False).mean()
        data["MACD"] = data["EMA12"] - data["EMA26"]
        data["Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()

        data["ATR"] = data["High"].sub(data["Low"]).rolling(window=14).mean()
        return data

    def should_enter_trade(self, current_row, previous_row):
        """判斷是否進場，並根據市場波動決定手數"""
        if (
            pd.isna(current_row["SMA20"])
            or pd.isna(current_row["SMA50"])
            or pd.isna(current_row["RSI"])
        ):
            return 0, self.lot_size

        lot_size = self.lot_size  # 預設手數

        if (
            current_row["SMA20"] > current_row["SMA50"]
            and current_row["Close"] > current_row["SMA20"]
            and previous_row["Close"] <= previous_row["SMA20"]
            and current_row["RSI"] < 70
        ):
            return 1, lot_size  # 買入信號
        elif (
            current_row["SMA20"] < current_row["SMA50"]
            and current_row["Close"] < current_row["SMA20"]
            and previous_row["Close"] >= previous_row["SMA20"]
            and current_row["RSI"] > 30
        ):
            return -1, lot_size  # 賣出信號

        return 0, lot_size  # 無信號

    def execute_trade(self, price, signal, lot_size):
        if self.position == 0 and signal != 0:
            self.position = signal
            self.entry_price = price
            self.lot_size = lot_size
            print(
                f"{datetime.now()} - {self.symbol} 進場: {'買' if signal == 1 else '賣'}，價格: {price}，手數: {lot_size:.4f}"
            )
        elif self.position != 0 and (
            price >= self.take_profit or price <= self.stop_loss
        ):
            profit_loss = (
                (price - self.entry_price) * lot_size * 100000
                if self.position == 1
                else (self.entry_price - price) * lot_size * 100000
            )
            self.balance += profit_loss
            print(
                f"{datetime.now()} - {self.symbol} {'止盈' if price >= self.take_profit else '止損'} 平倉，價格: {price}，盈虧: ${profit_loss:.2f}，餘額: ${self.balance:.2f}"
            )
            self.trades.append(
                {
                    "symbol": self.symbol,
                    "entry_price": self.entry_price,
                    "exit_price": price,
                    "profit_loss": profit_loss,
                    "lot_size": lot_size,
                    "timestamp": datetime.now(),
                }
            )
            self.position = 0
            self.entry_price = 0

    def run(self, price_data):
        data_with_indicators = self.calculate_indicators(price_data.copy())
        for i in range(1, len(data_with_indicators)):
            current_row = data_with_indicators.iloc[i]
            previous_row = data_with_indicators.iloc[i - 1]
            entry_signal, lot_size = self.should_enter_trade(current_row, previous_row)

            if self.position == 0:
                self.execute_trade(current_row["Close"], entry_signal, lot_size)
            elif self.position != 0:
                self.execute_trade(current_row["Close"], self.position, self.lot_size)

    def get_trades_history(self):
        return pd.DataFrame(self.trades)


if __name__ == "__main__":
    csv_file_path = "EURUSD_historical_data.csv"  # 替換為你的數據文件
    data = pd.read_csv(csv_file_path)
    price_data = data[["Close", "High", "Low"]]

    bot = QuantTradingBot(symbol="EURUSD", initial_balance=10000, risk_per_trade=0.01)
    bot.run(price_data)
    trades_history = bot.get_trades_history()
    print("\n交易歷史：")
    print(trades_history)
    print("\n結餘：", bot.balance)
