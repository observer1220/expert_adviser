import pandas as pd
import numpy as np
from datetime import datetime


class QuantTradingBot:
    def __init__(self, symbol, initial_balance=10000, lot_size=0.01, stop_loss=0.0005, take_profit=0.001):
        self.symbol = symbol
        self.balance = initial_balance
        self.lot_size = lot_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.position = 0  # 0: 無持倉, 1: 多頭, -1: 空頭
        self.entry_price = 0
        self.trades = []

    def calculate_indicators(self, data):
        """計算技術指標：SMA 和 RSI"""
        data['SMA20'] = data['Close'].rolling(window=20).mean()
        data['SMA50'] = data['Close'].rolling(window=50).mean()

        # 優化 RSI 計算
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.ewm(span=14, min_periods=14).mean()
        avg_loss = loss.ewm(span=14, min_periods=14).mean()

        rs = avg_gain / avg_loss
        data['RSI'] = 100 - (100 / (1 + rs))
        return data

    def should_enter_trade(self, current, previous):
        """判斷是否進場"""
        if pd.isna(current.SMA20) or pd.isna(current.SMA50) or pd.isna(current.RSI):
            return 0

        if (current.SMA20 > current.SMA50 and current.Close > current.SMA20 and
                previous.Close <= previous.SMA20 and current.RSI < 70):
            return 1  # 買入
        elif (current.SMA20 < current.SMA50 and current.Close < current.SMA20 and
              previous.Close >= previous.SMA20 and current.RSI > 30):
            return -1  # 賣出
        return 0

    def should_exit_trade(self, current):
        """判斷是否平倉"""
        if self.position == 1 and (current.RSI > 70 or current.Close < current.SMA20):
            return 0  # 平倉
        elif self.position == -1 and (current.RSI < 30 or current.Close > current.SMA20):
            return 0  # 平倉
        return self.position

    def _record_trade(self, trade_type, exit_price, profit_loss):
        """統一交易記錄邏輯"""
        self.balance += profit_loss
        print(f"{datetime.now()} - {self.symbol} {trade_type}，價格: {exit_price}，盈虧: ${profit_loss:.2f}，餘額: ${self.balance:.2f}")
        self.trades.append({
            'symbol': self.symbol, 'type': trade_type, 'entry_price': self.entry_price,
            'exit_price': exit_price, 'profit_loss': profit_loss, 'lot_size': self.lot_size,
            'timestamp': datetime.now()
        })
        self.position = 0
        self.entry_price = 0

    def execute_trade(self, price, signal):
        """執行交易邏輯"""
        if self.position == 0 and signal != 0:  # 進場
            self.position = signal
            self.entry_price = price
            trade_type = "買入" if signal == 1 else "賣出"
            print(
                f"{datetime.now()} - {self.symbol} {trade_type}，價格: {price}，手數: {self.lot_size}")

        elif self.position != 0 and signal == 0:  # 平倉
            profit_loss = (price - self.entry_price) * self.lot_size * 100000 if self.position == 1 else \
                          (self.entry_price - price) * self.lot_size * 100000
            trade_type = "平多" if self.position == 1 else "平空"
            self._record_trade(trade_type, price, profit_loss)

        elif self.position != 0:  # 停損或停利
            price_diff = price - self.entry_price if self.position == 1 else self.entry_price - price
            if price_diff <= -self.stop_loss or price_diff >= self.take_profit:
                exit_price = self.entry_price + \
                    (self.take_profit if price_diff >=
                     self.take_profit else -self.stop_loss)
                profit_loss = (exit_price - self.entry_price) * self.lot_size * 100000 if self.position == 1 else \
                              (self.entry_price - exit_price) * \
                    self.lot_size * 100000
                trade_type = "獲利平多" if price_diff >= self.take_profit else "止損平多"
                trade_type = "獲利平空" if self.position == - \
                    1 and price_diff >= self.take_profit else trade_type
                trade_type = "止損平空" if self.position == - \
                    1 and price_diff <= -self.stop_loss else trade_type
                self._record_trade(trade_type, exit_price, profit_loss)

    def run(self, price_data):
        """運行交易機器人"""
        data = self.calculate_indicators(price_data)
        for i, current in enumerate(data.itertuples(index=False)):
            if i == 0:
                continue
            previous = data.iloc[i - 1]

            # 先檢查是否需要平倉
            if self.position != 0:
                self.execute_trade(
                    current.Close, self.should_exit_trade(current))
            else:
                self.execute_trade(
                    current.Close, self.should_enter_trade(current, previous))

    def get_trades_history(self):
        """返回交易歷史"""
        return pd.DataFrame(self.trades)


# 示例使用
if __name__ == "__main__":
    csv_file_path = 'EURUSD_historical_data.csv'  # 替換為你的 CSV 文件路徑
    data = pd.read_csv(csv_file_path)
    price_data = data[['Close']]

    bot = QuantTradingBot(symbol='EURUSD', initial_balance=10000,
                          lot_size=0.01, stop_loss=0.0005, take_profit=0.001)
    bot.run(price_data)
    trades_history = bot.get_trades_history()

    print("\n交易歷史：")
    print(trades_history)
    print("\n結餘：", bot.balance)
