"""
Telegram Bot 測試腳本
在本機執行這個腳本來測試 Bot 是否設定正確

執行方式:
    python test_telegram.py

⚠️  請勿在此檔案硬編碼 token！
    使用環境變數或 .env 檔案（已加入 .gitignore）
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# ── 從環境變數讀取（不要直接寫在這裡！）──────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# ─────────────────────────────────────────────────────────────────

if not BOT_TOKEN or not CHAT_ID:
    print("❌ 錯誤：請先設定環境變數或 .env 檔案")
    print("   TELEGRAM_BOT_TOKEN=你的token")
    print("   TELEGRAM_CHAT_ID=你的chatid")
    sys.exit(1)


def test_bot():
    print("=" * 50)
    print("🤖 Telegram Bot 連線測試")
    print("=" * 50)

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    # 1. 確認 Bot 資訊
    print("\n[1/2] 確認 Bot 資訊...")
    resp = requests.get(f"{base_url}/getMe", timeout=10)
    if resp.status_code == 200:
        info = resp.json()["result"]
        print(f"  ✅ Bot 名稱: {info['first_name']}")
        print(f"  ✅ Bot 帳號: @{info['username']}")
    else:
        print(f"  ❌ 失敗: {resp.text}")
        sys.exit(1)

    # 2. 傳送測試訊息
    print(f"\n[2/2] 傳送測試訊息...")
    message = (
        "✅ *台灣股市篩選系統* 設定成功！\n\n"
        "Bot 連線正常 🎉\n\n"
        "📊 系統每天台灣時間 *15:45* 收盤後\n"
        "自動傳送今日精選股票報告給你。\n\n"
        "🇹🇼 準備好開始追蹤台股了！"
    )

    resp = requests.post(
        f"{base_url}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        },
        timeout=10,
    )

    if resp.status_code == 200:
        print("  ✅ 訊息傳送成功！請查看 Telegram")
    else:
        print(f"  ❌ 傳送失敗: {resp.text}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("🎉 全部測試通過！")
    print("=" * 50)
    print("\nGitHub Secrets 設定路徑:")
    print("  GitHub Repo → Settings → Secrets and variables")
    print("  → Actions → New repository secret")


if __name__ == "__main__":
    test_bot()
