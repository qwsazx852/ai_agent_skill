"""
Telegram Bot 測試腳本
在本機執行這個腳本來測試 Bot 是否設定正確

執行方式:
    python test_telegram.py
"""

import sys
import requests

# ── 設定你的資訊 ──────────────────────────────────────────────────
BOT_TOKEN = "8296994753:AAE8UMxeKx-BVBEIhAY2517NO-e0T3e81lM"
CHAT_ID = "6312156679"
# ─────────────────────────────────────────────────────────────────


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
    print(f"\n[2/2] 傳送測試訊息到 Chat ID: {CHAT_ID}...")
    message = (
        "✅ *台灣股市篩選系統* 設定成功！\n\n"
        "嗨 晉嘉，Bot 連線正常 🎉\n\n"
        "📊 系統每天台灣時間 *14:30* 收盤後\n"
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
    print("\n接下來請到 GitHub 設定 Secrets：")
    print(f"  TELEGRAM_BOT_TOKEN = {BOT_TOKEN}")
    print(f"  TELEGRAM_CHAT_ID   = {CHAT_ID}")
    print("\n設定路徑:")
    print("  GitHub Repo → Settings → Secrets and variables")
    print("  → Actions → New repository secret")


if __name__ == "__main__":
    test_bot()
