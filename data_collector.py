import pyupbit  # type: ignore
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_ohlcv(ticker: str, interval: str, days: int) -> pd.DataFrame:
    dfs = []
    for i in range(days):
        df = pyupbit.get_ohlcv(ticker, interval, to=datetime.now() - timedelta(days=i))
        dfs.append(df)
    result = pd.concat(dfs).sort_index()
    # logger.info(f"get_ohlcv 갯수: {result.count}")
    result = result.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    result.index = pd.to_datetime(result.index)
    # value 컬럼 제거 (불필요)
    if "value" in result.columns:
        result = result.drop(columns=["value"])
    result = result.dropna().sort_index()
    return result
