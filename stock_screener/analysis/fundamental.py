"""
基本面分析模組
分析財務指標並給出基本面評分 (0-100)

指標包含:
- EPS 成長率
- 月營收年增率
- ROE 股東權益報酬率
- 本益比 (P/E Ratio)
- 股價淨值比 (P/B Ratio)
- 股息殖利率
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def analyze_fundamental(financial_data: Dict) -> Dict:
    """
    基本面評分

    Args:
        financial_data: 財務資料字典，包含:
            - eps: 每股盈餘
            - eps_growth: EPS 成長率 (小數，e.g. 0.2 = 20%)
            - revenue_growth: 營收年增率
            - roe: 股東權益報酬率
            - pe_ratio: 本益比
            - pb_ratio: 股價淨值比
            - dividend_yield: 股息殖利率

    Returns:
        Dict with score (0-100), signals, sub_scores
    """
    if not financial_data:
        return {"score": 50, "signals": ["⚠️ 基本面資料不足，給予中性評分"], "sub_scores": {}}

    result = {
        "score": 0,
        "signals": [],
        "sub_scores": {},
        "data": financial_data
    }

    score = 0
    signals = []
    sub_scores = {}

    # ========================
    # 1. EPS 成長率 (最高 25 分)
    # ========================
    eps_score = 0
    eps_growth = financial_data.get("eps_growth", None)

    if eps_growth is not None:
        if eps_growth >= 0.5:
            eps_score = 25
            signals.append(f"🚀 EPS 高速成長 (+{eps_growth*100:.0f}%)")
        elif eps_growth >= 0.3:
            eps_score = 20
            signals.append(f"📈 EPS 快速成長 (+{eps_growth*100:.0f}%)")
        elif eps_growth >= 0.15:
            eps_score = 15
            signals.append(f"✅ EPS 成長 (+{eps_growth*100:.0f}%)")
        elif eps_growth >= 0.05:
            eps_score = 10
        elif eps_growth >= 0:
            eps_score = 6
        elif eps_growth >= -0.15:
            eps_score = 3
            signals.append(f"⚠️ EPS 小幅衰退 ({eps_growth*100:.0f}%)")
        else:
            eps_score = 0
            signals.append(f"❌ EPS 大幅衰退 ({eps_growth*100:.0f}%)")
    else:
        eps_score = 10  # 無資料給中性分

    sub_scores["eps_growth"] = eps_score
    score += eps_score

    # ========================
    # 2. 月營收年增率 (最高 25 分)
    # ========================
    rev_score = 0
    rev_growth = financial_data.get("revenue_growth", None)

    if rev_growth is not None:
        if rev_growth >= 0.3:
            rev_score = 25
            signals.append(f"🚀 營收大幅成長 (+{rev_growth*100:.0f}%)")
        elif rev_growth >= 0.15:
            rev_score = 20
            signals.append(f"📈 營收成長 (+{rev_growth*100:.0f}%)")
        elif rev_growth >= 0.05:
            rev_score = 15
            signals.append(f"✅ 營收小幅成長 (+{rev_growth*100:.0f}%)")
        elif rev_growth >= 0:
            rev_score = 10
        elif rev_growth >= -0.1:
            rev_score = 5
            signals.append(f"⚠️ 營收微幅下滑 ({rev_growth*100:.0f}%)")
        else:
            rev_score = 0
            signals.append(f"❌ 營收衰退 ({rev_growth*100:.0f}%)")
    else:
        rev_score = 10  # 無資料給中性分

    sub_scores["revenue_growth"] = rev_score
    score += rev_score

    # ========================
    # 3. ROE 股東權益報酬率 (最高 25 分)
    # ========================
    roe_score = 0
    roe = financial_data.get("roe", None)

    if roe is not None:
        if roe >= 0.25:
            roe_score = 25
            signals.append(f"🌟 ROE 優秀 ({roe*100:.1f}%)")
        elif roe >= 0.15:
            roe_score = 20
            signals.append(f"✅ ROE 良好 ({roe*100:.1f}%)")
        elif roe >= 0.10:
            roe_score = 15
        elif roe >= 0.05:
            roe_score = 8
        elif roe >= 0:
            roe_score = 3
        else:
            roe_score = 0
            signals.append(f"❌ ROE 負值 ({roe*100:.1f}%)")
    else:
        roe_score = 10

    sub_scores["roe"] = roe_score
    score += roe_score

    # ========================
    # 4. 估值合理性 (最高 25 分)
    # ========================
    val_score = 0

    pe = financial_data.get("pe_ratio", None)
    pb = financial_data.get("pb_ratio", None)
    div_yield = financial_data.get("dividend_yield", 0)

    pe_score = 0
    pb_score = 0
    div_score = 0

    # 本益比評分
    if pe is not None and pe > 0:
        if pe <= 12:
            pe_score = 10
            signals.append(f"💰 低本益比 (PE={pe:.0f}x)")
        elif pe <= 20:
            pe_score = 8
        elif pe <= 30:
            pe_score = 5
        elif pe <= 40:
            pe_score = 3
        else:
            pe_score = 1
            signals.append(f"⚠️ 高本益比 (PE={pe:.0f}x)")
    else:
        pe_score = 5

    # 股價淨值比評分
    if pb is not None and pb > 0:
        if pb <= 1.0:
            pb_score = 8
            signals.append(f"💰 低股淨比 (PB={pb:.1f}x)")
        elif pb <= 2.0:
            pb_score = 6
        elif pb <= 4.0:
            pb_score = 4
        else:
            pb_score = 2

    # 股息殖利率評分
    if div_yield and div_yield > 0:
        if div_yield >= 0.05:
            div_score = 7
            signals.append(f"💎 高殖利率 ({div_yield*100:.1f}%)")
        elif div_yield >= 0.03:
            div_score = 5
        elif div_yield >= 0.01:
            div_score = 3

    val_score = min(pe_score + pb_score + div_score, 25)
    sub_scores["valuation"] = val_score
    score += val_score

    # ========================
    # 最終結果
    # ========================
    result["score"] = min(round(score), 100)
    result["signals"] = signals[:5]
    result["sub_scores"] = sub_scores

    return result


def parse_finmind_financials(df: pd.DataFrame) -> Dict:
    """
    解析 FinMind 財報資料為標準格式

    Args:
        df: FinMind TaiwanStockFinancialStatements DataFrame

    Returns:
        標準財務資料字典
    """
    if df is None or df.empty:
        return {}

    result = {}

    try:
        # EPS
        eps_rows = df[df["type"] == "EPS"]
        if not eps_rows.empty:
            eps_sorted = eps_rows.sort_values("date", ascending=False)
            if len(eps_sorted) >= 1:
                result["eps"] = eps_sorted.iloc[0]["value"]
            if len(eps_sorted) >= 5:
                current = eps_sorted.iloc[0]["value"]
                prev_year = eps_sorted.iloc[4]["value"]
                if prev_year and prev_year != 0:
                    result["eps_growth"] = (current - prev_year) / abs(prev_year)

        # ROE
        roe_rows = df[df["type"] == "ROE"]
        if not roe_rows.empty:
            result["roe"] = roe_rows.sort_values("date", ascending=False).iloc[0]["value"] / 100

    except Exception as e:
        logger.warning(f"解析財報失敗: {e}")

    return result


def parse_finmind_revenue(df: pd.DataFrame) -> Dict:
    """
    解析 FinMind 月營收資料

    Returns:
        包含 revenue_growth 的字典
    """
    if df is None or df.empty:
        return {}

    try:
        df = df.sort_values("date", ascending=False)
        if len(df) >= 13:
            current_rev = df.iloc[0]["revenue"]
            prev_year_rev = df.iloc[12]["revenue"]
            if prev_year_rev and prev_year_rev != 0:
                return {"revenue_growth": (current_rev - prev_year_rev) / abs(prev_year_rev)}
    except Exception as e:
        logger.warning(f"解析月營收失敗: {e}")

    return {}
