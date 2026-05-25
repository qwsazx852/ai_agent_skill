#!/usr/bin/env python3
"""
月營收篩選執行腳本
每月10日執行，分析台股月營收成長情況

用法:
  python run_monthly_revenue.py
  python run_monthly_revenue.py --top 20 --notify
  python run_monthly_revenue.py --mock
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# 確保 package 可以被找到
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="台股月營收篩選")
    parser.add_argument("--top", type=int, default=20, help="輸出前N名 (預設20)")
    parser.add_argument("--notify", action="store_true", help="發送 Telegram 通知")
    parser.add_argument("--mock", action="store_true", help="使用模擬資料（測試）")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("📊 台股月營收篩選系統")
    logger.info(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        from stock_screener.config import config
        from stock_screener.data.tw_stock_list import get_combined_stock_list
        from stock_screener.analysis.revenue_alert import (
            screen_revenue_stocks,
            format_revenue_telegram_message,
        )

        if args.mock:
            logger.info("🧪 模擬模式 - 產生假資料")
            mock_results = [
                {
                    "stock_id": "2330", "stock_name": "台積電",
                    "score": 85, "yoy": 52.3, "mom": 8.1,
                    "consecutive_growth": 5, "is_new_high_12m": True,
                    "signals": ["🚀 年增率 +52.3%（爆發性成長）", "🏆 創近12個月營收新高！"],
                    "industry": "半導體",
                },
                {
                    "stock_id": "2382", "stock_name": "廣達",
                    "score": 72, "yoy": 35.8, "mom": 12.4,
                    "consecutive_growth": 4, "is_new_high_12m": False,
                    "signals": ["🔥 年增率 +35.8%（強勁成長）", "📊 連續 4 個月成長"],
                    "industry": "AI/雲端",
                },
                {
                    "stock_id": "3661", "stock_name": "世芯-KY",
                    "score": 68, "yoy": 28.2, "mom": 5.3,
                    "consecutive_growth": 3, "is_new_high_12m": False,
                    "signals": ["✅ 年增率 +28.2%", "✅ 連續 3 個月成長"],
                    "industry": "AI/雲端",
                },
                {
                    "stock_id": "2454", "stock_name": "聯發科",
                    "score": 60, "yoy": 18.5, "mom": 3.2,
                    "consecutive_growth": 2, "is_new_high_12m": False,
                    "signals": ["✅ 年增率 +18.5%"],
                    "industry": "半導體",
                },
                {
                    "stock_id": "2615", "stock_name": "萬海",
                    "score": 55, "yoy": 41.2, "mom": -2.1,
                    "consecutive_growth": 0, "is_new_high_12m": False,
                    "signals": ["🔥 年增率 +41.2%（強勁成長）"],
                    "industry": "航運",
                },
            ]
            results = mock_results
        else:
            # 取得股票清單
            logger.info("📋 取得股票清單...")
            stock_df = get_combined_stock_list(
                finmind_token=config.FINMIND_API_TOKEN,
                max_stocks=200,
            )
            stock_list = stock_df.to_dict("records")
            logger.info(f"股票池: {len(stock_list)} 檔")

            if not config.FINMIND_API_TOKEN:
                logger.error("❌ 未設定 FINMIND_API_TOKEN，無法取得真實月營收資料")
                return 1

            # 執行月營收篩選
            logger.info(f"📊 分析月營收...")
            results = screen_revenue_stocks(
                stock_list=stock_list,
                finmind_token=config.FINMIND_API_TOKEN,
                top_n=args.top,
            )

        # 顯示結果
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🏆 月營收成長 TOP {len(results)}")
        logger.info(f"{'=' * 60}")
        logger.info(f"{'排名':<4} {'代號':<6} {'名稱':<12} {'評分':<6} {'YoY':<10} {'MoM':<8} {'連月'}")
        logger.info("-" * 60)
        for i, r in enumerate(results, 1):
            yoy = f"+{r['yoy']:.1f}%" if r.get("yoy") and r["yoy"] >= 0 else f"{r.get('yoy', 0):.1f}%"
            mom = f"+{r['mom']:.1f}%" if r.get("mom") and r["mom"] >= 0 else f"{r.get('mom', 0):.1f}%"
            cons = f"{r.get('consecutive_growth', 0)}月↑"
            new_high = "🏆" if r.get("is_new_high_12m") else "  "
            logger.info(
                f"{i:<4} {r['stock_id']:<6} {r.get('stock_name',''):<12} "
                f"{r['score']:<6.0f} {yoy:<10} {mom:<8} {cons} {new_high}"
            )
        logger.info("=" * 60)

        # 傳送 Telegram
        if args.notify:
            logger.info("\n📱 傳送 Telegram 通知...")
            from stock_screener.notifier.telegram import TelegramNotifier
            notifier = TelegramNotifier(
                bot_token=config.TELEGRAM_BOT_TOKEN,
                chat_id=config.TELEGRAM_CHAT_ID,
            )
            date_str = datetime.now().strftime("%Y-%m")
            messages = format_revenue_telegram_message(results, date=date_str)
            success = all(notifier.send_message(msg) for msg in messages)
            if success:
                logger.info("✅ Telegram 通知已傳送")
            else:
                logger.warning("⚠️ Telegram 通知傳送失敗")

        logger.info("\n✅ 月營收篩選完成！")
        return 0

    except ImportError as e:
        logger.error(f"❌ 套件未安裝: {e}")
        return 1
    except Exception as e:
        logger.error(f"❌ 執行失敗: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
