from backtesting import Strategy
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
    min_holding_period = 2
    macd_crossover_threshold = 0.0

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
        self.entry_bar = None
        self.last_signal_bar = None

    def _calculate_macd(self, series, fast, slow):
        series = pd.Series(series)
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        return macd.values

    def _calculate_signal(self, macd, period):
        macd = pd.Series(macd)
        signal = macd.ewm(span=period, adjust=False).mean()
        return signal.values

    def next(self):
        current_bar = len(self.data) - 1
        current_price = self.data.Close[-1]

        # 같은 봉에서 신호 중복 방지
        if self.last_signal_bar == current_bar:
            return

        if self.position:
            bars_since_entry = current_bar - self.entry_bar
            # 익절/손절
            tp_price = self.entry_price * (1 + self.take_profit)
            sl_price = self.entry_price * (1 - self.stop_loss)
            if current_price >= tp_price or current_price <= sl_price:
                self.position.close()
                self.entry_price = None
                self.entry_bar = None
                self.last_signal_bar = current_bar
                return

            # 최소 보유 기간
            if bars_since_entry < self.min_holding_period:
                return

            # 매도 신호
            macd_diff = self.macd_line[-1] - self.signal_line[-1]
            if (
                macd_diff < -self.macd_crossover_threshold
                and self.macd_line[-2] >= self.signal_line[-2]
                and self.macd_line[-1] >= self.macd_threshold
            ):
                self.position.close()
                self.entry_price = None
                self.entry_bar = None
                self.last_signal_bar = current_bar

        if not self.position:
            # 매수 신호
            macd_diff = self.macd_line[-1] - self.signal_line[-1]
            if (
                macd_diff > self.macd_crossover_threshold
                and self.macd_line[-2] <= self.signal_line[-2]
                and self.macd_line[-1] >= self.macd_threshold
            ):
                self.buy()
                self.entry_price = current_price
                self.entry_bar = current_bar
                self.last_signal_bar = current_bar
