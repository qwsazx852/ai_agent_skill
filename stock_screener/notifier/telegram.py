"""
Telegram Bot 通知模組
每日篩選結果推送到 Telegram

功能:
- 傳送文字訊息
- 傳送 Markdown 格式報告
- 傳送圖片/圖表
- 傳送每日篩選摘要
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram Bot 通知器"""

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = (bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
        self.chat_id = (chat_id or os.getenv("TELEGRAM_CHAT_ID", "")).strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        logger.info(f"Telegram 初始化 - Token前10碼: {self.bot_token[:10]}... 長度:{len(self.bot_token)}")

    def _is_configured(self) -> bool:
        """確認 Telegram 設定是否完整"""
        return bool(self.bot_token and self.chat_id)

    def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True
    ) -> bool:
        """
        傳送文字訊息

        Args:
            text: 訊息內容 (支援 Markdown)
            parse_mode: 格式化模式
            disable_web_page_preview: 是否禁用預覽

        Returns:
            是否成功
        """
        if not self._is_configured():
            logger.warning("Telegram 未設定 BOT_TOKEN 或 CHAT_ID")
            return False

        try:
            import requests

            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            }

            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram 訊息傳送成功")
                return True
            else:
                logger.error(f"Telegram 傳送失敗: {resp.status_code} {resp.text}")
                return False

        except Exception as e:
            logger.error(f"Telegram 傳送例外: {e}")
            return False

    def send_photo(self, photo_path: str, caption: str = "") -> bool:
        """
        傳送圖片

        Args:
            photo_path: 圖片路徑
            caption: 圖片說明

        Returns:
            是否成功
        """
        if not self._is_configured():
            return False

        try:
            import requests

            url = f"{self.base_url}/sendPhoto"
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown",
                }
                resp = requests.post(url, files=files, data=data, timeout=30)
                return resp.status_code == 200

        except Exception as e:
            logger.error(f"Telegram 圖片傳送失敗: {e}")
            return False

    def send_document(self, file_path: str, caption: str = "") -> bool:
        """
        傳送文件

        Args:
            file_path: 文件路徑
            caption: 說明

        Returns:
            是否成功
        """
        if not self._is_configured():
            return False

        try:
            import requests

            url = f"{self.base_url}/sendDocument"
            with open(file_path, "rb") as f:
                files = {"document": f}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown",
                }
                resp = requests.post(url, files=files, data=data, timeout=30)
                return resp.status_code == 200

        except Exception as e:
            logger.error(f"Telegram 文件傳送失敗: {e}")
            return False

    def send_screening_report(
        self,
        top_stocks: List[Dict],
        hot_industries: List[Dict],
        industry_signals: List[str],
        date: str = "",
        dashboard_url: str = ""
    ) -> bool:
        """
        傳送每日股票篩選報告

        Args:
            top_stocks: 篩選排名前N名股票 (list of dicts)
            hot_industries: 熱門產業清單
            industry_signals: 產業輪動訊號
            date: 報告日期
            dashboard_url: Dashboard 網址

        Returns:
            是否成功
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # ── 標題 ──────────────────────────────
        messages = []

        header = f"""🇹🇼 *台灣股市每日篩選報告*
📅 {date} 收盤後分析
{'─' * 30}"""
        messages.append(header)

        # ── 熱門產業 ──────────────────────────
        if hot_industries:
            industry_text = "🔥 *今日強勢產業 TOP5*\n"
            for i, ind in enumerate(hot_industries[:5], 1):
                ret5 = ind.get("avg_ret_5d", 0)
                arrow = "▲" if ret5 >= 0 else "▼"
                industry_text += f"{i}. {ind['industry']} {arrow}{abs(ret5):.1f}%\n"
            messages.append(industry_text)

        # ── 產業輪動訊號 ──────────────────────
        if industry_signals:
            signal_text = "🔄 *產業輪動觀察*\n"
            for sig in industry_signals[:3]:
                signal_text += f"• {sig}\n"
            messages.append(signal_text)

        # ── 今日精選股票 ──────────────────────
        if top_stocks:
            stock_text = f"⭐ *今日精選股票 TOP{min(len(top_stocks), 10)}*\n"
            stock_text += "```\n"
            stock_text += f"{'排名':<4} {'代號':<6} {'名稱':<8} {'評分':<6} {'評級'}\n"
            stock_text += "─" * 36 + "\n"

            for i, stock in enumerate(top_stocks[:10], 1):
                sid = stock.get("stock_id", "")
                name = stock.get("stock_name", sid)[:6]
                score = stock.get("composite_score", 0)
                grade = stock.get("grade", "")
                stock_text += f"{i:<4} {sid:<6} {name:<8} {score:<6.1f} {grade}\n"

            stock_text += "```"
            messages.append(stock_text)

        # ── 個股詳細訊號 ──────────────────────
        if top_stocks:
            detail_text = "📋 *精選股票重點*\n"
            for stock in top_stocks[:5]:
                sid = stock.get("stock_id", "")
                name = stock.get("stock_name", sid)
                score = stock.get("composite_score", 0)
                grade = stock.get("grade", "")
                key_points = stock.get("key_points", [])

                grade_emoji = {
                    "A+": "🌟", "A": "⭐", "B+": "✅",
                    "B": "🔵", "C+": "🟡", "C": "🟠", "D": "🔴"
                }.get(grade, "")

                detail_text += f"\n{grade_emoji} *{sid} {name}* ({score:.0f}分/{grade})\n"
                for point in key_points[:3]:
                    detail_text += f"  • {point}\n"

            messages.append(detail_text)

        # ── Dashboard 連結 ─────────────────────
        if dashboard_url:
            footer = f"""
{'─' * 30}
🖥️ [查看完整 Dashboard]({dashboard_url})
⏰ 自動生成於 {datetime.now().strftime('%H:%M')}"""
            messages.append(footer)

        # 組合並傳送訊息（Telegram 單則訊息有 4096 字元限制）
        full_text = "\n\n".join(messages)

        if len(full_text) <= 4000:
            return self.send_message(full_text)
        else:
            # 分段傳送
            success = True
            for msg in messages:
                if msg.strip():
                    if not self.send_message(msg):
                        success = False
            return success

    def send_error_alert(self, error_msg: str) -> bool:
        """傳送錯誤警告"""
        text = f"⚠️ *股票篩選系統警告*\n\n{error_msg}\n\n時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        return self.send_message(text)

    def send_test_message(self) -> bool:
        """傳送測試訊息"""
        text = (
            "✅ *台灣股市篩選系統* 測試訊息\n\n"
            "Telegram Bot 設定成功！\n"
            f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(text)
