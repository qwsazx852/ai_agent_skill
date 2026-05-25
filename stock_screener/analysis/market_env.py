"""
市場環境分析模組
判斷大盤多空狀態，對所有個股評分施加全局調整

邏輯：個股再強，在空頭市場也容易被打壓
→ 市場健康 = 個股評分正常
→ 市場疲軟 = 全面打折，提高入場門檻
"""

import logging
from typing import Dict, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 台股大盤代理：0050（元大台灣50）最具代表性
MARKET_PROXY_TICKER = "0050.TW"
FALLBACK_TICKER = "^TWII"


def get_market_environment(price_data_cache: Optional[Dict] = None) -> Dict:
    """
    判斷市場環境

    Returns:
        {
          "status": "bull" | "neutral" | "bear" | "unknown",
          "score_multiplier": 0.75~1.0,   # 對個股評分的乘數
          "description": str,
          "signals": [...],
          "indicators": {...}
        }
    """
    result = {
        "status": "unknown",
        "score_multiplier": 1.0,
        "description": "市場狀態未知，給予中性調整",
        "signals": [],
        "indicators": {},
    }

    try:
        df = None

        # 從快取取
        if price_data_cache:
            for ticker in [MARKET_PROXY_TICKER, FALLBACK_TICKER, "0050.TW"]:
                if ticker in price_data_cache:
                    df = price_data_cache[ticker]
                    break

        # 嘗試下載
        if df is None or len(df) < 30:
            try:
                import yfinance as yf
                import warnings
                warnings.filterwarnings("ignore")
                from ..data.fetcher import fetch_price_data
                raw_df = fetch_price_data(MARKET_PROXY_TICKER, days=180)
                if raw_df is not None and len(raw_df) >= 30:
                    df = raw_df
            except Exception as e:
                logger.debug(f"大盤資料下載失敗: {e}")

        if df is None or len(df) < 20:
            return result

        close = df["close"].astype(float)

        # ── 計算市場指標 ──────────────────────────────────────
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean() if len(close) >= 60 else None

        c = close.iloc[-1]
        m20 = ma20.iloc[-1]
        m60 = ma60.iloc[-1] if ma60 is not None else None

        # 20日均線斜率（正 = 上升中）
        ma20_slope = (ma20.iloc[-1] - ma20.iloc[-5]) / ma20.iloc[-5] * 100 if len(ma20) >= 5 else 0

        # 近20日漲跌幅
        ret_20d = (c / close.iloc[-20] - 1) * 100

        # 近5日漲跌幅
        ret_5d = (c / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0

        result["indicators"] = {
            "price": round(c, 2),
            "ma20": round(m20, 2),
            "ma60": round(m60, 2) if m60 else None,
            "ma20_slope": round(ma20_slope, 2),
            "ret_20d": round(ret_20d, 2),
            "ret_5d": round(ret_5d, 2),
        }

        # ── 判斷市場狀態 ──────────────────────────────────────
        above_ma20 = c > m20
        above_ma60 = (c > m60) if m60 else True
        ma20_rising = ma20_slope > 0

        if above_ma20 and above_ma60 and ma20_rising:
            # 強多頭
            status = "bull"
            multiplier = 1.0
            desc = "📈 大盤多頭，順勢操作"
            result["signals"].append(f"✅ 0050 站上 MA20/MA60，趨勢向上")

        elif above_ma20 and (not ma20_rising or not above_ma60):
            # 震盪偏多
            status = "neutral"
            multiplier = 0.92
            desc = "🔄 大盤震盪，個股分化"
            result["signals"].append("⚠️ 大盤均線走平，宜精選個股")

        elif not above_ma20 and above_ma60:
            # 短線轉弱但中期未破壞
            status = "neutral"
            multiplier = 0.88
            desc = "⚠️ 大盤短線修正，謹慎追高"
            result["signals"].append("⚠️ 0050 跌破 MA20，短線偏弱")

        elif not above_ma20 and not above_ma60:
            # 空頭市場
            status = "bear"
            multiplier = 0.78
            desc = "🔻 大盤空頭，降低曝險"
            result["signals"].append("🚨 0050 跌破 MA60，空頭市場")

        else:
            status = "unknown"
            multiplier = 0.95
            desc = "市場狀態不明確"

        result["status"] = status
        result["score_multiplier"] = multiplier
        result["description"] = desc

    except Exception as e:
        logger.warning(f"市場環境分析失敗: {e}")

    return result
