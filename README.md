# 🇹🇼 台灣股市每日篩選系統

每日收盤後自動篩選值得觀察的股票，整合技術面、基本面、籌碼面、產業趨勢四大維度綜合評分。

[![Daily Screening](https://github.com/qwsazx852/ai_agent_skill/actions/workflows/daily_screening.yml/badge.svg)](https://github.com/qwsazx852/ai_agent_skill/actions/workflows/daily_screening.yml)

> 最後更新：2026-05-26

---

## 📊 系統架構

```
股市收盤 13:30
      │
      ▼
GitHub Actions 自動觸發 (UTC 07:45 / 台灣 15:45)
      │
      ├─ 📥 資料擷取
      │     ├─ Yahoo Finance (OHLCV 技術資料)
      │     └─ FinMind API (法人/基本面/融資券)
      │
      ├─ 🔍 四維度分析
      │     ├─ 技術分析 (30%) ─ MA/MACD/RSI/KD/布林/量能
      │     ├─ 基本面 (25%)  ─ EPS/ROE/營收/估值
      │     ├─ 籌碼分析 (30%) ─ 三大法人/融資券
      │     └─ 產業趨勢 (15%) ─ 類股強弱輪動
      │
      ├─ 🏆 綜合評分排名 (0-100分)
      │
      ├─ 💾 結果儲存 (results/latest_screening.json)
      │
      ├─ 📱 Telegram 通知推送
      │
      └─ 🖥️ Streamlit Dashboard 更新
```

---

## 🎯 評分系統

| 評級 | 分數 | 說明 |
|------|------|------|
| 🌟 A+ | 90-100 | 四面向均強，強力關注 |
| ⭐ A  | 80-89  | 整體優異，值得買進候選 |
| ✅ B+ | 70-79  | 偏多，短期觀察 |
| 🔵 B  | 60-69  | 中性偏多 |
| 🟡 C+ | 50-59  | 中性 |
| 🟠 C  | 40-49  | 中性偏弱 |
| 🔴 D  | 0-39   | 弱勢，暫時迴避 |

### 各面向評分子指標

**技術面 (30%)**
- 移動平均線多頭排列、MA5/MA20/MA60 位置
- MACD 黃金交叉、動能方向
- RSI 強弱區間
- KD 黃金交叉
- 布林通道位置
- 成交量放大 / 量價齊揚

**基本面 (25%)**
- EPS 成長率
- 月營收年增率
- ROE 股東權益報酬率
- 本益比 / 股價淨值比 / 股息殖利率

**籌碼面 (30%)**
- 外資當日 + 3日 + 10日累計買賣超
- 投信買賣超
- 自營商買賣超
- 融資增減 / 融券餘額

**產業趨勢 (15%)**
- 所屬產業近20日相對強弱排名
- 產業近5日動能
- 個股相對產業超額表現

---

## 🚀 快速開始

### 方法一：測試模式（不需 API）

```bash
# 複製並安裝
git clone https://github.com/qwsazx852/ai_agent_skill.git
cd ai_agent_skill
pip install -r requirements.txt

# 使用模擬資料測試
python run_screener.py --mock --top 10
```

### 方法二：正式執行（需要網路）

```bash
# 使用真實市場資料
python run_screener.py --top 30

# 加上 Telegram 通知
python run_screener.py --notify
```

### 方法三：Streamlit Dashboard

```bash
streamlit run stock_screener/app.py
```
在瀏覽器開啟 `http://localhost:8501`（iPad 連同一個 WiFi 即可存取）

---

## ⚙️ 環境設定

複製 `.env.example` 為 `.env` 並填入：

```env
# Telegram Bot (必填，用於推送通知)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# FinMind API (選填，不設定則使用模擬資料)
FINMIND_API_TOKEN=your_finmind_token
```

### 取得 Telegram Bot Token

1. 在 Telegram 搜尋 `@BotFather`
2. 傳送 `/newbot`
3. 輸入 Bot 名稱，取得 Token
4. 搜尋 `@userinfobot` 取得你的 Chat ID

### 取得 FinMind API Token

1. 至 [finmindtrade.com](https://finmindtrade.com) 免費註冊
2. 登入後在個人頁面取得 Token
3. 免費方案每日有請求限制，夠日常使用

---

## ☁️ 雲端部署（iPad 隨時存取）

### GitHub Actions（自動每日執行）

在 GitHub Repository 的 **Settings → Secrets** 設定：

| Secret | 說明 |
|--------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 你的 Telegram Chat ID |
| `FINMIND_API_TOKEN` | FinMind API Token |

在 **Settings → Variables** 設定：

| Variable | 說明 |
|----------|------|
| `STREAMLIT_DASHBOARD_URL` | Streamlit Cloud 部署網址 |

### Streamlit Cloud 部署

1. Fork 此 Repository
2. 前往 [share.streamlit.io](https://share.streamlit.io)
3. 連接 GitHub，選擇此 repo
4. Main file path: `stock_screener/app.py`
5. 在 Secrets 設定環境變數
6. 完成後取得 `https://your-app.streamlit.app` 網址

---

## 📁 專案結構

```
ai_agent_skill/
├── stock_screener/
│   ├── config.py               # 全域設定（權重、參數）
│   ├── screener.py             # 篩選主控流程
│   ├── app.py                  # Streamlit Dashboard
│   ├── data/
│   │   ├── fetcher.py          # yfinance / FinMind 資料擷取
│   │   └── tw_stock_list.py    # 台灣股票清單
│   ├── analysis/
│   │   ├── technical.py        # 技術指標計算
│   │   ├── fundamental.py      # 基本面評分
│   │   ├── institutional.py    # 籌碼面評分
│   │   ├── industry.py         # 產業趨勢分析
│   │   ├── market_env.py       # 大盤環境評估
│   │   └── scorer.py           # 綜合評分整合
│   └── notifier/
│       └── telegram.py         # Telegram 推送
├── run_screener.py             # CLI 執行入口
├── requirements.txt
├── .github/workflows/
│   └── daily_screening.yml     # GitHub Actions 自動排程
├── results/
│   ├── latest_screening.json   # 最新篩選結果
│   └── screening_history.json  # 歷史記錄
└── .env.example                # 環境變數範本
```

---

## 📱 Telegram 通知範例

```
🇹🇼 台灣股市每日篩選報告
📅 2024-01-15  ⏰14:35
──────────────────────────────

🔥 今日強勢產業 TOP5
1. AI/雲端 ▲3.2%
2. 半導體 ▲1.8%
3. 電動車 ▲1.4%
4. 生技醫療 ▲0.9%
5. 電子零組件 ▲0.6%

⭐ 今日精選股票 TOP10
排名 代號   名稱     評分   評級
──────────────────────────────────
1    3661   緯穎     87.3   A
2    2330   台積電   85.1   A
3    6669   緯創     82.4   A
...
```

---

## ⚠️ 免責聲明

本系統提供之資訊**僅供參考，不構成任何投資建議**。
股票投資有虧損風險，請自行評估風險承受能力，謹慎做出投資決策。

---

## 📃 License

MIT License
