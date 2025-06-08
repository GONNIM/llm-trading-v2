from backtesting import Backtest  # type: ignore
import logging
import traceback

logger = logging.getLogger(__name__)


def run_backtest(params: dict):
    logger.info("백테스트 시작")
    try:
        from data_collector import get_ohlcv
        from strategy_v2 import MACDStrategy

        df = get_ohlcv(params["ticker"], params["interval"], params["days"])
        logger.info(f"백테스트 데이터 크기: {df.shape}")

        # 모든 파라미터를 클래스 변수로 전달
        class CustomStrategy(MACDStrategy):
            fast_period = params["fast_period"]
            slow_period = params["slow_period"]
            signal_period = params["signal_period"]
            take_profit = params["take_profit"]
            stop_loss = params["stop_loss"]
            macd_threshold = params["macd_threshold"]
            min_holding_period = params.get("min_holding_period", 2)
            macd_crossover_threshold = params.get("macd_crossover_threshold", 0.0)

        bt = Backtest(
            df,
            CustomStrategy,
            cash=params["cash"],
            commission=params["commission"],
        )
        stats = bt.run()
        logger.info("백테스트 완료")
        return stats
    except Exception as e:
        logger.error(f"백테스트 실패: {str(e)}")
        logger.error(traceback.format_exc())
        raise
