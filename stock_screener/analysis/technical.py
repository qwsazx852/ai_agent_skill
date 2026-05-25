"""
技術分析模組
計算各種技術指標並給出技術面評分 (0-100)

指標包含:
- 移動平均線 (MA5, MA10, MA20, MA60)
- MACD
- RSI
- KD (隨機震盪指標)
- 布林通道 (Bollinger Bands)
- 成交量分析
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def calculate_ma(prices: pd.Series, window: int) -> pd.Series:
    """計算移動平均線"""
    return prices.rolling(window=window).mean()


def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    計算 MACD

    Returns:
        (macd_line, signal_line, histogram)
    """
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """計算 RSI 相對強弱指標"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_kd(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 9,
    smooth_k: int = 3,
    smooth_d: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """
    計算 KD 隨機震盪指標

    Returns:
        (K線, D線)
    """
    lowest_low = low.rolling(window=window).min()
    highest_high = high.rolling(window=window).max()

    rsv = (close - lowest_low) / (highest_high - lowest_low + 1e-10) * 100
    k = rsv.ewm(com=smooth_k - 1, adjust=False).mean()
    d = k.ewm(com=smooth_d - 1, adjust=False).mean()
    return k, d


def calculate_bollinger_bands(
    prices: pd.Series,
    window: int = 20,
    num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    計算布林通道

    Returns:
        (upper_band, middle_band, lower_band)
    """
    middle = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return upper, middle, lower


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14
) -> pd.Series:
    """計算 ATR 真實波動幅度"""
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=window).mean()


def analyze_technical(df: pd.DataFrame) -> Dict:
    """
    完整技術分析，回傳各指標值與評分

    Args:
        df: OHLCV DataFrame (index=日期, columns=open/high/low/close/volume)

    Returns:
        Dict containing indicators and score (0-100)
    """
    if df is None or len(df) < 30:
        return {"score": 0, "signals": [], "error": "資料不足"}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    result = {
        "score": 0,
        "signals": [],
        "indicators": {},
        "sub_scores": {}
    }

    score = 0
    signals = []
    indicators = {}
    sub_scores = {}

    # ========================
    # 1. 移動平均線分析 (最高 25 分)
    # ========================
    ma_score = 0
    try:
        ma5 = calculate_ma(close, 5)
        ma10 = calculate_ma(close, 10)
        ma20 = calculate_ma(close, 20)
        ma60 = calculate_ma(close, 60) if len(df) >= 60 else None

        c = close.iloc[-1]
        indicators["ma5"] = round(ma5.iloc[-1], 2)
        indicators["ma10"] = round(ma10.iloc[-1], 2)
        indicators["ma20"] = round(ma20.iloc[-1], 2)

        # 多頭排列: 價格 > MA5 > MA10 > MA20
        m5 = ma5.iloc[-1]
        m10 = ma10.iloc[-1]
        m20 = ma20.iloc[-1]

        if c > m5:
            ma_score += 6
            signals.append("✅ 站上 MA5")
        if c > m10:
            ma_score += 5
        if c > m20:
            ma_score += 7
            signals.append("✅ 站上 MA20")
        if m5 > m10 > m20:
            ma_score += 7
            signals.append("🚀 均線多頭排列")

        if ma60 is not None:
            m60 = ma60.iloc[-1]
            indicators["ma60"] = round(m60, 2)
            if c > m60:
                ma_score = min(ma_score + 5, 25)
                signals.append("✅ 站上年線")

        # MA5 黃金交叉 MA20
        if len(ma5) >= 2 and len(ma20) >= 2:
            if ma5.iloc[-1] > ma20.iloc[-1] and ma5.iloc[-2] <= ma20.iloc[-2]:
                ma_score = min(ma_score + 5, 25)
                signals.append("🌟 MA5 黃金交叉 MA20")

        ma_score = min(ma_score, 25)

    except Exception as e:
        logger.debug(f"MA 計算錯誤: {e}")

    sub_scores["moving_average"] = ma_score
    score += ma_score

    # ========================
    # 2. MACD 分析 (最高 20 分)
    # ========================
    macd_score = 0
    try:
        macd_line, signal_line, histogram = calculate_macd(close)

        macd_val = macd_line.iloc[-1]
        signal_val = signal_line.iloc[-1]
        hist_val = histogram.iloc[-1]

        indicators["macd"] = round(macd_val, 4)
        indicators["macd_signal"] = round(signal_val, 4)
        indicators["macd_hist"] = round(hist_val, 4)

        # MACD 在零軸以上
        if macd_val > 0:
            macd_score += 7

        # MACD > Signal (多頭)
        if macd_val > signal_val:
            macd_score += 7
            signals.append("✅ MACD 多頭")

        # 柱狀體增加中 (動能增強)
        if len(histogram) >= 3:
            if histogram.iloc[-1] > histogram.iloc[-2] > histogram.iloc[-3]:
                macd_score += 6
                signals.append("📈 MACD 動能增強")
            elif histogram.iloc[-1] > histogram.iloc[-2]:
                macd_score += 3

        # 黃金交叉信號
        if (macd_line.iloc[-1] > signal_line.iloc[-1] and
                macd_line.iloc[-2] <= signal_line.iloc[-2]):
            macd_score = min(macd_score + 5, 20)
            signals.append("🌟 MACD 黃金交叉")

        macd_score = min(macd_score, 20)

    except Exception as e:
        logger.debug(f"MACD 計算錯誤: {e}")

    sub_scores["macd"] = macd_score
    score += macd_score

    # ========================
    # 3. RSI 分析 (最高 15 分)
    # ========================
    rsi_score = 0
    try:
        rsi = calculate_rsi(close)
        rsi_val = rsi.iloc[-1]
        indicators["rsi"] = round(rsi_val, 2)

        if 40 <= rsi_val <= 70:
            rsi_score = 15
            if rsi_val >= 55:
                signals.append(f"✅ RSI 強勢區 ({rsi_val:.1f})")
        elif 70 < rsi_val <= 80:
            rsi_score = 10  # 偏強但稍過熱
            signals.append(f"⚠️ RSI 偏高 ({rsi_val:.1f})")
        elif rsi_val < 30:
            rsi_score = 8  # 超賣反彈機會
            signals.append(f"📉 RSI 超賣 ({rsi_val:.1f})")
        elif 30 <= rsi_val < 40:
            rsi_score = 5
        elif rsi_val > 80:
            rsi_score = 3  # 嚴重超買

    except Exception as e:
        logger.debug(f"RSI 計算錯誤: {e}")

    sub_scores["rsi"] = rsi_score
    score += rsi_score

    # ========================
    # 4. KD 分析 (最高 15 分)
    # ========================
    kd_score = 0
    try:
        k, d = calculate_kd(high, low, close)
        k_val = k.iloc[-1]
        d_val = d.iloc[-1]

        indicators["k"] = round(k_val, 2)
        indicators["d"] = round(d_val, 2)

        # K > D 多頭
        if k_val > d_val:
            kd_score += 5
            signals.append("✅ KD 多頭")

        # K, D 在適當區間 (20-80)
        if 20 < k_val < 80 and 20 < d_val < 80:
            kd_score += 5

        # KD 黃金交叉 (K由下往上穿越D)
        if (len(k) >= 2 and len(d) >= 2 and
                k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2] and
                d.iloc[-1] < 50):
            kd_score = min(kd_score + 5, 15)
            signals.append("🌟 KD 黃金交叉")

        # 超賣反彈 (K < 20)
        if k_val < 20:
            kd_score = min(kd_score + 3, 15)
            signals.append("💡 KD 超賣反彈機會")

        kd_score = min(kd_score, 15)

    except Exception as e:
        logger.debug(f"KD 計算錯誤: {e}")

    sub_scores["kd"] = kd_score
    score += kd_score

    # ========================
    # 5. 布林通道分析 (最高 10 分)
    # ========================
    bb_score = 0
    try:
        upper, middle, lower = calculate_bollinger_bands(close)
        c = close.iloc[-1]
        u = upper.iloc[-1]
        m = middle.iloc[-1]
        l = lower.iloc[-1]

        indicators["bb_upper"] = round(u, 2)
        indicators["bb_middle"] = round(m, 2)
        indicators["bb_lower"] = round(l, 2)

        # 計算 %B 指標
        bb_pct = (c - l) / (u - l + 1e-10)
        indicators["bb_pct"] = round(bb_pct, 3)

        if 0.4 <= bb_pct <= 0.8:
            bb_score = 10  # 在中軌到上軌之間，強勢
        elif 0.2 <= bb_pct < 0.4:
            bb_score = 6  # 接近中軌
        elif bb_pct < 0.2:
            bb_score = 4  # 接近下軌（可能反彈）
            signals.append("💡 接近布林下軌支撐")
        else:
            bb_score = 2  # 超過上軌（超買）

        # 價格突破上軌
        if c > u:
            signals.append("🚀 突破布林上軌")

    except Exception as e:
        logger.debug(f"布林通道計算錯誤: {e}")

    sub_scores["bollinger"] = bb_score
    score += bb_score

    # ========================
    # 6. 成交量分析 (最高 15 分)
    # ========================
    vol_score = 0
    try:
        vol_ma5 = volume.rolling(5).mean()
        vol_ma20 = volume.rolling(20).mean()

        curr_vol = volume.iloc[-1]
        avg_vol5 = vol_ma5.iloc[-1]
        avg_vol20 = vol_ma20.iloc[-1]

        indicators["volume"] = int(curr_vol)
        indicators["volume_ma5"] = int(avg_vol5) if not np.isnan(avg_vol5) else 0
        indicators["volume_ratio"] = round(curr_vol / avg_vol20, 2) if avg_vol20 > 0 else 0

        vol_ratio = curr_vol / (avg_vol20 + 1e-10)

        if vol_ratio >= 2.0:
            vol_score = 15
            signals.append(f"🔥 爆量 ({vol_ratio:.1f}x 均量)")
        elif vol_ratio >= 1.5:
            vol_score = 12
            signals.append(f"📊 放量 ({vol_ratio:.1f}x 均量)")
        elif vol_ratio >= 1.2:
            vol_score = 9
        elif vol_ratio >= 0.8:
            vol_score = 6
        else:
            vol_score = 3  # 縮量

        # 量價齊揚：價格上漲 + 成交量放大
        price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]
        if price_change > 0.01 and vol_ratio >= 1.3:
            vol_score = min(vol_score + 3, 15)
            signals.append("✅ 量價齊揚")

        vol_score = min(vol_score, 15)

    except Exception as e:
        logger.debug(f"成交量計算錯誤: {e}")

    sub_scores["volume"] = vol_score
    score += vol_score

    # ========================
    # 整理最終結果
    # ========================
    # 計算近期漲跌幅
    try:
        indicators["price"] = round(close.iloc[-1], 2)
        indicators["change_1d"] = round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2)
        indicators["change_5d"] = round((close.iloc[-1] / close.iloc[-5] - 1) * 100, 2)
        indicators["change_20d"] = round((close.iloc[-1] / close.iloc[-20] - 1) * 100, 2)
    except Exception:
        pass

    result["score"] = min(round(score), 100)
    result["signals"] = signals[:5]  # 最多顯示5個訊號
    result["indicators"] = indicators
    result["sub_scores"] = sub_scores

    return result
