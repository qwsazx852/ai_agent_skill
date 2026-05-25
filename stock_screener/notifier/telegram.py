"""
Telegram Bot 通知模組 - 主題概念股報告版

報告格式:
- 訊息一：今日大盤氣氛 + 熱門概念主題 TOP5
- 訊息二：TOP 15 精選股（依主題分群顯示）
- 訊息三：今日重點訊號
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

GRADE_EMOJI = {
    "A+": "🌟", "A": "⭐", "B+": "✅",
    "B": "🔵", "C+": "🟡", "C": "🟠", "D": "🔴",
}


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
        hot_themes: Optional[List[Dict]] = None,
    ) -> bool:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        hot_themes = hot_themes or []
        success = True

        # ── 判斷今日大盤氣氛 ──────────────────────────────────
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

        # ════════════════════════════════════════════════════
        # 訊息一：今日總覽 + 熱門概念主題
        # ════════════════════════════════════════════════════
        msg1 = (
            f"🇹🇼 *台股每日篩選報告*\n"
            f"📅 {date}  {datetime.now().strftime('%H:%M')}\n"
            f"{'─' * 28}\n"
            f"{market_mood}\n\n"
        )

        # 優先顯示熱門概念主題
        if hot_themes:
            msg1 += "🔥 *今日熱門概念主題*\n"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            for i, theme in enumerate(hot_themes[:5]):
                ret5 = theme.get("avg_ret_5d", 0)
                ret1 = theme.get("avg_ret_1d", 0)
                arrow = "▲" if ret5 >= 0 else "▼"
                count = theme.get("active_count", 0)
                emoji = theme.get("emoji", "")
                name = theme.get("name", "")
                msg1 += (
                    f"{medals[i]} {emoji}{name}  "
                    f"{arrow}{abs(ret5):.1f}%(5日)  "
                    f"今日{'+' if ret1>=0 else ''}{ret1:.1f}%  "
                    f"({count}檔)\n"
                )
        elif hot_industries:
            # fallback 到傳統產業
            msg1 += "🏭 *今日強勢產業*\n"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            for i, ind in enumerate(hot_industries[:5]):
                ret5 = ind.get("avg_ret_5d", 0)
                ret1 = ind.get("avg_ret_1d", 0)
                arrow = "▲" if ret5 >= 0 else "▼"
                msg1 += (
                    f"{medals[i]} {ind['industry']}  "
                    f"{arrow}{abs(ret5):.1f}%(5日)  "
                    f"今日{'+' if ret1>=0 else ''}{ret1:.1f}%\n"
                )

        if industry_signals:
            msg1 += "\n🔄 *產業輪動觀察*\n"
            for sig in industry_signals[:2]:
                msg1 += f"• {sig}\n"

        if not self.send_message(msg1):
            success = False

        # ════════════════════════════════════════════════════
        # 訊息二：TOP 15 精選股（依主題分群）
        # ════════════════════════════════════════════════════
        stocks_to_show = [
            s for s in top_stocks
            if s.get("grade") in ["A+", "A", "B+", "B"]
        ][:15]

        if stocks_to_show:
            # 依主題分群
            theme_groups: Dict[str, List[Dict]] = {}
            no_theme: List[Dict] = []

            for stock in stocks_to_show:
                themes = stock.get("themes", [])
                if themes:
                    primary_theme = themes[0]
                    if primary_theme not in theme_groups:
                        theme_groups[primary_theme] = []
                    theme_groups[primary_theme].append(stock)
                else:
                    no_theme.append(stock)

            msg2 = f"📋 *精選股 TOP{len(stocks_to_show)}*\n{'─' * 28}\n"
            rank = 1

            # 依熱門主題排序輸出
            hot_theme_ids = [t.get("theme_id", "") for t in hot_themes]
            sorted_theme_ids = sorted(
                theme_groups.keys(),
                key=lambda t: hot_theme_ids.index(t) if t in hot_theme_ids else 999
            )

            for theme_id in sorted_theme_ids:
                stocks_in_theme = theme_groups[theme_id]
                # 找主題標籤
                theme_label = f"📌 *{theme_id}*"
                for t in hot_themes:
                    if t.get("theme_id") == theme_id:
                        theme_label = f"{t.get('emoji','')} *{t.get('name','')} 概念*"
                        break

                msg2 += f"\n{theme_label}\n"
                for stock in stocks_in_theme:
                    msg2 += self._format_stock_line(rank, stock)
                    rank += 1

            if no_theme:
                msg2 += "\n📊 *其他精選*\n"
                for stock in no_theme:
                    msg2 += self._format_stock_line(rank, stock)
                    rank += 1

            if not self.send_message(msg2):
                success = False

        # ════════════════════════════════════════════════════
        # 訊息三：今日重點訊號
        # ════════════════════════════════════════════════════
        key_signals = []
        for stock in stocks_to_show[:8]:
            sid = stock["stock_id"]
            name = stock.get("stock_name", sid)
            for sig in stock.get("technical_signals", [])[:2]:
                if any(kw in sig for kw in ["黃金交叉", "爆量", "突破", "多頭排列", "形態"]):
                    key_signals.append(f"• `{sid}` {name} — {sig}")
            for sig in stock.get("institutional_signals", [])[:1]:
                if any(kw in sig for kw in ["大買", "持續"]):
                    key_signals.append(f"• `{sid}` {name} — {sig}")

        if key_signals:
            msg3 = "🔔 *今日重點訊號*\n" + "\n".join(key_signals[:8])
            if dashboard_url:
                msg3 += f"\n\n🖥️ [完整報告]({dashboard_url})"
            msg3 += f"\n\n_⚠️ 本報告僅供參考，不構成投資建議_"
            if not self.send_message(msg3):
                success = False

        return success

    def _format_stock_line(self, rank: int, stock: Dict) -> str:
        """格式化單一股票顯示行"""
        sid       = stock.get("stock_id", "")
        name      = stock.get("stock_name", sid)[:5]
        score     = stock.get("composite_score", 0)
        grade     = stock.get("grade", "")
        emoji     = GRADE_EMOJI.get(grade, "")
        tech_s    = stock.get("technical_score", 0)
        inst_s    = stock.get("institutional_score", 0)
        indicators = stock.get("indicators", {})
        inst_data  = stock.get("institutional_data", {})

        price     = indicators.get("price", 0)
        change_1d = indicators.get("change_1d", 0)
        rsi       = indicators.get("rsi", 0)
        vol_ratio = indicators.get("volume_ratio", 1)
        ma5       = indicators.get("ma5", 0)
        ma20      = indicators.get("ma20", 0)

        foreign_net = int(inst_data.get("foreign_net", 0) or 0)
        trust_net   = int(inst_data.get("trust_net", 0) or 0)

        price_arrow = "▲" if change_1d >= 0 else "▼"

        # 技術摘要
        tech_notes = []
        if ma5 and ma20 and ma5 > ma20:
            tech_notes.append("多頭")
        if rsi and 45 <= rsi <= 72:
            tech_notes.append(f"RSI{rsi:.0f}")
        if vol_ratio and vol_ratio >= 1.5:
            tech_notes.append(f"量{vol_ratio:.1f}x")
        patterns = stock.get("patterns", [])
        if patterns:
            p = patterns[0].replace("📐 形態: ", "").replace("📐", "").strip()
            tech_notes.append(p[:6])
        tech_str = "|".join(tech_notes) if tech_notes else "—"

        # 籌碼摘要
        inst_parts = []
        if foreign_net > 0:
            inst_parts.append(f"外資+{foreign_net:,}")
        elif foreign_net < -500:
            inst_parts.append(f"外資{foreign_net:,}")
        if trust_net > 0:
            inst_parts.append(f"投信+{trust_net:,}")
        inst_str = " ".join(inst_parts) if inst_parts else "—"

        return (
            f"{emoji}`{rank:>2}. {sid} {name}`"
            f" {score:.0f}/{grade}"
            f" {price_arrow}{abs(change_1d):.1f}%\n"
            f"    技{tech_s:.0f} 籌{inst_s:.0f}｜{tech_str}\n"
            f"    {inst_str}\n"
        )

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
