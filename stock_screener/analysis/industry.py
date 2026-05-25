"""
產業趨勢分析模組
分析類股強弱並給出產業評分 (0-100)

功能:
- 計算各產業平均漲跌幅
- 產業相對強弱排名
- 識別熱門輪動產業
- 個股相對所屬產業強弱
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# 台股主要產業分類 (股票代號前綴對應)
INDUSTRY_GROUPS = {
    "半導體": ["2330", "2303", "2308", "2379", "2454", "3711", "2344", "2449",
              "3034", "2338", "6770", "3443", "2404", "2408", "3533"],
    "電子零組件": ["2317", "2354", "2382", "3231", "2377", "2383", "3008",
                 "2357", "2353", "3706"],
    "AI/雲端/伺服器": ["3661", "6669", "4977", "3293", "2395"],
    "金融保險": ["2882", "2881", "2886", "2884", "2891", "2885",
               "2892", "2883", "5880", "2887", "2888"],
    "生技醫療": ["4711", "4715", "6547", "1730", "4726"],
    "航運": ["2603", "2609", "2615", "2610"],
    "鋼鐵": ["2002", "2006"],
    "建材營造": ["5534", "2395"],
    "食品飲料": ["1216", "1210", "1227", "1229"],
    "塑化": ["1301", "1303", "1326"],
    "電信": ["2412", "3045", "4904"],
    "電動車/汽車": ["2227", "1590", "1524"],
    "面板光電": ["2409", "3481", "2475", "2348"],
    "通路電商": ["2915", "2912", "9910"],
}


def calculate_industry_performance(
    price_data: Dict[str, pd.DataFrame],
    stock_industry_map: Dict[str, str],
    lookback_days: int = 20
) -> Dict[str, Dict]:
    """
    計算各產業的近期表現

    Args:
        price_data: {ticker: DataFrame} 的字典
        stock_industry_map: {stock_id: industry} 的字典
        lookback_days: 回溯天數

    Returns:
        {industry: {return, rank, stocks_count, ...}} 的字典
    """
    industry_returns = defaultdict(list)

    for ticker, df in price_data.items():
        if df is None or len(df) < lookback_days:
            continue

        # 從 ticker 取得股票代號 (e.g., "2330.TW" -> "2330")
        stock_id = ticker.split(".")[0]
        industry = stock_industry_map.get(stock_id, "其他")

        try:
            # 計算近期報酬率
            ret_20d = (df["close"].iloc[-1] / df["close"].iloc[-lookback_days] - 1)
            ret_5d = (df["close"].iloc[-1] / df["close"].iloc[-5] - 1) if len(df) >= 5 else 0
            ret_1d = (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) if len(df) >= 2 else 0

            industry_returns[industry].append({
                "stock_id": stock_id,
                "ret_1d": ret_1d,
                "ret_5d": ret_5d,
                "ret_20d": ret_20d,
            })
        except Exception as e:
            logger.debug(f"計算 {ticker} 產業報酬率失敗: {e}")

    # 彙整各產業統計
    industry_stats = {}
    for industry, stocks in industry_returns.items():
        if not stocks:
            continue

        avg_ret_1d = np.mean([s["ret_1d"] for s in stocks])
        avg_ret_5d = np.mean([s["ret_5d"] for s in stocks])
        avg_ret_20d = np.mean([s["ret_20d"] for s in stocks])

        industry_stats[industry] = {
            "avg_ret_1d": avg_ret_1d,
            "avg_ret_5d": avg_ret_5d,
            "avg_ret_20d": avg_ret_20d,
            "stocks_count": len(stocks),
            "stocks": [s["stock_id"] for s in stocks],
        }

    # 計算產業排名 (依20日報酬率)
    sorted_industries = sorted(
        industry_stats.keys(),
        key=lambda x: industry_stats[x]["avg_ret_20d"],
        reverse=True
    )

    for rank, industry in enumerate(sorted_industries, 1):
        industry_stats[industry]["rank"] = rank
        industry_stats[industry]["total_industries"] = len(sorted_industries)

    logger.info(f"分析了 {len(industry_stats)} 個產業")
    return industry_stats


def get_industry_score(
    stock_id: str,
    industry: str,
    industry_stats: Dict[str, Dict],
    stock_ret_20d: float = 0
) -> Dict:
    """
    計算個股的產業評分

    Args:
        stock_id: 股票代號
        industry: 所屬產業
        industry_stats: 產業統計資料
        stock_ret_20d: 個股20日報酬率

    Returns:
        Dict with score (0-100), signals, industry_data
    """
    result = {
        "score": 50,
        "signals": [],
        "industry": industry,
        "industry_data": {}
    }

    if not industry_stats or industry not in industry_stats:
        return result

    ind_data = industry_stats[industry]
    rank = ind_data.get("rank", 999)
    total = ind_data.get("total_industries", 1)
    avg_ret_20d = ind_data.get("avg_ret_20d", 0)
    avg_ret_5d = ind_data.get("avg_ret_5d", 0)

    score = 0
    signals = []

    # ========================
    # 1. 產業排名評分 (最高 50 分)
    # ========================
    rank_pct = 1 - (rank - 1) / max(total - 1, 1)  # 1=最強, 0=最弱

    if rank_pct >= 0.85:
        score += 50
        signals.append(f"🏆 強勢產業前段班 (#{rank}/{total})")
    elif rank_pct >= 0.70:
        score += 40
        signals.append(f"✅ 產業表現強勢 (#{rank}/{total})")
    elif rank_pct >= 0.55:
        score += 30
    elif rank_pct >= 0.40:
        score += 20
    elif rank_pct >= 0.25:
        score += 10
        signals.append(f"⚠️ 產業偏弱 (#{rank}/{total})")
    else:
        score += 0
        signals.append(f"❌ 產業強度末段 (#{rank}/{total})")

    # ========================
    # 2. 產業近期動能 (最高 30 分)
    # ========================
    if avg_ret_5d >= 0.05:
        score += 30
        signals.append(f"🚀 產業5日強勢 (+{avg_ret_5d*100:.1f}%)")
    elif avg_ret_5d >= 0.02:
        score += 20
    elif avg_ret_5d >= 0:
        score += 12
    elif avg_ret_5d >= -0.02:
        score += 6
    else:
        score += 0
        signals.append(f"📉 產業近期弱勢 ({avg_ret_5d*100:.1f}%)")

    # ========================
    # 3. 個股相對產業表現 (最高 20 分)
    # ========================
    if avg_ret_20d != 0:
        relative = stock_ret_20d - avg_ret_20d
        if relative >= 0.05:
            score += 20
            signals.append(f"⭐ 個股優於產業 (+{relative*100:.1f}%)")
        elif relative >= 0.02:
            score += 15
        elif relative >= 0:
            score += 10
        elif relative >= -0.03:
            score += 5
        else:
            score += 0
            signals.append(f"⚠️ 個股弱於產業 ({relative*100:.1f}%)")

    result["score"] = min(round(score), 100)
    result["signals"] = signals[:4]
    result["industry_data"] = {
        "rank": rank,
        "total": total,
        "avg_ret_1d": round(ind_data.get("avg_ret_1d", 0) * 100, 2),
        "avg_ret_5d": round(avg_ret_5d * 100, 2),
        "avg_ret_20d": round(avg_ret_20d * 100, 2),
    }

    return result


def get_hot_industries(
    industry_stats: Dict[str, Dict],
    top_n: int = 5
) -> List[Dict]:
    """
    取得熱門產業排行

    Returns:
        List of {industry, rank, avg_ret_5d, avg_ret_20d, ...}
    """
    if not industry_stats:
        return []

    industries = []
    for name, data in industry_stats.items():
        industries.append({
            "industry": name,
            "rank": data.get("rank", 999),
            "avg_ret_1d": round(data.get("avg_ret_1d", 0) * 100, 2),
            "avg_ret_5d": round(data.get("avg_ret_5d", 0) * 100, 2),
            "avg_ret_20d": round(data.get("avg_ret_20d", 0) * 100, 2),
            "stocks_count": data.get("stocks_count", 0),
        })

    # 按5日報酬率排序
    industries.sort(key=lambda x: x["avg_ret_5d"], reverse=True)
    return industries[:top_n]


def identify_rotation_opportunities(
    industry_stats: Dict[str, Dict]
) -> List[str]:
    """
    識別產業輪動機會

    Returns:
        輪動訊號清單
    """
    signals = []

    if not industry_stats:
        return signals

    for industry, data in industry_stats.items():
        rank = data.get("rank", 999)
        total = data.get("total_industries", 1)
        ret_5d = data.get("avg_ret_5d", 0)
        ret_20d = data.get("avg_ret_20d", 0)

        # 短期強勢但中期落後 -> 輪動初期
        if ret_5d >= 0.03 and ret_20d < 0:
            signals.append(f"🔄 {industry} 輪動跡象：近5日翻紅但中期仍弱")

        # 產業持續強勢
        if rank <= 3 and ret_5d >= 0.02:
            signals.append(f"🔥 {industry} 持續領漲市場")

    return signals[:5]
