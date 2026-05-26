"""
股票資料擷取模組
- yfinance: 技術面價量資料
- FinMind: 法人買賣超、基本面財報
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
import logging as _logging
warnings.filterwarnings("ignore")
# 靜音 yfinance 的 "possibly delisted" 和 timezone 相關 error 訊息
_logging.getLogger("yfinance").setLevel(_logging.CRITICAL)
_logging.getLogger("peewee").setLevel(_logging.CRITICAL)

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 標準 OHLCV 欄位名稱
_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def _normalize_df(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    將 yfinance 回傳的 DataFrame 正規化為標準 OHLCV 格式（欄位小寫）

    處理兩種格式：
    1. 新版 MultiIndex: columns = (ticker, price_type) 或 (price_type, ticker)
    2. 舊版 flat: columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    """
    if df is None or df.empty:
        return None
    try:
        # 若是 MultiIndex，先展平
        if hasattr(df.columns, 'levels'):
            # 嘗試判斷哪個 level 是 price type
            lv0 = df.columns.get_level_values(0).tolist()
            lv1 = df.columns.get_level_values(1).tolist()
            price_keys = {"close", "open", "high", "low", "volume",
                          "Close", "Open", "High", "Low", "Volume",
                          "Adj Close", "adj close"}
            if any(str(v).title() in price_keys or str(v).lower() in price_keys for v in lv0):
                # Level 0 是 price type (舊格式)
                df.columns = [str(c[0]).lower().replace(" ", "_") for c in df.columns]
            else:
                # Level 0 是 ticker，Level 1 是 price type (新格式)
                df.columns = [str(c[1]).lower().replace(" ", "_") for c in df.columns]
        else:
            df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

        # 統一欄位名稱：adj_close → close（若 close 不存在）
        if "close" not in df.columns and "adj_close" in df.columns:
            df = df.rename(columns={"adj_close": "close"})

        # 確認必要欄位存在
        if "close" not in df.columns or "volume" not in df.columns:
            return None

        df.index = pd.to_datetime(df.index)
        df = df.dropna(subset=["close"])
        return df if len(df) >= 5 else None

    except Exception as e:
        logger.debug(f"DataFrame 正規化失敗: {e}")
        return None


def _extract_ticker_df(data: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
    """
    從 yfinance 批次下載結果中取出指定 ticker 的 DataFrame 並正規化

    支援新舊版 yfinance 格式
    """
    if data is None or data.empty:
        return None
    try:
        # 嘗試 MultiIndex 方式：data[ticker]
        if hasattr(data.columns, 'levels'):
            lv0_vals = data.columns.get_level_values(0).tolist()
            lv1_vals = data.columns.get_level_values(1).tolist()

            if ticker in lv0_vals:
                # 新格式: Level 0 = ticker
                df = data[ticker].copy()
            elif ticker in lv1_vals:
                # 舊格式: Level 1 = ticker
                df = data.xs(ticker, level=1, axis=1).copy()
            else:
                return None
        else:
            # flat 格式（單一股票舊版）
            df = data.copy()

        return _normalize_df(df)
    except Exception as e:
        logger.debug(f"提取 {ticker} 失敗: {e}")
        return None


def fetch_price_data(
    ticker: str,
    days: int = 120,
    retry: int = 3
) -> Optional[pd.DataFrame]:
    """
    使用 yfinance 擷取股票歷史價格資料

    Args:
        ticker: Yahoo Finance 代碼 (e.g., "2330.TW")
        days: 歷史天數
        retry: 重試次數

    Returns:
        DataFrame with OHLCV data or None
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance 未安裝，請執行: pip install yfinance")
        return None

    # yfinance end 日期為 exclusive，需加 1 天才能包含今日收盤資料
    end = datetime.now() + timedelta(days=1)
    start = end - timedelta(days=days + 31)  # 多抓一些以確保有足夠交易日

    for attempt in range(retry):
        try:
            df = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
                timeout=10,
            )
            if df is not None and len(df) >= 20:
                df = _normalize_df(df)
                if df is not None:
                    return df.tail(days)
        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2 ** attempt)
            else:
                logger.warning(f"yfinance 擷取 {ticker} 失敗: {e}")

    return None


def fetch_batch_price_data(
    tickers: List[str],
    days: int = 120,
    batch_size: int = 20,
    delay: float = 1.0
) -> Dict[str, pd.DataFrame]:
    """
    批次擷取多檔股票價格資料

    Args:
        tickers: 股票代碼清單
        days: 歷史天數
        batch_size: 每批次數量
        delay: 批次間延遲秒數

    Returns:
        Dict {ticker: DataFrame}
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance 未安裝")
        return {}

    results = {}
    # yfinance end 日期為 exclusive，需加 1 天才能包含今日收盤資料
    end = datetime.now() + timedelta(days=1)
    start = end - timedelta(days=days + 31)

    # 分批下載
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        logger.info(f"下載批次 {i//batch_size + 1}: {batch[:3]}...")

        try:
            data = yf.download(
                batch,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                timeout=30,
            )

            if data.empty:
                continue

            # 新版 yfinance 不論單一或多檔，統一使用 MultiIndex 格式
            # Level 0 = ticker, Level 1 = price type (Open/High/Low/Close/Volume)
            # 使用統一的正規化函式處理
            for ticker in batch:
                try:
                    df = _extract_ticker_df(data, ticker)
                    if df is not None and len(df) >= 20:
                        results[ticker] = df.tail(days)
                except Exception as e:
                    logger.debug(f"處理 {ticker} 失敗: {e}")

        except Exception as e:
            logger.warning(f"批次下載失敗: {e}")
            # 單獨下載
            for ticker in batch:
                df = fetch_price_data(ticker, days)
                if df is not None:
                    results[ticker] = df

        if i + batch_size < len(tickers):
            time.sleep(delay)

    logger.info(f"成功下載 {len(results)}/{len(tickers)} 檔股票資料")
    return results


def fetch_finmind_institutional(
    stock_id: str,
    date: str,
    token: str = ""
) -> Optional[pd.DataFrame]:
    """
    使用 FinMind API 擷取三大法人買賣超資料

    Args:
        stock_id: 股票代號 (e.g., "2330")
        date: 日期 (e.g., "2024-01-01")
        token: FinMind API token

    Returns:
        DataFrame with institutional data
    """
    try:
        import requests

        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": stock_id,
            "start_date": date,
            "token": token,
        }

        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 200 and data.get("data"):
                return pd.DataFrame(data["data"])

    except Exception as e:
        logger.warning(f"FinMind 法人資料擷取失敗 {stock_id}: {e}")

    return None


def fetch_finmind_financials(
    stock_id: str,
    token: str = ""
) -> Optional[pd.DataFrame]:
    """
    使用 FinMind API 擷取財報資料

    Args:
        stock_id: 股票代號
        token: FinMind API token

    Returns:
        DataFrame with financial data
    """
    try:
        import requests

        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockFinancialStatements",
            "data_id": stock_id,
            "start_date": (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d"),
            "token": token,
        }

        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 200 and data.get("data"):
                return pd.DataFrame(data["data"])

    except Exception as e:
        logger.warning(f"FinMind 財報資料擷取失敗 {stock_id}: {e}")

    return None


def fetch_finmind_revenue(
    stock_id: str,
    token: str = ""
) -> Optional[pd.DataFrame]:
    """
    使用 FinMind API 擷取月營收資料
    """
    try:
        import requests

        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": stock_id,
            "start_date": (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d"),
            "token": token,
        }

        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 200 and data.get("data"):
                return pd.DataFrame(data["data"])

    except Exception as e:
        logger.warning(f"FinMind 月營收擷取失敗 {stock_id}: {e}")

    return None


def fetch_finmind_shareholding(
    stock_id: str,
    token: str = ""
) -> Optional[pd.DataFrame]:
    """
    擷取集保大戶持股分散表
    dataset: TaiwanStockHoldingSharesPer
    回傳最近兩期資料，計算大戶持股比例變化

    Args:
        stock_id: 股票代號 (e.g., "2330")
        token: FinMind API token

    Returns:
        DataFrame with shareholding distribution data or None
    """
    try:
        import requests

        # 取近 90 天以確保能拿到兩期（每週更新一次）
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockHoldingSharesPer",
            "data_id": stock_id,
            "start_date": start_date,
            "token": token,
        }

        resp = requests.get(url, params=params, timeout=15)
        time.sleep(0.3)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 200 and data.get("data"):
                df = pd.DataFrame(data["data"])
                if not df.empty and "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    # 只回傳最近兩期
                    latest_dates = sorted(df["date"].unique(), reverse=True)[:2]
                    df = df[df["date"].isin(latest_dates)]
                    return df

    except Exception as e:
        logger.warning(f"FinMind 大戶持股資料擷取失敗 {stock_id}: {e}")

    return None


def get_mock_institutional_data(stock_id: str) -> Dict:
    """
    當 API 不可用時，產生模擬法人資料（用於測試）
    """
    import random
    rng = np.random.default_rng(seed=int(stock_id) if stock_id.isdigit() else 0)

    return {
        "foreign_net": rng.integers(-5000, 5000),      # 外資買賣超 (張)
        "trust_net": rng.integers(-2000, 2000),          # 投信買賣超
        "dealer_net": rng.integers(-1000, 1000),         # 自營商買賣超
        "foreign_3d": rng.integers(-10000, 10000),       # 外資3日累計
        "foreign_10d": rng.integers(-20000, 20000),      # 外資10日累計
        "margin_balance": rng.integers(1000, 50000),     # 融資餘額
        "margin_change": rng.integers(-5000, 5000),      # 融資增減
        "short_balance": rng.integers(100, 10000),       # 融券餘額
    }


def get_mock_financial_data(stock_id: str) -> Dict:
    """
    當 API 不可用時，產生模擬基本面資料（用於測試）
    """
    rng = np.random.default_rng(seed=int(stock_id) if stock_id.isdigit() else 0)

    eps = round(rng.uniform(1.0, 20.0), 2)
    revenue_growth = round(rng.uniform(-0.2, 0.5), 4)
    roe = round(rng.uniform(0.05, 0.35), 4)
    pe_ratio = round(rng.uniform(8, 40), 1)

    return {
        "eps": eps,
        "eps_growth": round(rng.uniform(-0.3, 0.8), 4),
        "revenue_growth": revenue_growth,
        "roe": roe,
        "pe_ratio": pe_ratio,
        "pb_ratio": round(rng.uniform(0.5, 5.0), 2),
        "dividend_yield": round(rng.uniform(0, 0.08), 4),
    }
