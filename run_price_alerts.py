#!/usr/bin/env python3
"""
異常價量警報執行腳本
每日收盤後執行，監控觀察名單的異常動態

用法:
  python run_price_alerts.py
  python run_price_alerts.py --notify
  python run_price_alerts.py --mock
  python run_price_alerts.py --watchlist 2330 2454 2382
"""

import sys
import os
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="台股異常警報")
    parser.add_argument("--notify", action="store_true", help="發送 Telegram 通知")
    parser.add_argument("--mock", action="store_true", help="使用模擬資料（測試）")
    parser.add_argument("--watchlist", nargs="+", help="自訂監控股票代號")
    parser.add_argument("--top", type=int, default=30, help="監控前N名觀察股 (預設30)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🔔 台股異常警報系統")
    logger.info(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        from stock_screener.config import config
        from stock_screener.analysis.price_alert import (
            run_watchlist_alerts,
            format_alert_telegram_messages,
            check_price_alerts,
        )

        if args.mock:
            logger.info("🧪 模擬模式 - 產生假警報資料")
            mock_alerts = [
                {
                    "stock_id": "2382", "stock_name": "廣達",
                    "type": "surge", "level": "high",
                    "emoji": "🚀", "message": "急漲 +6.8%",
                    "value": 6.8, "grade": "B+", "prev_score": 72.0,
                },
                {
                    "stock_id": "3324", "stock_name": "雙鴻",
                    "type": "volume_surge", "level": "high",
                    "emoji": "💥", "message": "爆量 4.2x 均量",
                    "value": 4.2, "grade": "B", "prev_score": 65.0,
                },
                {
                    "stock_id": "2330", "stock_name": "台積電",
                    "type": "new_high", "level": "high",
                    "emoji": "🏆", "message": "突破近高點",
                    "value": 950.0, "grade": "B+", "prev_score": 70.0,
                },
                {
                    "stock_id": "2615", "stock_name": "萬海",
                    "type": "drop", "level": "high",
                    "emoji": "🔻", "message": "急跌 -5.3%",
                    "value": -5.3, "grade": "B", "prev_score": 66.0,
                },
                {
                    "stock_id": "2454", "stock_name": "聯發科",
                    "type": "volume_mild", "level": "medium",
                    "emoji": "📊", "message": "量增 2.3x 均量",
                    "value": 2.3, "grade": "B+", "prev_score": 68.0,
                },
            ]
            mock_summary = {
                "total_alerts": len(mock_alerts),
                "high_alerts": 4,
                "medium_alerts": 1,
                "watchlist_count": 30,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            result = {"alerts": mock_alerts, "summary": mock_summary}

        else:
            results_file = config.RESULTS_FILE
            if not os.path.exists(results_file):
                logger.warning(f"⚠️ 找不到篩選結果: {results_file}")
                logger.info("請先執行 run_screener.py 產生觀察名單")
                return 1

            logger.info(f"📋 讀取觀察名單: {results_file}")
            result = run_watchlist_alerts(
                results_file=results_file,
                top_n_watchlist=args.top,
            )

        alerts = result["alerts"]
        summary = result["summary"]

        # 顯示結果
        logger.info(f"\n監控: {summary['watchlist_count']} 檔")
        logger.info(f"警報: 高優先 {summary['high_alerts']} 個 / 共 {summary['total_alerts']} 個")

        if alerts:
            logger.info(f"\n{'─' * 50}")
            for a in alerts:
                level_mark = "🚨" if a["level"] == "high" else "📊"
                logger.info(
                    f"{level_mark} {a['stock_id']} {a.get('stock_name','')} "
                    f"({a.get('grade','')} {a.get('prev_score',0):.0f}分) "
                    f"— {a.get('emoji','')} {a.get('message','')}"
                )
        else:
            logger.info("✅ 今日無異常動態")

        # 傳送 Telegram
        if args.notify:
            logger.info("\n📱 傳送 Telegram 通知...")
            from stock_screener.notifier.telegram import TelegramNotifier
            notifier = TelegramNotifier(
                bot_token=config.TELEGRAM_BOT_TOKEN,
                chat_id=config.TELEGRAM_CHAT_ID,
            )
            messages = format_alert_telegram_messages(alerts, summary)
            success = all(notifier.send_message(msg) for msg in messages)
            if success:
                logger.info("✅ Telegram 通知已傳送")
            else:
                logger.warning("⚠️ Telegram 通知傳送失敗")

        logger.info("\n✅ 異常警報檢查完成！")
        return 0

    except ImportError as e:
        logger.error(f"❌ 套件未安裝: {e}")
        return 1
    except Exception as e:
        logger.error(f"❌ 執行失敗: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
