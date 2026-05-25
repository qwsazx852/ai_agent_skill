"""
籌碼面分析模組
分析三大法人買賣超、融資融券並給出籌碼評分 (0-100)

指標包含:
- 外資買賣超 (當日 + 近期累計)
- 投信買賣超
- 自營商買賣超
- 融資增減
- 融券增減
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def analyze_institutional(inst_data: Dict) -> Dict:
    """
    籌碼面評分

    Args:
        inst_data: 籌碼資料字典，包含:
            - foreign_net: 外資當日買賣超 (張)
            - trust_net: 投信當日買賣超
            - dealer_net: 自營商當日買賣超
            - foreign_3d: 外資近3日累計買賣超
            - foreign_10d: 外資近10日累計買賣超
            - margin_balance: 融資餘額 (張)
            - margin_change: 融資增減
            - short_balance: 融券餘額

    Returns:
        Dict with score (0-100), signals, sub_scores
    """
    if not inst_data:
        return {"score": 50, "signals": ["⚠️ 籌碼資料不足，給予中性評分"], "sub_scores": {}}

    result = {
        "score": 0,
        "signals": [],
        "sub_scores": {},
        "data": inst_data
    }

    score = 0
    signals = []
    sub_scores = {}

    # ========================
    # 1. 外資分析 (最高 40 分)
    # ========================
    foreign_score = 0

    foreign_net = inst_data.get("foreign_net", 0) or 0
    foreign_3d = inst_data.get("foreign_3d", 0) or 0
    foreign_10d = inst_data.get("foreign_10d", 0) or 0

    # 當日外資
    if foreign_net > 5000:
        foreign_score += 15
        signals.append(f"🏦 外資大買 (+{foreign_net:,}張)")
    elif foreign_net > 1000:
        foreign_score += 10
        signals.append(f"✅ 外資買超 (+{foreign_net:,}張)")
    elif foreign_net > 0:
        foreign_score += 6
    elif foreign_net > -1000:
        foreign_score += 3
    else:
        foreign_score += 0
        signals.append(f"⚠️ 外資賣超 ({foreign_net:,}張)")

    # 近3日外資累計
    if foreign_3d > 10000:
        foreign_score += 15
        signals.append(f"📈 外資3日累計大買 (+{foreign_3d:,}張)")
    elif foreign_3d > 3000:
        foreign_score += 10
    elif foreign_3d > 0:
        foreign_score += 5
    elif foreign_3d < -10000:
        foreign_score += 0
        signals.append(f"📉 外資持續賣超")
    else:
        foreign_score += 2

    # 近10日外資累計
    if foreign_10d > 20000:
        foreign_score += 10
        signals.append(f"🔥 外資10日大量買進")
    elif foreign_10d > 5000:
        foreign_score += 6
    elif foreign_10d > 0:
        foreign_score += 3
    else:
        foreign_score += 0

    foreign_score = min(foreign_score, 40)
    sub_scores["foreign"] = foreign_score
    score += foreign_score

    # ========================
    # 2. 投信分析 (最高 35 分)
    # ========================
    trust_score = 0
    trust_net = inst_data.get("trust_net", 0) or 0

    if trust_net > 2000:
        trust_score = 35
        signals.append(f"🏦 投信大買 (+{trust_net:,}張)")
    elif trust_net > 500:
        trust_score = 25
        signals.append(f"✅ 投信買超 (+{trust_net:,}張)")
    elif trust_net > 100:
        trust_score = 18
    elif trust_net > 0:
        trust_score = 12
    elif trust_net > -500:
        trust_score = 8
    else:
        trust_score = 0
        signals.append(f"⚠️ 投信賣超 ({trust_net:,}張)")

    sub_scores["trust"] = trust_score
    score += trust_score

    # ========================
    # 3. 自營商分析 (最高 25 分)
    # ========================
    dealer_score = 0
    dealer_net = inst_data.get("dealer_net", 0) or 0

    if dealer_net > 1000:
        dealer_score = 25
        signals.append(f"✅ 自營商買超 (+{dealer_net:,}張)")
    elif dealer_net > 200:
        dealer_score = 18
    elif dealer_net > 0:
        dealer_score = 12
    elif dealer_net > -200:
        dealer_score = 8
    else:
        dealer_score = 3

    sub_scores["dealer"] = dealer_score
    score += dealer_score

    # ========================
    # 4. 融資融券調整 (加減分)
    # ========================
    margin_change = inst_data.get("margin_change", 0) or 0
    short_balance = inst_data.get("short_balance", 0) or 0
    margin_balance = inst_data.get("margin_balance", 0) or 0

    margin_adjust = 0

    # 融資增加過多視為風險
    if margin_change > 5000:
        margin_adjust -= 5
        signals.append(f"⚠️ 融資大增 (+{margin_change:,}張)")
    elif margin_change > 2000:
        margin_adjust -= 2
    elif margin_change < -2000:
        margin_adjust += 3  # 融資減少視為籌碼乾淨
        signals.append(f"✅ 融資減少 ({margin_change:,}張)")

    # 融資餘額佔比（若過高風險較大）
    if margin_balance > 50000:
        margin_adjust -= 3

    # 融券放空多代表未來軋空潛力
    if short_balance > 5000:
        margin_adjust += 2
        signals.append(f"💡 融券多 (軋空潛力)")

    final_score = max(0, min(score + margin_adjust, 100))
    sub_scores["margin_adjust"] = margin_adjust

    result["score"] = round(final_score)
    result["signals"] = signals[:5]
    result["sub_scores"] = sub_scores

    return result


def parse_finmind_institutional(df: pd.DataFrame) -> Dict:
    """
    解析 FinMind 三大法人資料

    Args:
        df: FinMind TaiwanStockInstitutionalInvestorsBuySell DataFrame

    Returns:
        標準籌碼資料字典
    """
    if df is None or df.empty:
        return {}

    try:
        # 取最新日期資料
        latest_date = df["date"].max()
        latest = df[df["date"] == latest_date]

        result = {}

        # 外資
        foreign = latest[latest["name"].str.contains("外陸資", na=False)]
        if not foreign.empty:
            result["foreign_net"] = int(foreign["buy"].sum() - foreign["sell"].sum())

        # 投信
        trust = latest[latest["name"] == "投信"]
        if not trust.empty:
            result["trust_net"] = int(trust["buy"].sum() - trust["sell"].sum())

        # 自營商
        dealer = latest[latest["name"].str.contains("自營商", na=False)]
        if not dealer.empty:
            result["dealer_net"] = int(dealer["buy"].sum() - dealer["sell"].sum())

        # 計算3日累計外資
        df["date"] = pd.to_datetime(df["date"])
        df_sorted = df.sort_values("date", ascending=False)
        dates_3d = df_sorted["date"].unique()[:3]
        foreign_3d = df[
            (df["date"].isin(dates_3d)) &
            (df["name"].str.contains("外陸資", na=False))
        ]
        if not foreign_3d.empty:
            result["foreign_3d"] = int(foreign_3d["buy"].sum() - foreign_3d["sell"].sum())

        return result

    except Exception as e:
        logger.warning(f"解析法人資料失敗: {e}")
        return {}
