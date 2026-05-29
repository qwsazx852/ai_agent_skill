"""
族群資金流向分析執行腳本

使用方式:
    python run_sector_flow.py                  # 分析 + 傳送 Telegram
    python run_sector_flow.py --no-notify      # 只分析，不傳送通知
    python run_sector_flow.py --top 5          # 各取 TOP 5

環境變數:
    FINMIND_API_TOKEN   FinMind API 金鑰（必填）
    TELEGRAM_BOT_TOKEN  Telegram Bot Token
    TELEGRAM_CHAT_ID    Telegram Chat ID
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="族群資金流向分析")
    parser.add_argument("--top", type=int, default=10, help="各取前N名（預設10）")
    parser.add_argument("--no-notify", action="store_true", help="不傳送 Telegram 通知")
    args = parser.parse_args()

    token = os.getenv("FINMIND_API_TOKEN", "").strip()
    if not token:
        logger.error("請設定環境變數 FINMIND_API_TOKEN")
        sys.exit(1)

    from stock_screener.analysis.sector_flow import run_sector_flow_analysis
    from stock_screener.notifier.telegram import TelegramNotifier

    logger.info("🚀 開始族群資金流向分析...")
    result = run_sector_flow_analysis(token=token, top_n=args.top)

    top_buy = result["top_buy"]
    top_sell = result["top_sell"]
    date = result["date"]
    analyzed = result["stocks_analyzed"]

    # ── 終端輸出 ──────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  盤後族群資金流向  {date}")
    print(f"{'='*50}")

    print(f"\n🟢 法人買超 TOP{len(top_buy)}")
    print(f"{'排名':<4} {'族群':<14} {'淨流入(億)':<10} {'漲幅'}")
    print("─" * 45)
    for i, t in enumerate(top_buy, 1):
        chg = t["avg_change_pct"]
        chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
        print(f"{i:<4} {t['emoji']}{t['name']:<12} +{t['net_flow_yi']:.1f}億{'':<4} {chg_str}")

    print(f"\n🔴 法人賣超 TOP{len(top_sell)}")
    print(f"{'排名':<4} {'族群':<14} {'淨流出(億)':<10} {'漲幅'}")
    print("─" * 45)
    for i, t in enumerate(top_sell, 1):
        chg = t["avg_change_pct"]
        chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
        print(f"{i:<4} {t['emoji']}{t['name']:<12} {t['net_flow_yi']:.1f}億{'':<5} {chg_str}")

    print(f"\n共分析 {analyzed} 支主題股票")

    # ── 儲存結果 ──────────────────────────────────────────────
    os.makedirs("results", exist_ok=True)
    out_file = "results/latest_sector_flow.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"結果已儲存至 {out_file}")

    # ── Telegram 通知（圖片格式）────────────────────────────────
    if not args.no_notify:
        notifier = TelegramNotifier()
        ok = notifier.send_sector_flow_image(
            top_buy=top_buy,
            top_sell=top_sell,
            date=date,
            stocks_analyzed=analyzed,
        )
        if ok:
            logger.info("✅ Telegram 通知已傳送")
        else:
            logger.warning("⚠️ Telegram 通知傳送失敗（請確認環境變數設定）")


if __name__ == "__main__":
    main()
