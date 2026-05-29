"""
族群資金流向分析
計算三大法人在各概念主題的淨資金流向（億元），仿照盤後大戶資金流向報告格式

流程：
1. 從 THEMES 收集所有主題股票
2. 擷取三大法人買賣超（張）
3. 換算為億元：淨張數 × 1000 × 股價 / 1億
4. 依主題加總，輸出買超/賣超 TOP N
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .themes import THEMES

logger = logging.getLogger(__name__)

_LOTS_TO_SHARES = 1000   # 1張 = 1000股
_YI = 1e8                # 1億


def _all_theme_stocks() -> List[str]:
    """回傳所有主題中的不重複股票代號"""
    seen = set()
    stocks = []
    for theme_data in THEMES.values():
        for sid in theme_data.get("stocks", []):
            if sid not in seen:
                seen.add(sid)
                stocks.append(sid)
    return stocks


def fetch_sector_institutional_data(
    token: str,
    stock_ids: List[str],
    lookback_days: int = 5,
    delay: float = 0.25,
) -> Dict[str, Dict]:
    """
    批次擷取三大法人買賣超（最新交易日）

    Returns:
        {stock_id: {foreign_net, trust_net, dealer_net, total_net}}  單位：張
    """
    import requests

    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    url = "https://api.finmindtrade.com/api/v4/data"
    result: Dict[str, Dict] = {}

    for i, stock_id in enumerate(stock_ids, 1):
        try:
            resp = requests.get(
                url,
                params={
                    "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
                    "data_id": stock_id,
                    "start_date": start_date,
                    "token": token,
                },
                timeout=10,
            )
            time.sleep(delay)

            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get("status") != 200 or not data.get("data"):
                continue

            df = pd.DataFrame(data["data"])
            latest_date = df["date"].max()
            latest = df[df["date"] == latest_date]

            foreign_net = trust_net = dealer_net = 0
            for _, row in latest.iterrows():
                name = str(row.get("name", ""))
                net = int(row.get("buy", 0)) - int(row.get("sell", 0))
                if "外陸資" in name:
                    foreign_net += net
                elif name == "投信":
                    trust_net = net
                elif "自營商" in name:
                    dealer_net += net

            result[stock_id] = {
                "foreign_net": foreign_net,
                "trust_net": trust_net,
                "dealer_net": dealer_net,
                "total_net": foreign_net + trust_net + dealer_net,
            }

        except Exception as e:
            logger.debug(f"法人資料擷取失敗 {stock_id}: {e}")

        if i % 30 == 0:
            logger.info(f"  法人資料進度: {i}/{len(stock_ids)}")

    return result


def _build_price_maps(
    price_data: Optional[Dict[str, pd.DataFrame]],
    stock_ticker_map: Optional[Dict[str, str]],
    stock_ids: List[str],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    從已有的 price_data 或另行下載，回傳 price_map / change_map
    {stock_id: 收盤價}, {stock_id: 漲跌幅%}
    """
    price_map: Dict[str, float] = {}
    change_map: Dict[str, float] = {}

    if price_data and stock_ticker_map:
        reverse = {v: k for k, v in stock_ticker_map.items()}
        for ticker, df in price_data.items():
            if df is None or len(df) < 2:
                continue
            sid = reverse.get(ticker) or ticker.split(".")[0]
            price_map[sid] = float(df["close"].iloc[-1])
            change_map[sid] = float((df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100)
        return price_map, change_map

    # 沒有現成資料 → 用 yfinance 下載
    try:
        from ..data.fetcher import fetch_batch_price_data
        tickers = [f"{s}.TW" for s in stock_ids]
        downloaded = fetch_batch_price_data(tickers, days=5, batch_size=30, delay=1.0)
        for ticker, df in downloaded.items():
            if df is None or len(df) < 2:
                continue
            sid = ticker.split(".")[0]
            price_map[sid] = float(df["close"].iloc[-1])
            change_map[sid] = float((df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100)
    except Exception as e:
        logger.warning(f"價格資料下載失敗: {e}")

    return price_map, change_map


def calculate_theme_flow(
    inst_data: Dict[str, Dict],
    price_map: Dict[str, float],
    change_map: Dict[str, float],
) -> List[Dict]:
    """
    計算各主題的資金流向

    Returns:
        List[{theme_id, name, emoji, net_flow_yi, avg_change_pct, active_count}]
    """
    theme_results = []

    for theme_id, theme_data in THEMES.items():
        stocks = theme_data.get("stocks", [])
        total_flow_yi = 0.0
        changes: List[float] = []
        active = 0

        for sid in stocks:
            inst = inst_data.get(sid)
            price = price_map.get(sid, 0.0)
            if inst is None or price <= 0:
                continue

            net_lots = inst.get("total_net", 0)
            flow_yi = net_lots * _LOTS_TO_SHARES * price / _YI
            total_flow_yi += flow_yi

            chg = change_map.get(sid)
            if chg is not None:
                changes.append(chg)
            active += 1

        if active == 0:
            continue

        theme_results.append({
            "theme_id": theme_id,
            "name": theme_data["name"],
            "emoji": theme_data.get("emoji", ""),
            "net_flow_yi": round(total_flow_yi, 2),
            "avg_change_pct": round(sum(changes) / len(changes), 2) if changes else 0.0,
            "active_count": active,
        })

    return theme_results


def get_top_buy_sell(
    theme_flows: List[Dict],
    top_n: int = 10,
) -> Tuple[List[Dict], List[Dict]]:
    """
    回傳 (買超 TOP N, 賣超 TOP N)，各依 net_flow_yi 排序
    """
    buy = sorted(
        [t for t in theme_flows if t["net_flow_yi"] > 0],
        key=lambda x: x["net_flow_yi"],
        reverse=True,
    )[:top_n]

    sell = sorted(
        [t for t in theme_flows if t["net_flow_yi"] < 0],
        key=lambda x: x["net_flow_yi"],
    )[:top_n]

    return buy, sell


def run_sector_flow_analysis(
    token: str,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
    stock_ticker_map: Optional[Dict[str, str]] = None,
    top_n: int = 10,
) -> Dict:
    """
    執行完整族群資金流向分析

    Args:
        token: FinMind API token
        price_data: 已有的價格資料 {ticker: df}（可選，若無則自行下載）
        stock_ticker_map: {stock_id: yf_ticker}（搭配 price_data 使用）
        top_n: 排行榜數量

    Returns:
        {date, top_buy, top_sell, all_themes, stocks_analyzed}
    """
    today = datetime.now().strftime("%Y-%m-%d")
    all_stocks = _all_theme_stocks()
    logger.info(f"族群資金流向：{len(all_stocks)} 支主題股票")

    price_map, change_map = _build_price_maps(price_data, stock_ticker_map, all_stocks)
    logger.info(f"取得 {len(price_map)} 支股票價格")

    inst_data = fetch_sector_institutional_data(token, all_stocks)
    logger.info(f"取得 {len(inst_data)} 支股票法人資料")

    theme_flows = calculate_theme_flow(inst_data, price_map, change_map)
    top_buy, top_sell = get_top_buy_sell(theme_flows, top_n=top_n)

    return {
        "date": today,
        "top_buy": top_buy,
        "top_sell": top_sell,
        "all_themes": sorted(theme_flows, key=lambda x: x["net_flow_yi"], reverse=True),
        "stocks_analyzed": len(inst_data),
    }
