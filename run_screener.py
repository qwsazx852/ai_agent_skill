"""
股票篩選執行腳本
可從命令列直接執行

Usage:
    # 使用真實資料（需要網路）
    python run_screener.py

    # 測試模式（模擬資料）
    python run_screener.py --mock

    # 自訂股票清單
    python run_screener.py --stocks 2330 2317 3711

    # 指定輸出數量
    python run_screener.py --top 20

    # 傳送 Telegram 通知
    python run_screener.py --notify

    # 完整執行（真實資料 + 通知）
    python run_screener.py --notify --dashboard-url https://your-app.streamlit.app
"""

import argparse
import json
import logging
import sys
import os
from datetime import datetime

# ─── 日誌設定 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"results/screener_{datetime.now().strftime('%Y%m%d')}.log",
                           encoding="utf-8",
                           mode="a")
    ]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="台灣股市每日篩選系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--mock", action="store_true",
        help="使用模擬資料（測試用，不需網路）"
    )
    parser.add_argument(
        "--stocks", nargs="+", metavar="STOCK_ID",
        help="自訂股票代號清單 (e.g., 2330 2317 3711)"
    )
    parser.add_argument(
        "--top", type=int, default=30,
        help="輸出前N名 (預設: 30)"
    )
    parser.add_argument(
        "--notify", action="store_true",
        help="完成後傳送 Telegram 通知"
    )
    parser.add_argument(
        "--dashboard-url", type=str, default="",
        metavar="URL",
        help="Streamlit Dashboard 網址（附在通知中）"
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="不儲存結果到檔案"
    )

    args = parser.parse_args()

    # 確保結果目錄存在
    os.makedirs("results", exist_ok=True)

    logger.info("=" * 60)
    logger.info("🇹🇼 台灣股市每日篩選系統")
    logger.info(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"模式: {'模擬資料' if args.mock else '真實資料'}")
    logger.info("=" * 60)

    try:
        from stock_screener.screener import StockScreener

        screener = StockScreener()

        # 執行篩選
        top_stocks = screener.run(
            use_mock_data=args.mock,
            custom_stocks=args.stocks,
            top_n=args.top
        )

        if not top_stocks:
            logger.warning("⚠️ 真實資料篩選無結果，改用模擬資料重試...")
            top_stocks = screener.run(
                use_mock_data=True,
                custom_stocks=args.stocks,
                top_n=args.top
            )
            if not top_stocks:
                logger.error("❌ 篩選失敗，無結果（含模擬模式重試）")
                sys.exit(1)

        # 顯示結果摘要
        logger.info("\n" + "=" * 60)
        logger.info(f"🏆 篩選結果 TOP {min(10, len(top_stocks))}")
        logger.info("=" * 60)
        logger.info(f"{'排名':<4} {'代號':<8} {'名稱':<12} {'綜合分':<8} {'評級'}")
        logger.info("-" * 50)

        for i, stock in enumerate(top_stocks[:10], 1):
            logger.info(
                f"{i:<4} {stock['stock_id']:<8} "
                f"{stock['stock_name']:<12} "
                f"{stock['composite_score']:<8.1f} "
                f"{stock['grade']}"
            )

        logger.info("=" * 60)

        # 顯示熱門產業
        hot_industries = screener.industry_stats
        if hot_industries:
            logger.info("\n🏭 熱門產業:")
            from stock_screener.analysis.industry import get_hot_industries
            for ind in get_hot_industries(hot_industries, top_n=3):
                logger.info(f"  {ind['industry']}: {ind['avg_ret_5d']:+.1f}%")

        # 傳送 Telegram 通知
        if args.notify:
            logger.info("\n📱 傳送 Telegram 通知...")
            success = screener.notify(
                top_stocks=top_stocks,
                dashboard_url=args.dashboard_url
            )
            if success:
                logger.info("✅ Telegram 通知已傳送")
            else:
                logger.warning("⚠️ Telegram 通知傳送失敗（請確認 BOT_TOKEN 和 CHAT_ID）")

        logger.info("\n✅ 篩選完成！")
        return 0

    except ImportError as e:
        logger.error(f"❌ 套件未安裝: {e}")
        logger.error("請執行: pip install -r requirements.txt")
        return 1
    except KeyboardInterrupt:
        logger.info("\n⏹️ 使用者中斷")
        return 0
    except Exception as e:
        logger.error(f"❌ 執行失敗: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
