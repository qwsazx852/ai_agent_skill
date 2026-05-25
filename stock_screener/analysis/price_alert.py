"""
異常價量警報模組
監控觀察名單（上次篩選 TOP30）的今日異常動態

警報條件：
- 急漲 > +5%（突破性上漲）
- 急跌 < -5%（止損警告）
- 爆量 > 3x 均量（異常成交量）
- 突破年高（52週新高）
- 跌破重要均線（MA20 或 MA60）
"""

import logging
import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 警報閾值
ALERT_SURGE   = 5.0    # 急漲 %
ALERT_DROP    = -5.0   # 急跌 %
ALERT_VOLUME  = 3.0    # 爆量倍數（相對20日均量）
ALERT_VOLUME_MILD = 2.0  # 輕微爆量


def check_price_alerts(
    stock_id: str,
    stock_name: str,
    df: pd.DataFrame,
) -> List[Dict]:
    """
    對單一股票的 K 線資料進行異常偵測

    Args:
        stock_id: 股票代號
        stock_name: 股票名稱
        df: OHLCV DataFrame（至少 60 天）

    Returns:
        List of alert dicts: [{type, level, message, value}, ...]
    """
    alerts = []
    if df is None or len(df) < 5:
        return alerts

    try:
        closes = df["close"].values.astype(float)
        volumes = df["volume"].values.astype(float)
        highs = df["high"].values.astype(float)

        latest_close = closes[-1]
        prev_close = closes[-2]
        latest_vol = volumes[-1]

        # ── 今日漲跌幅 ─────────────────────────────────────────
        change_pct = (latest_close / prev_close - 1) * 100

        if change_pct >= ALERT_SURGE:
            alerts.append({
                "type": "surge",
                "level": "high",
                "emoji": "🚀",
                "message": f"急漲 +{change_pct:.1f}%",
                "value": change_pct,
            })
        elif change_pct >= 3.0:
            alerts.append({
                "type": "surge_mild",
                "level": "medium",
                "emoji": "📈",
                "message": f"上漲 +{change_pct:.1f}%",
                "value": change_pct,
            })
        elif change_pct <= ALERT_DROP:
            alerts.append({
                "type": "drop",
                "level": "high",
                "emoji": "🔻",
                "message": f"急跌 {change_pct:.1f}%",
                "value": change_pct,
            })
        elif change_pct <= -3.0:
            alerts.append({
                "type": "drop_mild",
                "level": "medium",
                "emoji": "📉",
                "message": f"下跌 {change_pct:.1f}%",
                "value": change_pct,
            })

        # ── 成交量異常 ──────────────────────────────────────────
        if len(volumes) >= 20:
            avg_vol_20d = np.mean(volumes[-21:-1])  # 前20日均量
            if avg_vol_20d > 0:
                vol_ratio = latest_vol / avg_vol_20d
                if vol_ratio >= ALERT_VOLUME:
                    alerts.append({
                        "type": "volume_surge",
                        "level": "high",
                        "emoji": "💥",
                        "message": f"爆量 {vol_ratio:.1f}x 均量",
                        "value": vol_ratio,
                    })
                elif vol_ratio >= ALERT_VOLUME_MILD:
                    alerts.append({
                        "type": "volume_mild",
                        "level": "medium",
                        "emoji": "📊",
                        "message": f"量增 {vol_ratio:.1f}x 均量",
                        "value": vol_ratio,
                    })

        # ── 突破52週新高 ────────────────────────────────────────
        if len(closes) >= 60:
            high_52w = np.max(highs[-252:]) if len(highs) >= 252 else np.max(highs)
            if latest_close >= high_52w * 0.995:  # 在1%以內視為突破
                alerts.append({
                    "type": "new_high",
                    "level": "high",
                    "emoji": "🏆",
                    "message": "突破近高點",
                    "value": latest_close,
                })

        # ── 跌破 MA20 ──────────────────────────────────────────
        if len(closes) >= 22:
            ma20 = np.mean(closes[-21:-1])  # 前20日MA（不含今日）
            if prev_close > ma20 and latest_close < ma20:
                alerts.append({
                    "type": "break_ma20",
                    "level": "medium",
                    "emoji": "⚠️",
                    "message": f"跌破MA20 ({ma20:.1f})",
                    "value": ma20,
                })

        # ── 黃金交叉 (MA5 上穿 MA20) ───────────────────────────
        if len(closes) >= 22:
            ma5_today = np.mean(closes[-5:])
            ma5_prev = np.mean(closes[-6:-1])
            ma20_today = np.mean(closes[-20:])
            ma20_prev = np.mean(closes[-21:-1])
            if ma5_prev < ma20_prev and ma5_today >= ma20_today:
                alerts.append({
                    "type": "golden_cross",
                    "level": "high",
                    "emoji": "✨",
                    "message": "MA5 黃金交叉 MA20",
                    "value": ma5_today,
                })

    except Exception as e:
        logger.debug(f"警報偵測失敗 {stock_id}: {e}")

    return alerts


def run_watchlist_alerts(
    results_file: str,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
    top_n_watchlist: int = 30,
) -> Dict:
    """
    讀取上次篩選結果，對 TOP N 觀察股執行異常偵測

    Args:
        results_file: latest_screening.json 路徑
        price_data: 已下載的價格資料（若無則自動下載）
        top_n_watchlist: 監控幾檔

    Returns:
        {"alerts": [...], "summary": {...}}
    """
    # 讀取觀察名單
    watchlist = []
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        all_stocks = data.get("top_stocks", data.get("all_stocks", []))
        watchlist = all_stocks[:top_n_watchlist]
        logger.info(f"載入觀察名單: {len(watchlist)} 檔")
    except Exception as e:
        logger.error(f"讀取篩選結果失敗: {e}")
        return {"alerts": [], "summary": {}}

    if not watchlist:
        return {"alerts": [], "summary": {}}

    # 下載價格資料（若未提供）
    if price_data is None:
        from ..data.fetcher import fetch_price_data
        price_data = {}
        for stock in watchlist:
            sid = stock.get("stock_id", "")
            ticker = sid + ".TW"  # 預設上市
            if stock.get("market") == "OTC":
                ticker = sid + ".TWO"
            df = fetch_price_data(ticker, days=60)
            if df is not None:
                price_data[ticker] = df

    # 執行警報偵測
    all_alerts = []
    for stock in watchlist:
        sid = stock.get("stock_id", "")
        name = stock.get("stock_name", sid)
        ticker = sid + ".TW"
        if stock.get("market") == "OTC":
            ticker = sid + ".TWO"

        df = price_data.get(ticker)
        if df is None:
            continue

        stock_alerts = check_price_alerts(sid, name, df)
        for alert in stock_alerts:
            alert["stock_id"] = sid
            alert["stock_name"] = name
            alert["prev_score"] = stock.get("composite_score", 0)
            alert["grade"] = stock.get("grade", "")
            all_alerts.append(alert)

    # 依嚴重程度排序
    level_order = {"high": 0, "medium": 1, "low": 2}
    all_alerts.sort(key=lambda x: (level_order.get(x["level"], 9), -x.get("prev_score", 0)))

    summary = {
        "total_alerts": len(all_alerts),
        "high_alerts": len([a for a in all_alerts if a["level"] == "high"]),
        "medium_alerts": len([a for a in all_alerts if a["level"] == "medium"]),
        "watchlist_count": len(watchlist),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    logger.info(f"警報偵測完成: 高優先 {summary['high_alerts']} 個，中 {summary['medium_alerts']} 個")
    return {"alerts": all_alerts, "summary": summary}


def format_alert_telegram_messages(
    alerts: List[Dict],
    summary: Dict,
) -> List[str]:
    """
    產生異常警報 Telegram 訊息

    Returns:
        List of message strings
    """
    date_str = summary.get("date", datetime.now().strftime("%Y-%m-%d %H:%M"))
    high = summary.get("high_alerts", 0)
    total = summary.get("total_alerts", 0)
    watchlist_n = summary.get("watchlist_count", 0)

    messages = []

    if total == 0:
        msg = (
            f"✅ *觀察股票異常警報*\n"
            f"📅 {date_str}\n"
            f"{'─' * 28}\n"
            f"監控 {watchlist_n} 檔觀察股，今日無異常動態"
        )
        return [msg]

    # 訊息一：概覽
    mood = "🚨 有重要異常，請留意！" if high > 0 else "📊 有些動態值得觀察"
    msg1 = (
        f"🔔 *觀察股票異常警報*\n"
        f"📅 {date_str}\n"
        f"{'─' * 28}\n"
        f"{mood}\n"
        f"監控 {watchlist_n} 檔 │ 高優先 {high} 個 │ 共 {total} 個\n\n"
    )

    # 高優先警報
    high_alerts = [a for a in alerts if a["level"] == "high"]
    if high_alerts:
        msg1 += "🚨 *高優先警報*\n"
        for a in high_alerts[:8]:
            sid = a["stock_id"]
            name = a.get("stock_name", sid)
            grade = a.get("grade", "")
            emoji = a.get("emoji", "")
            msg = a.get("message", "")
            score = a.get("prev_score", 0)
            msg1 += f"{emoji} `{sid}` {name[:5]} ({grade}/{score:.0f}分) — {msg}\n"

    messages.append(msg1)

    # 訊息二：中優先
    medium_alerts = [a for a in alerts if a["level"] == "medium"]
    if medium_alerts:
        msg2 = "📊 *中優先觀察*\n"
        for a in medium_alerts[:10]:
            sid = a["stock_id"]
            name = a.get("stock_name", sid)
            emoji = a.get("emoji", "")
            msg = a.get("message", "")
            msg2 += f"{emoji} `{sid}` {name[:5]} — {msg}\n"
        msg2 += f"\n_⚠️ 僅供參考，不構成投資建議_"
        messages.append(msg2)

    return messages
