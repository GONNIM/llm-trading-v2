from backtesting import Strategy # type: ignore
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MACDStrategy(Strategy):
    fast_period = 12
    slow_period = 26
    signal_period = 9
    take_profit = 0.05
    stop_loss = 0.03
    macd_threshold = 0.0

    def init(self):
        logger.info("전략 초기화 시작")
        close = self.data.Close
        self.macd_line = self.I(
            self._calculate_macd, close, self.fast_period, self.slow_period
        )
        self.signal_line = self.I(
            self._calculate_signal, self.macd_line, self.signal_period
        )
        self.entry_price = None

    def _calculate_macd(self, series, fast, slow):
        series = pd.Series(series)  # numpy array → pandas Series 변환
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        return macd.values  # pandas Series → numpy array로 반환

    def _calculate_signal(self, macd, period):
        macd = pd.Series(macd)  # numpy array → pandas Series 변환
        signal = macd.ewm(span=period, adjust=False).mean()
        return signal.values  # pandas Series → numpy array로 반환

    def next(self):
        current_price = self.data.Close[-1]
        if self.position:
            tp_price = self.entry_price * (1 + self.take_profit)
            sl_price = self.entry_price * (1 - self.stop_loss)
            if current_price >= tp_price:
                self.position.close()
                self.entry_price = None
                return
            if current_price <= sl_price:
                self.position.close()
                self.entry_price = None
                return

        if not self.position:
            if (
                self.macd_line[-1] > self.signal_line[-1]
                and self.macd_line[-2] <= self.signal_line[-2]
                and self.macd_line[-1] >= self.macd_threshold
            ):
                self.buy()
                self.entry_price = current_price
        else:
            if (
                self.macd_line[-1] < self.signal_line[-1]
                and self.macd_line[-2] >= self.signal_line[-2]
                and self.macd_line[-1] >= self.macd_threshold
            ):
                self.position.close()
                self.entry_price = None
