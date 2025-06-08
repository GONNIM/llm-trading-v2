import streamlit as st
import logging
import traceback
from backtest_runner import run_backtest
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="업비트 자동매매 시스템 - MACD, EMA v2", page_icon="📈", layout="wide"
)

st.title("📊 업비트 자동매매 백테스트 - MACD, EMA v2")

# 차트 단위 옵션 (한글:코드 매핑)
interval_options = {
    "1분봉": "minute1",
    "3분봉": "minute3",
    "5분봉": "minute5",
    "10분봉": "minute10",
    "15분봉": "minute15",
    "30분봉": "minute30",
    "60분봉": "minute60",
    "일봉": "day",
    "주봉": "week",
    "월봉": "month",
}


def validate_ticker(ticker: str) -> bool:
    """입력된 ticker가 업비트에서 지원하는 형식인지 검증"""
    # 예시: BTC, ETH, KRW-BTC, BTC/USDT 등
    parts = ticker.upper().split("-")
    if len(parts) == 1 and parts[0].isalpha():
        return True  # 예: BTC, ETH
    elif len(parts) == 2 and parts[0] == "KRW" and parts[1].isalpha():
        return True  # 예: KRW-BTC
    return False


column_mapping = {
    "EntryBar": "진입 바 (인덱스)",
    "ExitBar": "종료 바 (인덱스)",
    "EntryTime": "진입 시간",
    "ExitTime": "종료 시간",
    "EntryPrice": "진입 가격",
    "ExitPrice": "종료 가격",
    "PnL": "손익",
    "ReturnPct": "수익률 (%)",
    "Size": "거래 수량",
    "Value": "거래 금액",
    "Commission": "수수료",
    "TradeDuration": "보유 기간 (바)",
}


def rename_and_filter_columns(df, mapping):
    # 실제로 존재하는 칼럼만 매핑
    available_cols = [col for col in mapping.keys() if col in df.columns]
    # 한글로 변환
    renamed_df = df[available_cols].rename(columns=mapping)
    if "수익률 (%)" in renamed_df.columns:
        renamed_df["수익률 (%)"] = (renamed_df["수익률 (%)"] * 100).round(2)
    return renamed_df


with st.sidebar:
    st.header("⚙️ 백테스트 설정")
    # 1. 데이터 기간 선택 방식 선택
    period_type = st.radio(
        "데이터 기간 선택 방식",
        ["슬라이더로 선택", "직접 입력 (일수)"],
        horizontal=True,
    )
    # 2. 미세 조정 파라미터 사용 여부
    fine_tune_type = st.radio(
        "미세 조정 파라미터 사용",
        ["기본값 사용", "직접 입력 (미세 조정)"],
        horizontal=True,
        help="최소 보유 기간, 신호 민감도 등 고급 옵션을 직접 입력하려면 선택하세요.",
    )
    sort_column = "진입 시간"
    sort_order = st.radio(
        "정렬 방향을 선택하세요",
        ("오름차순", "내림차순"),
        horizontal=True,
    )
    ascending = True if sort_order == "오름차순" else False
    with st.form("input_form"):
        # 거래 종목 직접 입력 및 검증
        ticker = st.text_input("거래 종목 (예: BTC, ETH, KRW-BTC, DOGE)", value="DOGE")
        selected_interval_name = st.selectbox(
            "차트 단위",
            list(interval_options.keys()),
            index=6,  # 기본값: 60분봉
            help="차트 데이터의 시간 단위를 선택하세요.",
        )
        selected_interval = interval_options[selected_interval_name]
        if period_type == "슬라이더로 선택":
            # 슬라이더로 일수 선택 (예: 1~365일)
            days = st.slider(
                "데이터 기간 (일)",
                min_value=1,
                max_value=365,
                value=90,
                help="분석에 사용할 데이터의 일수(범위)를 선택하세요.",
            )
        else:  # 직접 입력(일수)
            # 일수 직접 입력 (숫자 입력)
            days = st.number_input(
                "데이터 기간 (일)",
                min_value=1,
                max_value=365,
                value=90,
                help="분석에 사용할 데이터의 일수를 직접 입력하세요.",
            )
        fast_period = st.number_input("단기 EMA", 5, 50, 12)
        slow_period = st.number_input("장기 EMA", 20, 100, 26)
        signal_period = st.number_input("신호선 기간", 5, 20, 7)
        macd_threshold = st.number_input(
            "MACD 기준값 (기준선)",
            min_value=-10.0,
            max_value=10.0,
            value=0.0,
            step=0.01,
        )
        take_profit = st.number_input("Take Profit (%)", 0.1, 50.0, 5.0, 0.1) / 100
        stop_loss = st.number_input("Stop Loss (%)", 0.1, 50.0, 1.0, 0.1) / 100
        cash = st.number_input("초기 자본 (원)", 100_000, 100_000_000_000, 1_000_000)

        # 미세 조정 파라미터
        if fine_tune_type == "직접 입력 (미세 조정)":
            min_holding_period = st.number_input(
                "최소 보유 기간 (봉)",
                min_value=0,
                max_value=100,
                value=2,
                help="진입 후 최소 보유할 봉 수 (0: 제한 없음)",
            )
            macd_crossover_threshold = st.number_input(
                "MACD 신호선 차이 임계값",
                min_value=-5.0,
                max_value=5.0,
                value=0.0,
                step=0.01,
                help="MACD와 신호선의 차이가 이 값 이상일 때만 매수/매도",
            )
        else:
            min_holding_period = 1
            macd_crossover_threshold = 0.0

        submitted = st.form_submit_button("백테스트 실행")

if submitted:
    if not ticker.strip():
        st.error("거래 종목을 입력해 주세요.")
    elif not validate_ticker(ticker):
        st.error("올바른 거래 종목 형식이 아닙니다. (예: BTC, ETH, KRW-BTC)")
    else:
        try:
            if fast_period >= slow_period:
                raise ValueError("단기 EMA는 장기 EMA보다 작아야 합니다.")
            params = {
                "ticker": f"KRW-{ticker}",
                "interval": selected_interval,
                "days": days,
                "fast_period": fast_period,
                "slow_period": slow_period,
                "signal_period": signal_period,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "macd_threshold": macd_threshold,
                "min_holding_period": min_holding_period,
                "macd_crossover_threshold": macd_crossover_threshold,
                "cash": cash,
                "commission": 0.0005,
            }
            with st.spinner("백테스트 실행 중…"):
                result = run_backtest(params)

            # 결과 구조 확인 및 세션 저장
            if hasattr(result, "to_dict"):
                result = result.to_dict()

            trades_df = None
            if hasattr(result, "_trades"):
                trades_df = result._trades
            elif isinstance(result, dict) and "_trades" in result:
                trades_df = result["_trades"]

            if trades_df is not None and not trades_df.empty:
                total_trades = len(trades_df)
                profit_trades = (trades_df["PnL"] > 0).sum()
                loss_trades = (trades_df["PnL"] <= 0).sum()
                max_investment = (trades_df["Size"] * trades_df["EntryPrice"]).max()
                win_rate = (
                    (profit_trades / total_trades * 100) if total_trades > 0 else 0
                )
            else:
                total_trades = profit_trades = loss_trades = max_investment = (
                    win_rate
                ) = 0

            st.session_state["result"] = result
            st.session_state["trades_df"] = trades_df
            st.session_state["win_rate"] = win_rate
            st.session_state["max_investment"] = max_investment
            st.session_state["total_trades"] = total_trades
            st.session_state["profit_trades"] = profit_trades
            st.session_state["loss_trades"] = loss_trades
            st.session_state["ticker"] = ticker
        except Exception as e:
            st.error(f"오류 발생: {str(e)}")
            st.code(traceback.format_exc(), language="python")

# ====== 결과 표시 (세션 상태에 있을 때 항상 표시) ======
if (
    "result" in st.session_state
    and "trades_df" in st.session_state
    and "ticker" in st.session_state
):
    result = st.session_state["result"]
    trades_df = st.session_state["trades_df"]
    win_rate = st.session_state["win_rate"]
    max_investment = st.session_state["max_investment"]
    total_trades = st.session_state["total_trades"]
    profit_trades = st.session_state["profit_trades"]
    loss_trades = st.session_state["loss_trades"]
    ticker = st.session_state["ticker"]

    end_value = (
        result.get("End Value")
        or result.get("Equity Final [$]")
        or result.get("Equity Final")
        or "확인 불가"
    )
    return_pct = result.get("Return [%]") or result.get("Return") or "확인 불가"
    max_dd = (
        result.get("Max. Drawdown [%]") or result.get("Max. Drawdown") or "확인 불가"
    )

    st.subheader(f"📊 백테스트 결과 < {ticker} >")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "최종 자산",
            f"{end_value:,.0f}원" if isinstance(end_value, (int, float)) else end_value,
        )
    with col2:
        st.metric(
            "수익률",
            (
                f"{return_pct:.2f}%"
                if isinstance(return_pct, (int, float))
                else return_pct
            ),
        )
    with col3:
        st.metric(
            "최대 손실",
            f"{max_dd:.2f}%" if isinstance(max_dd, (int, float)) else max_dd,
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("총 거래 횟수", f"{total_trades:,}")
    with col5:
        st.metric("수익 거래", f"{profit_trades:,}")
    with col6:
        st.metric("손실 거래", f"{loss_trades:,}")

    # 거래 내역 표시
    with st.expander("전체 거래 내역"):
        if trades_df is not None and not trades_df.empty:
            renamed_df = rename_and_filter_columns(trades_df, column_mapping)
            if sort_column in renamed_df.columns:
                renamed_df = renamed_df.sort_values(by=sort_column, ascending=ascending)
            st.dataframe(renamed_df)
        else:
            st.write("거래 내역 없음")

    with st.expander("수익 거래 내역"):
        if trades_df is not None and not trades_df.empty:
            profit_df = trades_df[trades_df["PnL"] > 0]
            if not profit_df.empty:
                renamed_profit_df = rename_and_filter_columns(profit_df, column_mapping)
                if sort_column in renamed_profit_df.columns:
                    renamed_profit_df = renamed_profit_df.sort_values(
                        by=sort_column, ascending=ascending
                    )
                st.dataframe(renamed_profit_df)
            else:
                st.write("수익 거래 내역 없음")
        else:
            st.write("수익 거래 내역 없음")

    with st.expander("손실 거래 내역"):
        if trades_df is not None and not trades_df.empty:
            loss_df = trades_df[trades_df["PnL"] <= 0]
            if not loss_df.empty:
                renamed_loss_df = rename_and_filter_columns(loss_df, column_mapping)
                if sort_column in renamed_loss_df.columns:
                    renamed_loss_df = renamed_loss_df.sort_values(
                        by=sort_column, ascending=ascending
                    )
                st.dataframe(renamed_loss_df)
            else:
                st.write("손실 거래 내역 없음")
        else:
            st.write("손실 거래 내역 없음")

    st.write("---")

    col7, col8, col9 = st.columns(3)
    with col7:
        st.metric("승률", f"{win_rate:.2f}%")
    with col8:
        st.metric("최대 투자금", f"{max_investment:,.0f}원")

    start = result.get("Start")
    end = result.get("End")
    duration = result.get("Duration")

    # 포맷팅 처리
    if hasattr(start, "strftime"):
        start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    else:
        start_str = str(start)
    if hasattr(end, "strftime"):
        end_str = end.strftime("%Y-%m-%d %H:%M:%S")
    else:
        end_str = str(end)
    # Timedelta 포맷팅
    if hasattr(duration, "components"):
        # pandas.Timedelta
        comps = duration.components
        duration_str = f"{comps.days}일 {comps.hours}시간 {comps.minutes}분"
    else:
        duration_str = str(duration)

    col10, col11, col12 = st.columns(3)
    with col10:
        st.metric("백테스트 시작", f"{start_str}")
    with col11:
        st.metric("백테스트 종료", f"{end_str}")
    with col12:
        st.metric("백테스트 기간", f"{duration_str}")

    with st.expander("상세 통계 보기"):
        st.write(result)
