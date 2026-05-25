"""
月營收分析模組
每月10日抓取 FinMind TaiwanStockMonthRevenue
分析 YoY、MoM 成長，找出營收亮眼的股票

評分標準：
- YoY > 50%：超強成長
- YoY 20-50%：強勁成長
- 連續3個月正成長：趨勢向上
- 創近12月新高：突破性成長
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)


def analyze_monthly_revenue(
    stock_id: str,
    df: pd.DataFrame,
) -> Dict:
    """
    分析單一股票月營收

    Args:
        stock_id: 股票代號
        df: FinMind TaiwanStockMonthRevenue DataFrame

    Returns:
        Dict with score, signals, key metrics
    """
    result = {
        "stock_id": stock_id,
        "score": 0,
        "signals": [],
        "yoy": None,
        "mom": None,
        "latest_revenue": None,
        "consecutive_growth": 0,
        "is_new_high_12m": False,
    }

    if df is None or df.empty:
        return result

    try:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date", ascending=False)

        # 取出營收欄位（FinMind 欄位名稱）
        rev_col = None
        for col in ["revenue", "Revenue", "totalRevenue", "total_revenue"]:
            if col in df.columns:
                rev_col = col
                break
        if rev_col is None:
            return result

        df[rev_col] = pd.to_numeric(df[rev_col], errors="coerce").fillna(0)
        df = df[df[rev_col] > 0]

        if len(df) < 2:
            return result

        latest = df.iloc[0]
        latest_rev = float(latest[rev_col])
        result["latest_revenue"] = latest_rev
        result["latest_date"] = str(latest["date"])[:7]  # YYYY-MM

        score = 0
        signals = []

        # ── MoM 月增率 ─────────────────────────────────────────
        if len(df) >= 2:
            prev_rev = float(df.iloc[1][rev_col])
            if prev_rev > 0:
                mom = (latest_rev / prev_rev - 1) * 100
                result["mom"] = round(mom, 2)
                if mom > 20:
                    score += 15
                    signals.append(f"📈 月增率 +{mom:.1f}%（月月成長顯著）")
                elif mom > 10:
                    score += 10
                    signals.append(f"✅ 月增率 +{mom:.1f}%")
                elif mom > 0:
                    score += 5
                elif mom < -20:
                    score -= 10
                    signals.append(f"⚠️ 月減率 {mom:.1f}%（月衰退明顯）")

        # ── YoY 年增率 ─────────────────────────────────────────
        # 找12個月前的資料
        latest_date = latest["date"]
        year_ago = latest_date - pd.DateOffset(months=12)
        year_ago_data = df[df["date"].dt.to_period("M") == year_ago.to_period("M")]

        if not year_ago_data.empty:
            year_ago_rev = float(year_ago_data.iloc[0][rev_col])
            if year_ago_rev > 0:
                yoy = (latest_rev / year_ago_rev - 1) * 100
                result["yoy"] = round(yoy, 2)
                if yoy > 50:
                    score += 30
                    signals.append(f"🚀 年增率 +{yoy:.1f}%（爆發性成長）")
                elif yoy > 30:
                    score += 25
                    signals.append(f"🔥 年增率 +{yoy:.1f}%（強勁成長）")
                elif yoy > 15:
                    score += 18
                    signals.append(f"✅ 年增率 +{yoy:.1f}%")
                elif yoy > 0:
                    score += 10
                elif yoy < -20:
                    score -= 15
                    signals.append(f"⚠️ 年衰退 {yoy:.1f}%")

        # ── 連續月增率正成長 ────────────────────────────────────
        consecutive = 0
        for i in range(min(6, len(df) - 1)):
            cur = float(df.iloc[i][rev_col])
            prev = float(df.iloc[i + 1][rev_col])
            if prev > 0 and cur > prev:
                consecutive += 1
            else:
                break
        result["consecutive_growth"] = consecutive
        if consecutive >= 4:
            score += 20
            signals.append(f"📊 連續 {consecutive} 個月成長（趨勢強勁）")
        elif consecutive >= 2:
            score += 10
            signals.append(f"✅ 連續 {consecutive} 個月成長")

        # ── 近12月新高 ─────────────────────────────────────────
        recent_12m = df.head(12)[rev_col]
        if len(recent_12m) >= 3 and latest_rev >= recent_12m.max():
            result["is_new_high_12m"] = True
            score += 25
            signals.append(f"🏆 創近12個月營收新高！")

        result["score"] = min(100, max(0, score))
        result["signals"] = signals[:4]

    except Exception as e:
        logger.warning(f"月營收分析失敗 {stock_id}: {e}")

    return result


def screen_revenue_stocks(
    stock_list: List[Dict],
    finmind_token: str,
    top_n: int = 20,
) -> List[Dict]:
    """
    批次分析多檔股票月營收，回傳成長最佳的前 N 名

    Args:
        stock_list: [{"stock_id": "2330", "stock_name": "台積電", ...}, ...]
        finmind_token: FinMind API token
        top_n: 回傳前 N 名

    Returns:
        排序後的月營收分析結果
    """
    from ..data.fetcher import fetch_finmind_revenue
    import time

    results = []
    total = len(stock_list)

    for i, stock in enumerate(stock_list):
        stock_id = stock.get("stock_id", "")
        stock_name = stock.get("stock_name", stock_id)

        if i % 20 == 0:
            logger.info(f"  月營收分析進度: {i}/{total}")

        try:
            df = fetch_finmind_revenue(stock_id, finmind_token)
            if df is not None and not df.empty:
                result = analyze_monthly_revenue(stock_id, df)
                result["stock_name"] = stock_name
                result["industry"] = stock.get("industry", "")
                if result["score"] > 0:
                    results.append(result)
            time.sleep(0.15)  # 避免 API 限速
        except Exception as e:
            logger.debug(f"跳過 {stock_id}: {e}")

    # 依分數排序
    results.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"月營收分析完成: {len(results)} 檔有資料，取前 {top_n} 名")
    return results[:top_n]


def format_revenue_telegram_message(
    results: List[Dict],
    date: str = "",
) -> List[str]:
    """
    產生月營收 Telegram 訊息（可能超過一則）

    Returns:
        List of message strings
    """
    if not date:
        date = datetime.now().strftime("%Y-%m")

    messages = []

    # 訊息一：總覽
    msg1 = (
        f"📊 *月營收亮眼股票篩選*\n"
        f"📅 {date} 月營收報告\n"
        f"{'─' * 28}\n\n"
    )

    if not results:
        msg1 += "⚠️ 本月暫無顯著成長股票"
        return [msg1]

    # 先列出爆發性成長（YoY > 30%）
    stars = [r for r in results if r.get("yoy") and r["yoy"] > 30]
    if stars:
        msg1 += "🚀 *爆發性成長（年增>30%）*\n"
        for r in stars[:5]:
            yoy = r.get("yoy", 0)
            mom = r.get("mom", 0)
            new_high = "🏆新高 " if r.get("is_new_high_12m") else ""
            msg1 += (
                f"• `{r['stock_id']}` {r.get('stock_name','')} "
                f"{new_high}YoY+{yoy:.0f}% MoM{'+' if mom>=0 else ''}{mom:.0f}%\n"
            )

    # 連續成長股
    consecutive = [r for r in results if r.get("consecutive_growth", 0) >= 3
                   and r not in stars]
    if consecutive:
        msg1 += "\n📈 *連續成長（3個月以上）*\n"
        for r in consecutive[:5]:
            c = r.get("consecutive_growth", 0)
            yoy = r.get("yoy", 0) or 0
            msg1 += (
                f"• `{r['stock_id']}` {r.get('stock_name','')} "
                f"連{c}月↑ YoY{'+' if yoy>=0 else ''}{yoy:.0f}%\n"
            )

    messages.append(msg1)

    # 訊息二：詳細列表 TOP 15
    if len(results) > 0:
        msg2 = f"📋 *月營收 TOP{min(15, len(results))} 詳細*\n{'─' * 28}\n"
        for i, r in enumerate(results[:15], 1):
            yoy = r.get("yoy")
            mom = r.get("mom")
            score = r.get("score", 0)
            new_high = "🏆" if r.get("is_new_high_12m") else ""
            cons = r.get("consecutive_growth", 0)

            yoy_str = f"YoY{'+' if yoy and yoy>=0 else ''}{yoy:.0f}%" if yoy is not None else "YoY—"
            mom_str = f"MoM{'+' if mom and mom>=0 else ''}{mom:.0f}%" if mom is not None else ""
            cons_str = f"連{cons}月↑" if cons >= 2 else ""

            msg2 += (
                f"{new_high}`{i:>2}.{r['stock_id']}` {r.get('stock_name','')[:5]}"
                f" {score:.0f}分 {yoy_str} {mom_str} {cons_str}\n"
            )
        msg2 += f"\n_⚠️ 本報告僅供參考，不構成投資建議_"
        messages.append(msg2)

    return messages
