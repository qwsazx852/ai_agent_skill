"""
主題概念股分析模組
以「產業故事」取代傳統產業分類，捕捉有話題有動能的概念股

主題設計原則：
- 以市場正在討論的「敘事」為主
- 每個主題涵蓋上中下游廠商
- 一支股票可以屬於多個主題
- 主題隨時事動態可擴充
"""

from typing import Dict, List, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 主題定義
# 格式: theme_id -> {name, emoji, description, stocks}
# ============================================================
THEMES: Dict[str, Dict] = {

    # ── AI / 伺服器供應鏈 ──────────────────────────────────────
    "ai_server": {
        "name": "AI伺服器",
        "emoji": "🤖",
        "description": "AI伺服器整機組裝、機櫃、電源供應",
        "stocks": ["2382", "3231", "2356", "2324", "6669", "3661", "4977", "2301",
                   "2395", "3293", "6770"],
    },
    "thermal": {
        "name": "AI散熱",
        "emoji": "🌡️",
        "description": "液冷散熱、熱管、風扇、散熱模組",
        "stocks": ["3324", "3017", "2421", "6230", "3483", "1490", "2424", "3014",
                   "6515", "8213"],
    },
    "cowos": {
        "name": "CoWoS先進封裝",
        "emoji": "⚡",
        "description": "台積電CoWoS、SoIC先進封裝供應鏈",
        "stocks": ["2330", "3711", "2325", "6239", "2404", "3014", "6533", "2449",
                   "3443", "6643"],
    },
    "hbm": {
        "name": "HBM記憶體",
        "emoji": "💾",
        "description": "高頻寬記憶體、AI DRAM、記憶體模組",
        "stocks": ["2408", "2344", "5346", "4967", "3260", "2603"],
    },

    # ── 半導體設備/材料 ────────────────────────────────────────
    "semi_equip": {
        "name": "半導體設備材料",
        "emoji": "🔬",
        "description": "晶圓設備、化學品、研磨液、光罩",
        "stocks": ["3558", "5351", "6533", "2358", "2404", "3491", "6438", "4552",
                   "6239", "3014"],
    },
    "passive": {
        "name": "被動元件",
        "emoji": "🔩",
        "description": "MLCC、電阻、電感、電容",
        "stocks": ["2327", "2492", "3026", "2456", "2320", "2492", "1723"],
    },

    # ── PCB / 基板 ────────────────────────────────────────────
    "pcb": {
        "name": "高階PCB/基板",
        "emoji": "📋",
        "description": "AI伺服器高層板、ABF載板、HDI",
        "stocks": ["4958", "3037", "8046", "2383", "2365", "6269", "3189", "6768"],
    },

    # ── 電源管理 / 電網 ───────────────────────────────────────
    "power": {
        "name": "電源管理/電網",
        "emoji": "⚡",
        "description": "伺服器電源、UPS、電網建設",
        "stocks": ["2308", "2301", "6669", "3005", "1504", "1503", "1513", "2441",
                   "6285", "3576"],
    },

    # ── AI PC / 終端裝置 ──────────────────────────────────────
    "ai_pc": {
        "name": "AI PC/終端",
        "emoji": "💻",
        "description": "AI PC、筆電、平板、邊緣AI裝置",
        "stocks": ["2353", "2357", "2377", "3008", "2354", "2382", "4938", "2324"],
    },

    # ── 網通 / 資料中心互連 ───────────────────────────────────
    "network": {
        "name": "高速網通",
        "emoji": "🌐",
        "description": "高速交換器、光收發器、網路設備",
        "stocks": ["2498", "3044", "4977", "6223", "3515", "5478", "3051"],
    },

    # ── 電動車 / 新能源 ───────────────────────────────────────
    "ev": {
        "name": "電動車供應鏈",
        "emoji": "🚗",
        "description": "EV零組件、充電樁、電池管理",
        "stocks": ["2227", "1524", "1590", "3665", "6279", "1537", "2393", "3563",
                   "1702", "6230"],
    },
    "green_energy": {
        "name": "綠能/儲能",
        "emoji": "☀️",
        "description": "太陽能、風電、儲能系統",
        "stocks": ["3576", "6244", "3703", "2109", "1560", "3622", "6409"],
    },

    # ── 航運 / 循環股 ─────────────────────────────────────────
    "shipping": {
        "name": "航運循環",
        "emoji": "🚢",
        "description": "貨櫃航運、散裝、航空貨運",
        "stocks": ["2603", "2609", "2615", "2610", "2618", "2601", "5608"],
    },

    # ── 金融科技 / 數位金融 ───────────────────────────────────
    "fintech": {
        "name": "金融/數位金融",
        "emoji": "🏦",
        "description": "數位銀行、電支、資產管理",
        "stocks": ["2882", "2881", "2884", "2886", "2891", "5880", "2892", "2885"],
    },

    # ── 生技醫療 ──────────────────────────────────────────────
    "biotech": {
        "name": "生技醫療",
        "emoji": "💊",
        "description": "新藥、醫材、CRO、健康科技",
        "stocks": ["4711", "4715", "6547", "1730", "4726", "4174", "6197", "1799",
                   "4162", "4160"],
    },

    # ── 國防/軍工 ─────────────────────────────────────────────
    "defense": {
        "name": "國防軍工",
        "emoji": "🛡️",
        "description": "無人機、雷達、軍事電子",
        "stocks": ["2313", "2634", "1569", "3001", "2208"],
    },

    # ── 機器人 / 自動化 ───────────────────────────────────────
    "robot": {
        "name": "機器人/自動化",
        "emoji": "🦾",
        "description": "工業機器人、精密減速機、視覺系統",
        "stocks": ["1590", "2049", "2049", "1536", "4562", "6509", "3563"],
    },
}


def get_stock_themes(stock_id: str) -> List[str]:
    """
    查詢某支股票屬於哪些主題

    Returns:
        List of theme_ids
    """
    result = []
    for theme_id, theme_data in THEMES.items():
        if stock_id in theme_data.get("stocks", []):
            result.append(theme_id)
    return result


def get_theme_display_name(theme_id: str) -> str:
    """取得主題顯示名稱（含 emoji）"""
    theme = THEMES.get(theme_id, {})
    return f"{theme.get('emoji', '')} {theme.get('name', theme_id)}"


def analyze_themes(
    price_data: Dict[str, pd.DataFrame],
    stock_ticker_map: Dict[str, str],  # stock_id -> yf_ticker
    all_stock_results: List[Dict],
) -> Dict:
    """
    計算各主題的績效與熱度

    Args:
        price_data: {ticker: DataFrame}
        stock_ticker_map: {stock_id: ticker}
        all_stock_results: 所有個股分析結果列表

    Returns:
        {
          "hot_themes": [...],       # 依熱度排序的主題列表
          "stock_themes": {...},     # {stock_id: [theme_ids]}
          "theme_stats": {...},      # {theme_id: stats}
        }
    """
    # 建立 stock_id -> themes 對應
    stock_theme_map: Dict[str, List[str]] = {}
    for stock_result in all_stock_results:
        sid = stock_result.get("stock_id", "")
        themes = get_stock_themes(sid)
        if themes:
            stock_theme_map[sid] = themes

    # 計算每個主題的績效
    theme_stats: Dict[str, Dict] = {}

    for theme_id, theme_data in THEMES.items():
        theme_stocks = theme_data.get("stocks", [])
        rets_1d = []
        rets_5d = []
        avg_score = []
        active_stocks = []  # 有資料的股票

        for sid in theme_stocks:
            ticker = stock_ticker_map.get(sid)
            if ticker and ticker in price_data:
                df = price_data[ticker]
                if df is not None and len(df) >= 6:
                    try:
                        closes = df["close"].values
                        ret_1d = (closes[-1] / closes[-2] - 1) * 100 if len(closes) >= 2 else 0
                        ret_5d = (closes[-1] / closes[-6] - 1) * 100 if len(closes) >= 6 else 0
                        rets_1d.append(ret_1d)
                        rets_5d.append(ret_5d)
                        active_stocks.append(sid)
                    except Exception:
                        pass

            # 取得綜合評分
            for res in all_stock_results:
                if res.get("stock_id") == sid:
                    avg_score.append(res.get("composite_score", 0))
                    break

        if not rets_5d:
            continue  # 主題內無有效股票，跳過

        theme_avg_ret_5d = sum(rets_5d) / len(rets_5d)
        theme_avg_ret_1d = sum(rets_1d) / len(rets_1d) if rets_1d else 0
        theme_avg_score = sum(avg_score) / len(avg_score) if avg_score else 0

        # 熱度分數：結合5日漲幅 + 平均評分
        heat_score = theme_avg_ret_5d * 0.6 + (theme_avg_score / 100 * 10) * 0.4

        theme_stats[theme_id] = {
            "theme_id": theme_id,
            "name": theme_data["name"],
            "emoji": theme_data.get("emoji", ""),
            "description": theme_data.get("description", ""),
            "avg_ret_1d": round(theme_avg_ret_1d, 2),
            "avg_ret_5d": round(theme_avg_ret_5d, 2),
            "avg_score": round(theme_avg_score, 1),
            "heat_score": round(heat_score, 2),
            "active_count": len(active_stocks),
            "active_stocks": active_stocks[:5],  # 最多列5支
        }

    # 依熱度排序
    hot_themes = sorted(
        theme_stats.values(),
        key=lambda x: x["heat_score"],
        reverse=True
    )

    return {
        "hot_themes": hot_themes[:8],   # 回傳前8個熱門主題
        "stock_themes": stock_theme_map,
        "theme_stats": theme_stats,
    }


def get_theme_score_for_stock(stock_id: str, theme_stats: Dict) -> int:
    """
    根據股票所屬主題的熱度，給予產業面加分（0-100）

    屬於越熱門的主題 → 越高分
    """
    themes = get_stock_themes(stock_id)
    if not themes:
        return 50  # 不屬於任何主題，中性分

    scores = []
    for theme_id in themes:
        stat = theme_stats.get(theme_id)
        if stat:
            # 依熱度分數轉換為 0-100 分
            heat = stat.get("heat_score", 0)
            # heat_score 約 -5 到 +15，轉為 0-100
            converted = min(100, max(0, 50 + heat * 3))
            scores.append(converted)

    return round(max(scores)) if scores else 50
