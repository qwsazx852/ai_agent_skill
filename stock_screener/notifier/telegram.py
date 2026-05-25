"""
Telegram Bot 通知模組 - 精簡實用版分析報告

報告格式:
- 今日強勢產業 TOP3
- 精選股票（含籌碼/技術/產業三維分析）
- 每檔股票重點訊號一目了然
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
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        if not self._is_configured():
            logger.warning("Telegram 未設定 BOT_TOKEN 或 CHAT_ID")
            return False
        try:
            import requests
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info("Telegram 訊息傳送成功")
                return True
            else:
                logger.error(f"Telegram 傳送失敗: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram 傳送例外: {e}")
            return False

    def send_screening_report(
        self,
        top_stocks: List[Dict],
        hot_industries: List[Dict],
        industry_signals: List[str],
        date: str = "",
        dashboard_url: str = "",
    ) -> bool:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # ── 判斷今日大盤氣氛 ──────────────────────────────────────
        all_scores = [s.get("composite_score", 0) for s in top_stocks[:20]]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        if avg_score >= 75:
            market_mood = "🔥 市場強勢，多頭氣氛濃厚"
        elif avg_score >= 65:
            market_mood = "📈 市場偏多，精選標的表現佳"
        elif avg_score >= 55:
            market_mood = "🔄 市場中性，個股分化明顯"
        else:
            market_mood = "⚠️ 市場偏弱，宜謹慎觀察"

        success = True

        # ════════════════════════════════════════════════════════
        # 訊息一：今日總覽 + 強勢產業
        # ════════════════════════════════════════════════════════
        msg1 = (
            f"🇹🇼 *台股每日篩選報告*\n"
            f"📅 {date}  {datetime.now().strftime('%H:%M')}\n"
            f"{'─' * 28}\n"
            f"{market_mood}\n\n"
        )

        if hot_industries:
            msg1 += "🏭 *今日強勢產業*\n"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            for i, ind in enumerate(hot_industries[:5]):
                ret5 = ind.get("avg_ret_5d", 0)
                ret1 = ind.get("avg_ret_1d", 0)
                arrow = "▲" if ret5 >= 0 else "▼"
                msg1 += (
                    f"{medals[i]} {ind['industry']}  "
                    f"{arrow}{abs(ret5):.1f}% (5日)  "
                    f"今日{'+' if ret1>=0 else ''}{ret1:.1f}%\n"
                )

        if industry_signals:
            msg1 += "\n🔄 *輪動觀察*\n"
            for sig in industry_signals[:2]:
                msg1 += f"• {sig}\n"

        if not self.send_message(msg1):
            success = False

        # ════════════════════════════════════════════════════════
        # 訊息二：精選股票詳細分析（每檔一段）
        # ════════════════════════════════════════════════════════
        grade_emoji = {
            "A+": "🌟", "A": "⭐", "B+": "✅",
            "B": "🔵", "C+": "🟡", "C": "🟠", "D": "🔴",
        }

        stocks_to_show = [s for s in top_stocks if s.get("grade") in
                          ["A+", "A", "B+", "B"]][:8]

        if stocks_to_show:
            msg2 = f"📋 *精選股票分析 TOP{len(stocks_to_show)}*\n{'─' * 28}\n"

            for i, stock in enumerate(stocks_to_show, 1):
                sid    = stock.get("stock_id", "")
                name   = stock.get("stock_name", sid)
                score  = stock.get("composite_score", 0)
                grade  = stock.get("grade", "")
                ind    = stock.get("industry", "")
                emoji  = grade_emoji.get(grade, "")

                tech_s = stock.get("technical_score", 0)
                inst_s = stock.get("institutional_score", 0)
                ind_s  = stock.get("industry_score", 0)
                fund_s = stock.get("fundamental_score", 0)

                indicators   = stock.get("indicators", {})
                inst_data    = stock.get("institutional_data", {})
                industry_data = stock.get("industry_data", {})

                price     = indicators.get("price", 0)
                change_1d = indicators.get("change_1d", 0)
                rsi       = indicators.get("rsi", 0)
                k_val     = indicators.get("k", 0)
                vol_ratio = indicators.get("volume_ratio", 1)
                ma5       = indicators.get("ma5", 0)
                ma20      = indicators.get("ma20", 0)

                foreign_net = inst_data.get("foreign_net", 0) or 0
                trust_net   = inst_data.get("trust_net", 0) or 0
                margin_chg  = inst_data.get("margin_change", 0) or 0

                ind_rank    = industry_data.get("rank", 0)
                ind_total   = industry_data.get("total", 0)
                ind_ret5    = industry_data.get("avg_ret_5d", 0)

                price_arrow = "▲" if change_1d >= 0 else "▼"

                # 技術面摘要
                tech_notes = []
                if ma5 and ma20 and ma5 > ma20:
                    tech_notes.append("均線多頭")
                if rsi and 45 <= rsi <= 70:
                    tech_notes.append(f"RSI {rsi:.0f}")
                if k_val and k_val > 50:
                    tech_notes.append(f"K值{k_val:.0f}")
                if vol_ratio and vol_ratio >= 1.3:
                    tech_notes.append(f"量{vol_ratio:.1f}x")
                tech_str = " | ".join(tech_notes) if tech_notes else "—"

                # 籌碼面摘要
                inst_notes = []
                if foreign_net > 0:
                    inst_notes.append(f"外資+{foreign_net:,}")
                elif foreign_net < 0:
                    inst_notes.append(f"外資{foreign_net:,}")
                if trust_net > 0:
                    inst_notes.append(f"投信+{trust_net:,}")
                elif trust_net < 0:
                    inst_notes.append(f"投信{trust_net:,}")
                if margin_chg != 0:
                    inst_notes.append(f"融資{'↑' if margin_chg>0 else '↓'}{abs(margin_chg):,}")
                inst_str = " | ".join(inst_notes) if inst_notes else "法人資料待更新"

                # 產業排名
                ind_str = f"{ind}"
                if ind_rank and ind_total:
                    ind_str += f" #{ind_rank}/{ind_total}"
                if ind_ret5:
                    ind_str += f" ({'+' if ind_ret5>=0 else ''}{ind_ret5:.1f}%)"

                msg2 += (
                    f"\n{emoji} *{i}. {sid} {name}*  {score:.0f}分/{grade}\n"
                    f"💰 現價 `{price:.1f}` {price_arrow}{abs(change_1d):.2f}%\n"
                    f"📊 技術({tech_s:.0f})｜籌碼({inst_s:.0f})｜產業({ind_s:.0f})｜基本({fund_s:.0f})\n"
                    f"📈 {tech_str}\n"
                    f"🏦 {inst_str}\n"
                    f"🏭 {ind_str}\n"
                )

            if not self.send_message(msg2):
                success = False

        # ════════════════════════════════════════════════════════
        # 訊息三：今日觀察重點（關鍵訊號摘要）
        # ════════════════════════════════════════════════════════
        key_signals = []
        for stock in stocks_to_show[:5]:
            for sig in stock.get("technical_signals", [])[:1]:
                if any(kw in sig for kw in ["黃金交叉", "爆量", "突破", "多頭排列"]):
                    key_signals.append(f"• {stock['stock_id']} {stock.get('stock_name','')} — {sig}")
            for sig in stock.get("institutional_signals", [])[:1]:
                if any(kw in sig for kw in ["大買", "持續"]):
                    key_signals.append(f"• {stock['stock_id']} {stock.get('stock_name','')} — {sig}")

        if key_signals:
            msg3 = "🔔 *今日重點訊號*\n" + "\n".join(key_signals[:6])
            if dashboard_url:
                msg3 += f"\n\n🖥️ [完整報告 Dashboard]({dashboard_url})"
            msg3 += f"\n\n_⚠️ 本報告僅供參考，不構成投資建議_"
            if not self.send_message(msg3):
                success = False

        return success

    def send_error_alert(self, error_msg: str) -> bool:
        text = (
            f"⚠️ *台股篩選系統警告*\n\n{error_msg}\n\n"
            f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        return self.send_message(text)

    def send_test_message(self) -> bool:
        text = (
            "✅ *台灣股市篩選系統* 測試訊息\n\n"
            "Telegram Bot 設定成功！\n"
            f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(text)
