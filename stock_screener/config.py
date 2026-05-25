"""
台灣股市每日篩選系統 - 設定檔
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # === Telegram 設定 ===
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # === FinMind API 設定 ===
    FINMIND_API_TOKEN: str = os.getenv("FINMIND_API_TOKEN", "")

    # === 篩選參數 ===
    # 最少成交量 (張)
    MIN_VOLUME: int = 1000
    # 最低股價
    MIN_PRICE: float = 10.0
    # 最高股價 (0 = 不限)
    MAX_PRICE: float = 0
    # 技術面資料天數
    LOOKBACK_DAYS: int = 120
    # 每次篩選最多股票數
    MAX_STOCKS: int = 300
    # 最終輸出排行榜數量
    TOP_N: int = 30

    # === 評分權重 ===
    WEIGHT_TECHNICAL: float = 0.35      # 技術面 35%
    WEIGHT_FUNDAMENTAL: float = 0.15    # 基本面 15%
    WEIGHT_INSTITUTIONAL: float = 0.35  # 籌碼面 35%
    WEIGHT_INDUSTRY: float = 0.15       # 產業趨勢 15%

    # === 結果儲存 ===
    RESULTS_DIR: str = "results"
    RESULTS_FILE: str = "results/latest_screening.json"
    HISTORY_FILE: str = "results/screening_history.json"
    SHAREHOLDING_CACHE_FILE: str = "results/shareholding_cache.json"

    # === 市場時間 (台灣時區 UTC+8) ===
    MARKET_CLOSE_HOUR: int = 13
    MARKET_CLOSE_MINUTE: int = 30

    # === 觀察清單產業分類 ===
    INDUSTRIES: List[str] = field(default_factory=lambda: [
        "半導體", "電子零組件", "電腦及週邊設備",
        "光電", "通訊網路", "電子通路", "資訊服務",
        "其他電子", "金融保險", "生技醫療",
        "建材營造", "航運", "化學", "鋼鐵",
        "食品", "傳統產業", "電機機械"
    ])


# 全域設定實例
config = Config()
