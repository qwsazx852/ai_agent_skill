"""
Streamlit Dashboard - 台灣股市每日篩選系統
雲端部署，支援 iPad 瀏覽器存取

功能:
- 每日篩選結果排行榜
- 個股詳細分析頁
- 產業趨勢地圖
- 歷史篩選記錄
- 自訂篩選條件
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd

# ─── 頁面設定 ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🇹🇼 台股每日篩選系統",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/qwsazx852/ai_agent_skill",
        "About": "台灣股市每日篩選系統 - 技術/基本/籌碼/產業綜合評分",
    }
)

# ─── 樣式設定 ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* 主色調 */
    .main-header {
        background: linear-gradient(90deg, #1a1a2e, #16213e, #0f3460);
        color: white;
        padding: 20px 30px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .metric-card {
        background: #1e2130;
        border: 1px solid #2d3561;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }
    /* 評級顏色 */
    .grade-a-plus { color: #FFD700; font-weight: bold; font-size: 1.2em; }
    .grade-a { color: #FFA500; font-weight: bold; }
    .grade-b-plus { color: #00CED1; font-weight: bold; }
    .grade-b { color: #32CD32; }
    .grade-c { color: #808080; }
    .grade-d { color: #FF4444; }
    /* 表格樣式 */
    .stDataFrame { font-size: 0.9em; }
    /* iPad 響應式 */
    @media (max-width: 1024px) {
        .main-header { padding: 15px; }
    }
</style>
""", unsafe_allow_html=True)


# ─── 工具函數 ─────────────────────────────────────────────────────────────────

def load_results() -> Optional[Dict]:
    """載入最新篩選結果"""
    results_file = "results/latest_screening.json"
    if os.path.exists(results_file):
        try:
            with open(results_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"載入結果失敗: {e}")
    return None


def load_history() -> List[Dict]:
    """載入歷史記錄"""
    history_file = "results/screening_history.json"
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_grade_color(grade: str) -> str:
    """評級對應顏色"""
    colors = {
        "A+": "#FFD700",
        "A": "#FFA500",
        "B+": "#00CED1",
        "B": "#32CD32",
        "C+": "#ADFF2F",
        "C": "#808080",
        "D": "#FF4444",
    }
    return colors.get(grade, "#FFFFFF")


def get_grade_emoji(grade: str) -> str:
    emoji_map = {
        "A+": "🌟", "A": "⭐", "B+": "✅",
        "B": "🔵", "C+": "🟡", "C": "🟠", "D": "🔴",
    }
    return emoji_map.get(grade, "⚪")


def run_screening(use_mock: bool = False) -> bool:
    """執行篩選"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from stock_screener.screener import StockScreener

        screener = StockScreener()
        with st.spinner("🔍 篩選中，請稍候..."):
            top_stocks = screener.run(use_mock_data=use_mock, top_n=30)

        if top_stocks:
            st.success(f"✅ 篩選完成！共分析 {len(top_stocks)} 檔股票")
            return True
        else:
            st.error("❌ 篩選失敗，請檢查網路連線")
            return False
    except Exception as e:
        st.error(f"❌ 執行失敗: {e}")
        return False


# ─── 側邊欄 ───────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.image("https://via.placeholder.com/200x60/1a1a2e/FFD700?text=台股篩選系統",
                 use_column_width=True)
        st.markdown("---")

        # 導航
        page = st.radio(
            "📌 頁面導航",
            ["🏆 今日精選", "📊 個股分析", "🏭 產業趨勢", "📈 歷史記錄", "⚙️ 設定"],
            label_visibility="collapsed"
        )

        st.markdown("---")

        # 快速操作
        st.markdown("### 🔄 手動執行篩選")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 正式篩選", use_container_width=True,
                         help="使用真實市場資料（需要網路）"):
                if run_screening(use_mock=False):
                    st.rerun()
        with col2:
            if st.button("🧪 測試模式", use_container_width=True,
                         help="使用模擬資料快速測試"):
                if run_screening(use_mock=True):
                    st.rerun()

        st.markdown("---")

        # 篩選條件設定
        st.markdown("### 🎯 篩選條件")
        min_score = st.slider("最低綜合評分", 0, 100, 60)
        show_grades = st.multiselect(
            "顯示評級",
            ["A+", "A", "B+", "B", "C+", "C", "D"],
            default=["A+", "A", "B+", "B"]
        )

        st.markdown("---")
        st.caption("⚡ 每日 14:30 自動執行篩選")
        st.caption("📱 可在 iPad Safari 瀏覽")

        return page, min_score, show_grades


# ─── 頁面渲染函數 ─────────────────────────────────────────────────────────────

def render_top_stocks(data: Dict, min_score: float, show_grades: List[str]):
    """渲染今日精選頁"""
    top_stocks = data.get("top_stocks", [])
    screening_date = data.get("date", "N/A")
    total_analyzed = data.get("total_analyzed", 0)

    # 標題
    st.markdown(f"""
    <div class="main-header">
        <h1>🏆 今日精選股票</h1>
        <p>📅 {screening_date} 收盤後分析 ｜ 共分析 {total_analyzed} 檔股票</p>
    </div>
    """, unsafe_allow_html=True)

    # 快速統計
    if top_stocks:
        col1, col2, col3, col4 = st.columns(4)
        a_plus = sum(1 for s in top_stocks if s.get("grade") == "A+")
        a = sum(1 for s in top_stocks if s.get("grade") in ["A+", "A"])
        avg_score = sum(s.get("composite_score", 0) for s in top_stocks[:10]) / min(len(top_stocks), 10)
        hot_ind = data.get("hot_industries", [{}])[0].get("industry", "N/A") if data.get("hot_industries") else "N/A"

        with col1:
            st.metric("🌟 A+ 評級股票", a_plus)
        with col2:
            st.metric("⭐ A 級以上股票", a)
        with col3:
            st.metric("📊 TOP10 平均分", f"{avg_score:.1f}")
        with col4:
            st.metric("🔥 最強產業", hot_ind)

    st.markdown("---")

    # 過濾股票
    filtered = [
        s for s in top_stocks
        if s.get("composite_score", 0) >= min_score
        and s.get("grade", "") in show_grades
    ]

    if not filtered:
        st.info("📭 目前沒有符合篩選條件的股票，請調整條件")
        return

    # 股票排行榜
    st.subheader(f"📋 精選股票排行榜 ({len(filtered)} 檔)")

    # 建立表格資料
    rows = []
    for i, stock in enumerate(filtered, 1):
        grade = stock.get("grade", "")
        rows.append({
            "排名": i,
            "代號": stock.get("stock_id", ""),
            "名稱": stock.get("stock_name", ""),
            "產業": stock.get("industry", ""),
            "綜合評分": f"{stock.get('composite_score', 0):.1f}",
            "評級": f"{get_grade_emoji(grade)} {grade}",
            "技術": f"{stock.get('technical_score', 0):.0f}",
            "基本面": f"{stock.get('fundamental_score', 0):.0f}",
            "籌碼": f"{stock.get('institutional_score', 0):.0f}",
            "產業分": f"{stock.get('industry_score', 0):.0f}",
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "排名": st.column_config.NumberColumn(width="small"),
            "代號": st.column_config.TextColumn(width="small"),
            "綜合評分": st.column_config.TextColumn(width="medium"),
            "評級": st.column_config.TextColumn(width="small"),
        }
    )

    # 個股卡片
    st.markdown("---")
    st.subheader("🃏 精選股票詳細分析")

    for stock in filtered[:10]:
        grade = stock.get("grade", "")
        grade_color = get_grade_color(grade)
        composite = stock.get("composite_score", 0)

        with st.expander(
            f"{get_grade_emoji(grade)} {stock.get('stock_id')} {stock.get('stock_name')} "
            f"| 綜合評分: {composite:.1f} | {grade}",
            expanded=(composite >= 75)
        ):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("技術分析", f"{stock.get('technical_score', 0):.0f}/100")
            with col2:
                st.metric("基本面", f"{stock.get('fundamental_score', 0):.0f}/100")
            with col3:
                st.metric("籌碼面", f"{stock.get('institutional_score', 0):.0f}/100")
            with col4:
                st.metric("產業趨勢", f"{stock.get('industry_score', 0):.0f}/100")

            # 觀察重點
            key_points = stock.get("key_points", [])
            if key_points:
                st.markdown("**📌 觀察重點:**")
                for point in key_points:
                    st.markdown(f"- {point}")

            # 各面向訊號
            col_left, col_right = st.columns(2)
            with col_left:
                tech_signals = stock.get("technical_signals", [])
                if tech_signals:
                    st.markdown("**📊 技術訊號:**")
                    for sig in tech_signals:
                        st.markdown(f"- {sig}")

                fund_signals = stock.get("fundamental_signals", [])
                if fund_signals:
                    st.markdown("**💰 基本面訊號:**")
                    for sig in fund_signals:
                        st.markdown(f"- {sig}")

            with col_right:
                inst_signals = stock.get("institutional_signals", [])
                if inst_signals:
                    st.markdown("**🏦 籌碼訊號:**")
                    for sig in inst_signals:
                        st.markdown(f"- {sig}")

                ind_signals = stock.get("industry_signals", [])
                if ind_signals:
                    st.markdown("**🏭 產業訊號:**")
                    for sig in ind_signals:
                        st.markdown(f"- {sig}")

            # 技術指標
            indicators = stock.get("indicators", {})
            if indicators:
                st.markdown("**📈 技術指標:**")
                ind_cols = st.columns(6)
                ind_items = [
                    ("現價", indicators.get("price", "N/A")),
                    ("1日漲跌", f"{indicators.get('change_1d', 0):+.2f}%"),
                    ("RSI", indicators.get("rsi", "N/A")),
                    ("K值", indicators.get("k", "N/A")),
                    ("D值", indicators.get("d", "N/A")),
                    ("量/均量", indicators.get("volume_ratio", "N/A")),
                ]
                for col, (label, val) in zip(ind_cols, ind_items):
                    with col:
                        st.metric(label, val)


def render_industry_trends(data: Dict):
    """渲染產業趨勢頁"""
    st.markdown("""
    <div class="main-header">
        <h1>🏭 產業趨勢分析</h1>
        <p>台灣股市各產業強弱與輪動分析</p>
    </div>
    """, unsafe_allow_html=True)

    hot_industries = data.get("hot_industries", [])
    industry_signals = data.get("industry_signals", [])

    # 產業輪動訊號
    if industry_signals:
        st.subheader("🔄 產業輪動訊號")
        for sig in industry_signals:
            st.info(sig)

    # 熱門產業排行
    if hot_industries:
        st.subheader("🔥 產業強弱排行")
        rows = []
        for i, ind in enumerate(hot_industries, 1):
            ret5 = ind.get("avg_ret_5d", 0)
            ret20 = ind.get("avg_ret_20d", 0)
            rows.append({
                "排名": i,
                "產業": ind.get("industry", ""),
                "5日報酬": f"{ret5:+.2f}%",
                "20日報酬": f"{ret20:+.2f}%",
                "1日報酬": f"{ind.get('avg_ret_1d', 0):+.2f}%",
                "成份股數": ind.get("stocks_count", 0),
                "強弱": "🔴" if ret5 < 0 else ("🟢" if ret5 > 2 else "🟡"),
            })

        df = pd.DataFrame(rows)

        # 視覺化產業排行
        try:
            import plotly.express as px
            import plotly.graph_objects as go

            fig = go.Figure(go.Bar(
                x=[r["產業"] for r in rows],
                y=[float(r["5日報酬"].replace("%", "").replace("+", "")) for r in rows],
                marker_color=[
                    "#FF4444" if float(r["5日報酬"].replace("%", "").replace("+", "")) < 0
                    else "#00CC44"
                    for r in rows
                ],
                text=[r["5日報酬"] for r in rows],
                textposition="auto",
            ))
            fig.update_layout(
                title="各產業5日報酬率",
                xaxis_title="產業",
                yaxis_title="報酬率 (%)",
                plot_bgcolor="#1e2130",
                paper_bgcolor="#1e2130",
                font_color="white",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            pass

        st.dataframe(df, use_container_width=True, hide_index=True)


def render_history(history: List[Dict]):
    """渲染歷史記錄頁"""
    st.markdown("""
    <div class="main-header">
        <h1>📈 歷史篩選記錄</h1>
        <p>過去每日篩選結果追蹤</p>
    </div>
    """, unsafe_allow_html=True)

    if not history:
        st.info("📭 目前沒有歷史記錄，請先執行篩選")
        return

    # 歷史記錄表
    rows = []
    for h in reversed(history):
        top3 = h.get("top3", [])
        top3_str = " | ".join([f"{s['stock_id']}({s['score']:.0f})" for s in top3])
        rows.append({
            "日期": h.get("date", ""),
            "分析股數": h.get("total_analyzed", 0),
            "TOP3 精選": top3_str,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_settings():
    """渲染設定頁"""
    st.markdown("""
    <div class="main-header">
        <h1>⚙️ 系統設定</h1>
        <p>Telegram 通知與 API 設定</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("📱 Telegram Bot 設定")
    st.markdown("""
    **設定步驟:**
    1. 在 Telegram 搜尋 `@BotFather`
    2. 傳送 `/newbot` 建立新 Bot
    3. 取得 **Bot Token**
    4. 搜尋 `@userinfobot` 取得您的 **Chat ID**
    5. 將 Token 和 Chat ID 設定為 GitHub Secrets:
       - `TELEGRAM_BOT_TOKEN`
       - `TELEGRAM_CHAT_ID`
    """)

    with st.expander("🔐 目前設定狀態"):
        import os
        token_set = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
        chat_set = bool(os.getenv("TELEGRAM_CHAT_ID"))
        finmind_set = bool(os.getenv("FINMIND_API_TOKEN"))

        st.write(f"TELEGRAM_BOT_TOKEN: {'✅ 已設定' if token_set else '❌ 未設定'}")
        st.write(f"TELEGRAM_CHAT_ID: {'✅ 已設定' if chat_set else '❌ 未設定'}")
        st.write(f"FINMIND_API_TOKEN: {'✅ 已設定' if finmind_set else '❌ 未設定 (將使用模擬資料)'}")

    st.subheader("📊 FinMind API 設定 (法人/基本面資料)")
    st.markdown("""
    **設定步驟:**
    1. 前往 [FinMind](https://finmindtrade.com/) 註冊帳號
    2. 免費方案每日有限制次數
    3. 取得 API Token 後設定為 GitHub Secret: `FINMIND_API_TOKEN`

    *不設定時系統將使用模擬資料*
    """)

    st.subheader("⏰ 自動排程說明")
    st.markdown("""
    - **排程時間**: 台灣時間每日 14:30 (UTC+8 / GitHub Actions UTC 06:30)
    - **執行平台**: GitHub Actions
    - **資料來源**: Yahoo Finance + FinMind API
    - **結果儲存**: `results/latest_screening.json`
    """)


# ─── 主程式 ───────────────────────────────────────────────────────────────────

def main():
    # 側邊欄
    page, min_score, show_grades = render_sidebar()

    # 載入資料
    data = load_results()
    history = load_history()

    # 頁面路由
    if "今日精選" in page:
        if data:
            render_top_stocks(data, min_score, show_grades)
        else:
            st.markdown("""
            <div class="main-header">
                <h1>🏆 今日精選股票</h1>
                <p>歡迎使用台灣股市每日篩選系統</p>
            </div>
            """, unsafe_allow_html=True)
            st.info("📭 尚無篩選結果，請點擊左側「🚀 正式篩選」或「🧪 測試模式」開始分析")

            st.markdown("""
            ### 🚀 快速開始

            1. **點擊左側「🧪 測試模式」** - 使用模擬資料快速體驗系統
            2. **設定 Telegram Bot** - 在「⚙️ 設定」頁面查看說明
            3. **設定 GitHub Actions** - 啟用每日自動篩選

            ### 📊 評分說明
            | 評級 | 分數範圍 | 建議 |
            |------|---------|------|
            | 🌟 A+ | 90-100 | 強力關注候選 |
            | ⭐ A  | 80-89  | 值得關注 |
            | ✅ B+ | 70-79  | 偏多觀察 |
            | 🔵 B  | 60-69  | 中性偏多 |
            | 🟡 C+ | 50-59  | 中性 |
            | 🟠 C  | 40-49  | 中性偏弱 |
            | 🔴 D  | 0-39   | 弱勢迴避 |

            ### ⚠️ 免責聲明
            本系統提供之資訊僅供參考，不構成任何投資建議。
            股票投資有風險，請自行評估風險並謹慎決策。
            """)

    elif "個股分析" in page:
        st.markdown("""
        <div class="main-header">
            <h1>📊 個股分析</h1>
        </div>
        """, unsafe_allow_html=True)

        all_stocks = data.get("all_stocks", []) if data else []
        if not all_stocks:
            st.info("請先執行篩選以取得個股資料")
            return

        stock_options = {
            f"{s['stock_id']} {s['stock_name']}": s
            for s in all_stocks[:50]
        }
        selected = st.selectbox("選擇股票", list(stock_options.keys()))

        if selected:
            stock = stock_options[selected]
            grade = stock.get("grade", "")

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("綜合評分", f"{stock.get('composite_score', 0):.1f}")
            with col2:
                st.metric("評級", f"{get_grade_emoji(grade)} {grade}")
            with col3:
                st.metric("技術面", f"{stock.get('technical_score', 0):.0f}")
            with col4:
                st.metric("基本面", f"{stock.get('fundamental_score', 0):.0f}")
            with col5:
                st.metric("籌碼面", f"{stock.get('institutional_score', 0):.0f}")

            st.markdown("---")
            key_points = stock.get("key_points", [])
            if key_points:
                st.subheader("📌 觀察重點")
                for pt in key_points:
                    st.markdown(f"- {pt}")

    elif "產業趨勢" in page:
        if data:
            render_industry_trends(data)
        else:
            st.info("請先執行篩選以取得產業趨勢資料")

    elif "歷史記錄" in page:
        render_history(history)

    elif "設定" in page:
        render_settings()


if __name__ == "__main__":
    main()
