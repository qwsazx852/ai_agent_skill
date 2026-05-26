"""
籌碼面分析模組
分析三大法人買賣超、融資融券並給出籌碼評分 (0-100)

指標包含:
- 外資買賣超 (當日 + 近期累計)
- 投信買賣超
- 自營商買賣超
- 融資增減
- 融券增減
- 大戶持股分散表分析
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def parse_finmind_margin(df: pd.DataFrame) -> Dict:
    """
    解析 FinMind 融資融券資料 (TaiwanStockMarginPurchaseShortSale)

    Returns:
        {
          margin_balance: 融資餘額（今日）
          margin_change:  融資增減（今日 vs 昨日）
          margin_5d_change: 融資5日淨變化（正=增加=風險，負=減少=乾淨）
          short_balance:  融券餘額（今日）
          short_change:   融券增減
          margin_ratio:   融資使用率（現值/前高）
        }
    """
    result = {}
    if df is None or df.empty:
        return result
    try:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date", ascending=False)

        # 欄位對應：FinMind MarginPurchaseShortSale
        col_map = {
            "MarginPurchaseToday": "margin_balance",
            "ShortSaleToday": "short_balance",
            "MarginPurchaseBuy": "margin_buy",
            "MarginPurchaseSell": "margin_sell",
            "ShortSaleBuy": "short_buy",
            "ShortSaleSell": "short_sell",
        }
        for src, dst in col_map.items():
            if src in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce").fillna(0)

        if "margin_balance" in df.columns and len(df) >= 1:
            result["margin_balance"] = int(df["margin_balance"].iloc[0])
        if "short_balance" in df.columns and len(df) >= 1:
            result["short_balance"] = int(df["short_balance"].iloc[0])

        # 今日融資增減
        if "margin_buy" in df.columns and "margin_sell" in df.columns and len(df) >= 1:
            result["margin_change"] = int(df["margin_buy"].iloc[0] - df["margin_sell"].iloc[0])

        # 近5日融資淨變化
        if "margin_balance" in df.columns and len(df) >= 5:
            result["margin_5d_change"] = int(df["margin_balance"].iloc[0] - df["margin_balance"].iloc[4])

        # 融資使用率：現值相對近20日最高點
        if "margin_balance" in df.columns and len(df) >= 5:
            recent_max = df["margin_balance"].head(20).max()
            if recent_max > 0:
                result["margin_ratio"] = round(df["margin_balance"].iloc[0] / recent_max, 3)

    except Exception as e:
        logger.warning(f"解析融資融券失敗: {e}")
    return result


def analyze_shareholding(df: Optional[pd.DataFrame]) -> Dict:
    """
    分析集保大戶持股分散表，計算持有超過 400張、1000張、2000張 的大戶持股比例變化

    Args:
        df: FinMind TaiwanStockHoldingSharesPer DataFrame（最近兩期）

    Returns:
        Dict with score (0-30), signals, and detail data
    """
    result = {
        "score": 15,  # 預設中性分數
        "signals": [],
        "data": {}
    }

    if df is None or df.empty:
        result["signals"].append("⚠️ 大戶持股資料不足，給予中性評分")
        return result

    try:
        # 確認欄位存在
        required_cols = {"date", "HoldingSharesLevel", "percent"}
        if not required_cols.issubset(set(df.columns)):
            # 嘗試常見替代欄位名稱
            col_aliases = {
                "HoldingSharesLevel": ["holding_shares_level", "level"],
                "percent": ["percent", "Percent", "ratio"],
            }
            for col, aliases in col_aliases.items():
                if col not in df.columns:
                    for alias in aliases:
                        if alias in df.columns:
                            df = df.rename(columns={alias: col})
                            break

        if "HoldingSharesLevel" not in df.columns or "percent" not in df.columns:
            result["signals"].append("⚠️ 大戶持股欄位格式不符，跳過分析")
            return result

        # 大戶門檻定義 (張數)
        whale_levels_keywords = {
            "400張以上": ["400", "400-", "400~"],
            "1000張以上": ["1000", "1,000"],
            "2000張以上": ["2000", "2,000"],
        }

        df["percent"] = pd.to_numeric(df["percent"], errors="coerce").fillna(0)
        df["date"] = pd.to_datetime(df["date"])

        sorted_dates = sorted(df["date"].unique(), reverse=True)
        if len(sorted_dates) < 2:
            result["signals"].append("⚠️ 大戶持股期數不足（需至少兩期）")
            return result

        latest_date = sorted_dates[0]
        prev_date = sorted_dates[1]

        latest_df = df[df["date"] == latest_date]
        prev_df = df[df["date"] == prev_date]

        # 計算大戶 (持有超過 400 張以上) 的總持股比例
        def _sum_whale_pct(sub_df: pd.DataFrame, min_lots: int) -> float:
            """加總持有超過 min_lots 張以上的持股比例"""
            total = 0.0
            for _, row in sub_df.iterrows():
                level_str = str(row.get("HoldingSharesLevel", ""))
                # 簡單判斷：取 level 中的數字，看是否 >= min_lots
                import re
                nums = re.findall(r"[\d,]+", level_str.replace(",", ""))
                for n in nums:
                    try:
                        if int(n) >= min_lots:
                            total += float(row["percent"])
                            break
                    except ValueError:
                        pass
            return total

        score = 0
        signals: List[str] = []
        data: Dict = {}

        for label, min_lots in [("400張", 400), ("1000張", 1000), ("2000張", 2000)]:
            latest_pct = _sum_whale_pct(latest_df, min_lots)
            prev_pct = _sum_whale_pct(prev_df, min_lots)
            change = latest_pct - prev_pct

            data[f"whale_{label}_latest"] = round(latest_pct, 2)
            data[f"whale_{label}_prev"] = round(prev_pct, 2)
            data[f"whale_{label}_change"] = round(change, 2)

            # 評分邏輯
            if change > 1.0:
                score += 10
                signals.append(f"🐋 大戶({label})增加 +{change:.1f}%（正面）")
            elif change > 0.3:
                score += 6
                signals.append(f"✅ 大戶({label})小幅增加 +{change:.1f}%")
            elif change < -1.0:
                score -= 8
                signals.append(f"⚠️ 大戶({label})減少 {change:.1f}%（負面）")
            elif change < -0.3:
                score -= 4
            else:
                score += 3  # 持平，給予些微正分

        # 限制分數範圍 0-30
        final_score = max(0, min(30, score + 15))  # 中心點 15

        result["score"] = final_score
        result["signals"] = signals[:4]
        result["data"] = data

    except Exception as e:
        logger.warning(f"大戶持股分析失敗: {e}")
        result["signals"].append("⚠️ 大戶持股分析異常，給予中性評分")

    return result


def analyze_institutional(inst_data: Dict, shareholding_score: int = 0) -> Dict:
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
    trust_3d = inst_data.get("trust_3d", 0) or 0

    if trust_net > 2000:
        trust_score = 28
        signals.append(f"🏦 投信大買 (+{trust_net:,}張)")
    elif trust_net > 500:
        trust_score = 20
        signals.append(f"✅ 投信買超 (+{trust_net:,}張)")
    elif trust_net > 100:
        trust_score = 14
    elif trust_net > 0:
        trust_score = 9
    elif trust_net > -500:
        trust_score = 6
    else:
        trust_score = 0
        signals.append(f"⚠️ 投信賣超 ({trust_net:,}張)")

    # 投信3日累計加分：連續買才有意義
    if trust_3d > 3000:
        trust_score = min(trust_score + 7, 35)
        signals.append(f"🔥 投信3日持續買超 (+{trust_3d:,}張)")
    elif trust_3d > 1000:
        trust_score = min(trust_score + 4, 35)

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
    # 4. 融資融券分析 (加減分，最大 ±10)
    # ========================
    margin_change = inst_data.get("margin_change", 0) or 0
    margin_5d_change = inst_data.get("margin_5d_change", 0) or 0
    margin_ratio = inst_data.get("margin_ratio", 0.5) or 0.5
    short_balance = inst_data.get("short_balance", 0) or 0
    margin_balance = inst_data.get("margin_balance", 0) or 0

    margin_adjust = 0

    # 融資5日趨勢（比單日更可靠）
    if margin_5d_change < -3000:
        margin_adjust += 5   # 融資持續減少 = 籌碼乾淨，健康
        signals.append(f"✅ 融資5日淨減 {margin_5d_change:,}張（籌碼乾淨）")
    elif margin_5d_change < 0:
        margin_adjust += 2
    elif margin_5d_change > 5000:
        margin_adjust -= 6   # 散戶融資大量湧入 = 風險
        signals.append(f"⚠️ 融資5日大增 +{margin_5d_change:,}張（散戶追高風險）")
    elif margin_5d_change > 2000:
        margin_adjust -= 3

    # 融資使用率（相對近期高點）
    if margin_ratio >= 0.95:
        margin_adjust -= 4   # 融資接近歷史高點，賣壓沉重
        signals.append(f"⚠️ 融資使用率高（{margin_ratio:.0%}，賣壓風險）")
    elif margin_ratio <= 0.5:
        margin_adjust += 3   # 融資低位，有增長空間

    # 融券多代表市場看空，若股價仍強 = 軋空潛力
    if short_balance > 5000:
        margin_adjust += 3
        signals.append(f"💡 融券多 ({short_balance:,}張，潛在軋空)")
    elif short_balance > 2000:
        margin_adjust += 1

    margin_adjust = max(-10, min(10, margin_adjust))
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

        # 計算累計外資（3日、10日）與累計投信（3日）
        df["date"] = pd.to_datetime(df["date"])
        df_sorted = df.sort_values("date", ascending=False)
        all_dates = df_sorted["date"].unique()

        # 外資 3日累計
        dates_3d = all_dates[:3]
        foreign_3d_df = df[
            (df["date"].isin(dates_3d)) &
            (df["name"].str.contains("外陸資", na=False))
        ]
        if not foreign_3d_df.empty:
            result["foreign_3d"] = int(foreign_3d_df["buy"].sum() - foreign_3d_df["sell"].sum())

        # 外資 10日累計
        dates_10d = all_dates[:10]
        foreign_10d_df = df[
            (df["date"].isin(dates_10d)) &
            (df["name"].str.contains("外陸資", na=False))
        ]
        if not foreign_10d_df.empty:
            result["foreign_10d"] = int(foreign_10d_df["buy"].sum() - foreign_10d_df["sell"].sum())

        # 投信 3日累計
        trust_3d_df = df[
            (df["date"].isin(dates_3d)) &
            (df["name"] == "投信")
        ]
        if not trust_3d_df.empty:
            result["trust_3d"] = int(trust_3d_df["buy"].sum() - trust_3d_df["sell"].sum())

        return result

    except Exception as e:
        logger.warning(f"解析法人資料失敗: {e}")
        return {}
