import pandas as pd
import numpy as np
from datetime import datetime
# import matplotlib.pyplot as plt


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

        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        return data

    def should_enter_trade(self, current_row, previous_row):
        """判斷是否進場：放寬 SMA 和 RSI 條件"""

        if pd.isna(current_row['SMA20']) or pd.isna(current_row['SMA50']) or pd.isna(current_row['RSI']):
            return 0

        # 買入信號：SMA20 高於 SMA50 且價格突破 SMA20，RSI 不超 70
        if (current_row['SMA20'] > current_row['SMA50'] and
            current_row['Close'] > current_row['SMA20'] and
            previous_row['Close'] <= previous_row['SMA20'] and
                current_row['RSI'] < 70):
            return 1

        # 賣出信號：SMA20 低於 SMA50 且價格跌破 SMA20，RSI 不低於 30
        elif (current_row['SMA20'] < current_row['SMA50'] and
              current_row['Close'] < current_row['SMA20'] and
              previous_row['Close'] >= previous_row['SMA20'] and
              current_row['RSI'] > 30):
            return -1

        return 0

    def should_exit_trade(self, current_row):
        """判斷是否平倉：基於 RSI 反轉或止損/止盈"""
        if self.position == 0:
            return 0

        if self.position == 1:  # 多頭持倉
            # RSI 超買（> 70）或價格跌破 SMA20 平倉
            if current_row['RSI'] > 70 or current_row['Close'] < current_row['SMA20']:
                return 0
        elif self.position == -1:  # 空頭持倉
            # RSI 超賣（< 30）或價格突破 SMA20 平倉
            if current_row['RSI'] < 30 or current_row['Close'] > current_row['SMA20']:
                return 0
        return self.position

    def execute_trade(self, price, signal):
        """執行交易邏輯"""
        if self.position == 0 and signal != 0:  # 開倉
            self.position = signal
            self.entry_price = price
            trade_type = "買入" if signal == 1 else "賣出"
            print(
                f"{datetime.now()} - {self.symbol} {trade_type}，價格: {price}，手數: {self.lot_size}")

        elif self.position != 0 and signal == 0:  # 平倉
            profit_loss = (price - self.entry_price) * self.lot_size * 100000 if self.position == 1 else \
                          (self.entry_price - price) * self.lot_size * 100000
            self.balance += profit_loss
            trade_type = "平多" if self.position == 1 else "平空"
            print(
                f"{datetime.now()} - {self.symbol} {trade_type}，價格: {price}，盈虧: ${profit_loss:.2f}，餘額: ${self.balance:.2f}")
            self.trades.append({
                'symbol': self.symbol, 'type': trade_type, 'entry_price': self.entry_price,
                'exit_price': price, 'profit_loss': profit_loss, 'lot_size': self.lot_size,
                'timestamp': datetime.now()
            })
            self.position = 0
            self.entry_price = 0

        elif self.position != 0:  # 檢查止損或獲利
            price_diff = price - self.entry_price if self.position == 1 else self.entry_price - price
            if price_diff <= -self.stop_loss:  # 止損
                exit_price = self.entry_price - \
                    self.stop_loss if self.position == 1 else self.entry_price + self.stop_loss
                profit_loss = (exit_price - self.entry_price) * self.lot_size * 100000 if self.position == 1 else \
                              (self.entry_price - exit_price) * \
                    self.lot_size * 100000
                self.balance += profit_loss
                trade_type = "止損平多" if self.position == 1 else "止損平空"
                print(
                    f"{datetime.now()} - {self.symbol} {trade_type}，價格: {exit_price}，盈虧: ${profit_loss:.2f}，餘額: ${self.balance:.2f}")
                self.trades.append({
                    'symbol': self.symbol, 'type': trade_type, 'entry_price': self.entry_price,
                    'exit_price': exit_price, 'profit_loss': profit_loss, 'lot_size': self.lot_size,
                    'timestamp': datetime.now()
                })
                self.position = 0
                self.entry_price = 0
            elif price_diff >= self.take_profit:  # 獲利
                exit_price = self.entry_price + \
                    self.take_profit if self.position == 1 else self.entry_price - self.take_profit
                profit_loss = (exit_price - self.entry_price) * self.lot_size * 100000 if self.position == 1 else \
                              (self.entry_price - exit_price) * \
                    self.lot_size * 100000
                self.balance += profit_loss
                trade_type = "獲利平多" if self.position == 1 else "獲利平空"
                print(
                    f"{datetime.now()} - {self.symbol} {trade_type}，價格: {exit_price}，盈虧: ${profit_loss:.2f}，餘額: ${self.balance:.2f}")
                self.trades.append({
                    'symbol': self.symbol, 'type': trade_type, 'entry_price': self.entry_price,
                    'exit_price': exit_price, 'profit_loss': profit_loss, 'lot_size': self.lot_size,
                    'timestamp': datetime.now()
                })
                self.position = 0
                self.entry_price = 0

    def run(self, price_data):
        """運行交易機器人"""
        data_with_indicators = self.calculate_indicators(price_data.copy())
        for i in range(len(data_with_indicators)):
            if i == 0:
                continue
            current_row = data_with_indicators.iloc[i]
            previous_row = data_with_indicators.iloc[i - 1]

            # 判斷進場
            entry_signal = self.should_enter_trade(current_row, previous_row)
            # 判斷平倉
            exit_signal = self.should_exit_trade(current_row)

            # 若有持倉，優先檢查退出條件
            if self.position != 0:
                self.execute_trade(current_row['Close'], exit_signal)
            else:
                self.execute_trade(current_row['Close'], entry_signal)

    def get_trades_history(self):
        """返回交易歷史"""
        return pd.DataFrame(self.trades)


# 示例使用
if __name__ == "__main__":
    # 讀取 EURUSD 歷史數據 CSV 文件
    csv_file_path = 'EURUSD_historical_data.csv'  # 替換為你的 CSV 文件路徑
    data = pd.read_csv(csv_file_path)
    price_data = data[['Close']]

    # 初始化交易機器人: 初始餘額 $10,000, 每次交易手數 0.01, 止損 50 pips, 止盈 100 pips
    bot = QuantTradingBot(symbol='EURUSD', initial_balance=10000,
                          lot_size=0.01, stop_loss=0.0005, take_profit=0.001)
    bot.run(price_data)
    trades_history = bot.get_trades_history()
    print("\n交易歷史：")
    print(trades_history)
    print("\n結餘：", bot.balance)
