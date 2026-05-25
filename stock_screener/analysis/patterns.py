"""
技術形態辨識模組
偵測各種 K 線與價量形態，提供形態評分 (0-20)
"""

import numpy as np
import pandas as pd
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def detect_patterns(df: pd.DataFrame) -> Dict:
    """
    偵測技術形態

    Args:
        df: OHLCV DataFrame

    Returns:
        {"patterns": [...], "pattern_score": 0-20}
    """
    if df is None or len(df) < 20:
        return {"patterns": [], "pattern_score": 0}

    patterns = []
    score = 0
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    volume = df["volume"]

    try:
        # 1. 突破近20日高點  +5分
        recent_high_20 = high.iloc[-21:-1].max()
        if close.iloc[-1] > recent_high_20 * 1.005:
            score += 5
            patterns.append(f"🚀 突破近20日高點 ({recent_high_20:.1f})")

        # 2. MA5 剛黃金交叉 MA20 (近5日內)  +4分
        if len(close) >= 25:
            ma5  = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            for i in range(-5, -1):
                if (ma5.iloc[i] > ma20.iloc[i] and ma5.iloc[i-1] <= ma20.iloc[i-1]):
                    score += 4
                    patterns.append("🌟 MA5 剛黃金交叉 MA20")
                    break

        # 3. 縮量整理後放量突破  +4分
        if len(volume) >= 10:
            consol_vol = volume.iloc[-6:-1].mean()
            price_range = (high.iloc[-6:-1].max() - low.iloc[-6:-1].min()) / close.iloc[-6]
            if (volume.iloc[-1] > consol_vol * 1.5 and
                    price_range < 0.06 and
                    close.iloc[-1] > close.iloc[-2]):
                score += 4
                patterns.append("💥 縮量整理後放量突破")

        # 4. 連三紅  +3分
        if len(close) >= 4:
            if all(close.iloc[i] > close.iloc[i-1] for i in [-1, -2, -3]):
                score += 3
                patterns.append("📈 連三日收紅")

        # 5. 低點持續墊高  +2分
        if len(low) >= 10:
            lows_10 = low.iloc[-10:]
            local_lows = [
                lows_10.iloc[i]
                for i in range(1, len(lows_10) - 1)
                if lows_10.iloc[i] < lows_10.iloc[i-1] and lows_10.iloc[i] < lows_10.iloc[i+1]
            ]
            if len(local_lows) >= 2 and local_lows[-1] > local_lows[-2] * 1.005:
                score += 2
                patterns.append("📊 低點持續墊高 (N字上升)")

        # 6. 底部放量反彈  +2分
        if len(df) >= 15:
            low_10d    = low.iloc[-11:-1].min()
            today_chg  = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]
            vol_ratio  = volume.iloc[-1] / (volume.iloc[-11:-1].mean() + 1e-10)
            if (close.iloc[-2] <= low_10d * 1.02 and today_chg > 0.01 and vol_ratio > 1.5):
                score += 2
                patterns.append("🔄 底部放量反彈")

        # 7. 箱型向上突破  +2分
        if len(df) >= 20:
            box_high  = high.iloc[-16:-1].max()
            box_low   = low.iloc[-16:-1].min()
            box_range = (box_high - box_low) / (box_low + 1e-10)
            if box_range < 0.08 and close.iloc[-1] > box_high * 1.005:
                score += 2
                patterns.append(f"📦 箱型向上突破 ({box_range*100:.1f}%箱寬)")

        # 反向: 今日大跌扣3分
        today_chg = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]
        if today_chg < -0.04:
            score = max(0, score - 3)
            patterns.append(f"⚠️ 今日大跌 ({today_chg*100:.1f}%)")

    except Exception as e:
        logger.debug(f"形態偵測錯誤: {e}")

    return {"patterns": patterns, "pattern_score": min(score, 20)}


def get_pattern_summary(patterns: List[str]) -> str:
    """將形態清單轉為簡短摘要"""
    return " | ".join(patterns[:2]) if patterns else "無特殊形態"
