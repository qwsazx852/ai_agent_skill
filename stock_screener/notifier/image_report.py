"""
族群資金流向圖片生成器 — 漫畫 / Manga 風格
輸出卡通漫畫感 PNG，仿照盤後大戶資金流向版面
"""

import io
import logging
import math
import os
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── emoji 字元範圍（CJK 字型不支援）──────────────────────────────────────
# 只保留 BMP 基本字元（U+0000–U+FFFF 中的非符號部分）及中英數字
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FFFF"   # Supplemental symbols, emoji, mahjong…
    "\U00002600-\U000027BF"   # Misc symbols, dingbats
    "\U0000FE00-\U0000FE0F"   # Variation selectors
    "\U0000200D"               # Zero-width joiner
    "\U000023CF"               # Eject (correct 8-digit form)
    "\U000023E9-\U000023F3"   # Clock/media symbols
    "\U000023F8-\U000023FA"
    "\U000025AA-\U000025FE"   # Geometric shapes
    "\U00002702-\U000027B0"   # Dingbats
    "\U00002B00-\U00002BFF"   # Misc symbols and arrows
    "\U00003030"
    "\U0000303D"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """移除 CJK 字型不支援的 emoji，保留中英文"""
    return _EMOJI_RE.sub("", text).strip()


def _find_cjk_font() -> Optional[str]:
    """
    尋找系統上可用的 CJK 字型，回傳完整路徑或 None
    優先順序: Noto Sans CJK TC > WenQuanYi > 任何含 noto/cjk/wqy 的字型
    """
    try:
        import matplotlib.font_manager as fm

        # 先讓 matplotlib 重新掃描（確保剛安裝的字型被識別）
        try:
            fm._load_fontmanager(try_read_cache=False)
        except Exception:
            pass

        preferred = [
            "Noto Sans CJK TC", "Noto Sans TC",
            "Noto Sans CJK SC", "Noto Sans CJK JP",
            "WenQuanYi Zen Hei", "AR PL UMing TW",
        ]
        name_to_path = {f.name: f.fname for f in fm.fontManager.ttflist}
        for name in preferred:
            if name in name_to_path:
                logger.debug(f"找到中文字型: {name}")
                return name_to_path[name]

        # 搜尋字型目錄（GitHub Actions / Linux 路徑）
        keywords = ["notosanscjk", "noto_sans_cjk", "wqy", "wenquanyi", "cjk"]
        for base in ["/usr/share/fonts", "/usr/local/share/fonts",
                     os.path.expanduser("~/.fonts")]:
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for f in files:
                    if not f.lower().endswith((".ttf", ".otf", ".ttc")):
                        continue
                    fl = f.lower().replace("-", "").replace("_", "")
                    if any(kw in fl for kw in keywords):
                        path = os.path.join(root, f)
                        logger.debug(f"找到字型檔案: {path}")
                        return path
    except Exception as e:
        logger.debug(f"字型搜尋失敗: {e}")
    return None


def _generate_analysis(
    top_buy: List[Dict],
    top_sell: List[Dict],
) -> Tuple[List[str], str]:
    """
    根據買超/賣超資料自動生成分析觀察重點與結語

    Returns:
        (bullets, quote) — bullets 有 4 條，quote 為一句話
    """
    # ── Bullet 1: 大戶資金聚焦（前三買超） ──────────────────────────
    buy_names_3 = "、".join(
        _strip_emoji(item.get("name", "")) for item in top_buy[:3]
    ) if top_buy else "—"
    b1 = f"大戶資金聚焦：{buy_names_3}，資金明顯流入"

    # ── Bullet 2: 買超前三強平均漲幅 ────────────────────────────────
    if top_buy:
        buy_total = sum(item.get("net_flow_yi", 0) for item in top_buy)
        top3_changes = [
            item.get("avg_change_pct", 0) for item in top_buy[:3]
        ]
        avg_chg = sum(top3_changes) / len(top3_changes) if top3_changes else 0
        b2 = (
            f"買超前三強平均漲幅 +{avg_chg:.2f}%，"
            f"{buy_total:.0f}億強勢入場"
        )
    else:
        b2 = "買超資料暫無，請關注後續法人動向"

    # ── Bullet 3: 賣超前兩名 ─────────────────────────────────────────
    sell_names_2 = "、".join(
        _strip_emoji(item.get("name", "")) for item in top_sell[:2]
    ) if top_sell else "—"
    b3 = f"{sell_names_2} 遭法人調節，資金轉向上游題材"

    # ── Bullet 4: 市場輪動判斷 ─────────────────────────────────────────
    any_high = any(
        item.get("avg_change_pct", 0) > 3.0 for item in top_buy
    )
    if any_high:
        b4 = "市場輪動加速，聚焦高成長與低基期標的"
    else:
        b4 = "族群分化明顯，選股優於選市"

    # ── Quote ───────────────────────────────────────────────────────────
    quote = "資金不會說謊，大戶的選擇，就是下一波趨勢的線索！"

    return [b1, b2, b3, b4], quote


def generate_sector_flow_image(
    top_buy: List[Dict],
    top_sell: List[Dict],
    date: str,
    stocks_analyzed: int = 0,
) -> Optional[bytes]:
    """
    生成漫畫/Manga 風格的族群資金流向圖片

    Args:
        top_buy:         買超族群列表 [{name, emoji, net_flow_yi, avg_change_pct}, ...]
        top_sell:        賣超族群列表
        date:            報告日期字串
        stocks_analyzed: 分析股票總數

    Returns:
        PNG bytes，生成失敗回傳 None
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpa
        import matplotlib.patheffects as pe
        from matplotlib.font_manager import FontProperties
        from matplotlib.lines import Line2D

        # ── 字型 ──────────────────────────────────────────────────────────
        font_path = _find_cjk_font()
        FP: Optional[FontProperties] = (
            FontProperties(fname=font_path) if font_path else None
        )
        matplotlib.rcParams["axes.unicode_minus"] = False
        if FP:
            matplotlib.rcParams["font.family"] = [FP.get_name(), "DejaVu Sans"]

        # ── 漫畫配色 ──────────────────────────────────────────────────────
        C = {
            'bg':           '#0d0d1a',   # very dark navy
            'title_bg':     '#1a1a3a',   # dark purple-blue for title area
            'title_line':   '#ffdd00',   # yellow gold for speed lines / decorations
            'buy_hdr':      '#cc0022',   # saturated red for buy header
            'sell_hdr':     '#007744',   # saturated green for sell header
            'buy_border':   '#ff3355',   # bright red border
            'sell_border':  '#00dd66',   # bright green border
            'buy_bg':       '#1a0508',   # dark red tint background
            'sell_bg':      '#051a08',   # dark green tint background
            'col_hdr':      '#1f2937',   # dark gray for column header row
            'row_a':        '#0d0d1a',   # same as bg
            'row_b':        '#151525',   # slightly lighter for alternating rows
            'white':        '#ffffff',
            'gold':         '#ffd700',
            'silver':       '#c0c0c0',
            'bronze':       '#cd7f32',
            'sub':          '#8b8ba0',
            'buy_val':      '#ff6b6b',   # light red for buy amounts
            'sell_val':     '#69ff94',   # light green for sell amounts
            'pos':          '#4ade80',   # green for positive % change
            'neg':          '#f87171',   # red for negative % change
            'analysis_bg':  '#1e1a00',   # dark yellow tint for analysis bg
            'analysis_brd': '#ffdd00',   # yellow border for analysis section
            'quote_bg':     '#1a1a3a',   # same as title bg for quote
            'quote_brd':    '#ff9900',   # orange for quote border
        }

        # ── Layout（英寸）─────────────────────────────────────────────────
        FW       = 14.0    # 圖片寬度（英寸）
        TITLE_H  = 1.90    # 標題區高度
        SEC_H    = 0.55    # 族群標頭高度
        COL_H    = 0.42    # 欄位標頭高度
        ROW_H    = 0.50    # 每筆資料行高度
        ANALYSIS_H = 2.0   # 分析區高度
        FOOT_H   = 0.30    # 頁尾高度

        n = max(len(top_buy), len(top_sell), 1)
        FH = TITLE_H + SEC_H + COL_H + n * ROW_H + ANALYSIS_H + FOOT_H

        fig = plt.figure(figsize=(FW, FH), facecolor=C['bg'], dpi=150)

        # 英寸 → figure 正規化座標
        def fh(inches: float) -> float:
            return inches / FH

        # ── 各區域邊界（figure 座標，y=0 在底部） ────────────────────────
        title_bot   = 1.0 - fh(TITLE_H)
        sec_bot     = title_bot - fh(SEC_H)
        col_bot     = sec_bot - fh(COL_H)

        def row_bot(i: int) -> float:
            return col_bot - fh((i + 1) * ROW_H)

        analysis_bot = row_bot(n - 1) - fh(ANALYSIS_H)
        foot_cen     = fh(FOOT_H) / 2

        # ── 通用繪圖工具 ──────────────────────────────────────────────────
        def add_rect(x, y, w, h_inch, color, zorder=1, edgecolor="none", lw=0,
                     radius=0.0):
            if radius > 0:
                patch = mpa.FancyBboxPatch(
                    (x, y), w, fh(h_inch),
                    boxstyle=f"round,pad={radius}",
                    transform=fig.transFigure,
                    facecolor=color, edgecolor=edgecolor,
                    linewidth=lw, zorder=zorder,
                )
            else:
                patch = mpa.Rectangle(
                    (x, y), w, fh(h_inch),
                    transform=fig.transFigure,
                    facecolor=color, edgecolor=edgecolor,
                    linewidth=lw, zorder=zorder,
                )
            fig.add_artist(patch)
            return patch

        def add_text(x, y, s, size=11, color=None, weight="normal",
                     ha="center", va="center", zorder=5,
                     stroke=False, stroke_lw=3, stroke_fg=None):
            color = color or C['white']
            kw: dict = dict(
                transform=fig.transFigure,
                fontsize=size, color=color,
                fontweight=weight, ha=ha, va=va, zorder=zorder,
            )
            if FP:
                kw["fontproperties"] = FP
            txt = fig.text(x, y, s, **kw)
            if stroke:
                fg = stroke_fg or C['bg']
                txt.set_path_effects([
                    pe.withStroke(linewidth=stroke_lw, foreground=fg)
                ])
            return txt

        # ── ① 標題區背景 ─────────────────────────────────────────────────
        add_rect(0, title_bot, 1.0, TITLE_H, C['title_bg'], zorder=1)

        # ── ② 速度線（漫畫感） ─────────────────────────────────────────
        for angle_deg in range(-160, -20, 10):
            rad = math.radians(angle_deg)
            x1 = 0.5 + 0.05 * math.cos(rad)
            y1 = 1.0 + 0.05 * math.sin(rad)
            x2 = 0.5 + 0.28 * math.cos(rad)
            y2 = 1.0 + 0.28 * math.sin(rad)
            line = Line2D(
                [x1, x2], [y1, y2],
                transform=fig.transFigure,
                color=C['title_line'], alpha=0.20, linewidth=0.8, zorder=2,
            )
            fig.add_artist(line)

        # ── ③ 標題裝飾線（左右各一） ──────────────────────────────────
        deco_y = title_bot + fh(TITLE_H) * 0.50
        deco_w = 0.16
        for x_start, x_end in [(0.04, 0.04 + deco_w), (0.96 - deco_w, 0.96)]:
            dline = Line2D(
                [x_start, x_end], [deco_y, deco_y],
                transform=fig.transFigure,
                color=C['title_line'], alpha=0.85, linewidth=1.5, zorder=3,
            )
            fig.add_artist(dline)

        # ── ④ 標題文字 ────────────────────────────────────────────────
        t_cen = title_bot + fh(TITLE_H) / 2
        add_text(
            0.5, t_cen + fh(0.38),
            "盤後族群資金流向",
            size=28, color=C['gold'], weight="bold", zorder=5,
            stroke=True, stroke_lw=4, stroke_fg=C['bg'],
        )
        add_text(
            0.5, t_cen - fh(0.08),
            "三大法人在買什麼？賣什麼？",
            size=13, color=C['white'], zorder=5,
            stroke=True, stroke_lw=2, stroke_fg=C['bg'],
        )
        add_text(
            0.5, t_cen - fh(0.48),
            f"{date}　|　分析 {stocks_analyzed} 支主題股票",
            size=10, color=C['sub'], zorder=5,
        )

        # ── ⑤ 兩欄面板 ───────────────────────────────────────────────
        MARGIN = 0.010
        GAP    = 0.008
        LX = MARGIN
        LW = 0.5 - MARGIN - GAP / 2
        RX = 0.5 + GAP / 2
        RW = 0.5 - MARGIN - GAP / 2

        # Panel 外框高度 = sec + col + n 列 (英寸)
        panel_h_inch = SEC_H + COL_H + n * ROW_H

        def draw_panel(px: float, pw: float, items: List[Dict], is_buy: bool):
            sec_color   = C['buy_hdr']    if is_buy else C['sell_hdr']
            bg_color    = C['buy_bg']     if is_buy else C['sell_bg']
            border_c    = C['buy_border'] if is_buy else C['sell_border']
            val_color   = C['buy_val']    if is_buy else C['sell_val']
            arrow       = "▲" if is_buy else "▼"
            side_label  = (
                f"法人買超 TOP{len(items)} {arrow}"
                if is_buy else
                f"法人賣超 TOP{len(items)} {arrow}"
            )

            # 面板資料區底色
            add_rect(
                px, row_bot(n - 1), pw, panel_h_inch,
                bg_color, zorder=2,
            )

            # 漫畫感外框（FancyBboxPatch）
            frame = mpa.FancyBboxPatch(
                (px, row_bot(n - 1)),
                pw, fh(panel_h_inch),
                boxstyle="round,pad=0.005",
                transform=fig.transFigure,
                facecolor="none",
                edgecolor=border_c,
                linewidth=2.5, zorder=8,
            )
            fig.add_artist(frame)

            # 族群標頭（紅/綠背景）
            add_rect(px, sec_bot, pw, SEC_H, sec_color, zorder=3)
            add_text(
                px + pw / 2, sec_bot + fh(SEC_H) / 2,
                side_label, size=14, color=C['white'], weight="bold", zorder=5,
            )

            # 欄位標頭
            add_rect(px, col_bot, pw, COL_H, C['col_hdr'], zorder=3)
            col_defs = [
                (0.055, "排名",      "center"),
                (0.105, "族群",      "left"),
                (0.790, "大戶差(億)", "right"),
                (0.980, "漲幅",      "right"),
            ]
            for ratio, label, align in col_defs:
                add_text(
                    px + pw * ratio,
                    col_bot + fh(COL_H) / 2,
                    label, size=10, color=C['sub'], ha=align, zorder=5,
                )

            # 資料列
            rank_badge_colors = [C['gold'], C['silver'], C['bronze']]

            # Radius for rank badge circle — account for aspect ratio so it's round
            badge_r = 0.022 / (FH / FW)

            for i, item in enumerate(items):
                ry  = row_bot(i)
                cy  = ry + fh(ROW_H) / 2

                # 行底色
                add_rect(
                    px, ry, pw, ROW_H,
                    C['row_a'] if i % 2 == 0 else C['row_b'],
                    zorder=2,
                )

                # ── 排名徽章圓圈 ─────────────────────────────────
                badge_color = rank_badge_colors[i] if i < 3 else '#2d3748'
                circle = mpa.Circle(
                    (px + pw * 0.055, cy),
                    radius=badge_r,
                    transform=fig.transFigure,
                    facecolor=badge_color, edgecolor='none', zorder=6,
                )
                fig.add_artist(circle)

                # 排名數字
                txt_color = C['bg'] if i < 3 else C['silver']
                add_text(
                    px + pw * 0.055, cy,
                    str(i + 1),
                    size=12, color=txt_color, weight="bold",
                    ha="center", va="center", zorder=7,
                )

                # 族群名稱
                raw_name = f"{item.get('emoji', '')}{item.get('name', '')}"
                name = _strip_emoji(raw_name)
                add_text(
                    px + pw * 0.105, cy,
                    name, size=11, color=C['white'], ha="left", zorder=5,
                )

                # 大戶差（億）
                flow = item.get("net_flow_yi", 0)
                f_str = f"+{flow:.2f}億" if flow >= 0 else f"{flow:.2f}億"
                add_text(
                    px + pw * 0.790, cy,
                    f_str, size=12, color=val_color, weight="bold",
                    ha="right", zorder=5,
                )

                # 漲幅
                chg = item.get("avg_change_pct", 0)
                chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
                add_text(
                    px + pw * 0.980, cy,
                    chg_str, size=11,
                    color=C['pos'] if chg >= 0 else C['neg'],
                    ha="right", zorder=5,
                )

            # 填滿空列（讓兩欄等高）
            for i in range(len(items), n):
                ry = row_bot(i)
                add_rect(
                    px, ry, pw, ROW_H,
                    C['row_a'] if i % 2 == 0 else C['row_b'],
                    zorder=2,
                )

        draw_panel(LX, LW, top_buy,  is_buy=True)
        draw_panel(RX, RW, top_sell, is_buy=False)

        # ── ⑥ 分析觀察區 ────────────────────────────────────────────
        bullets, quote = _generate_analysis(top_buy, top_sell)

        # 左 65% 分析面板 / 右 35% 引言框
        ANALY_X  = MARGIN
        ANALY_W  = 0.62 - MARGIN
        QUOTE_X  = 0.63
        QUOTE_W  = 0.37 - MARGIN

        # 分析面板底色與外框
        analy_patch = mpa.FancyBboxPatch(
            (ANALY_X, analysis_bot),
            ANALY_W, fh(ANALYSIS_H),
            boxstyle="round,pad=0.005",
            transform=fig.transFigure,
            facecolor=C['analysis_bg'],
            edgecolor=C['analysis_brd'],
            linewidth=2, zorder=4,
        )
        fig.add_artist(analy_patch)

        # 分析面板標頭
        analy_hdr_y = analysis_bot + fh(ANALYSIS_H) - fh(0.32)
        add_text(
            ANALY_X + 0.015,
            analy_hdr_y + fh(0.16),
            "分析觀察",
            size=13, color=C['gold'], weight="bold",
            ha="left", zorder=6,
        )

        # 子彈點
        bullet_start_y = analy_hdr_y - fh(0.10)
        bullet_step    = fh(0.40)
        for idx, b in enumerate(bullets):
            by = bullet_start_y - idx * bullet_step
            add_text(
                ANALY_X + 0.018, by,
                f"◆ {_strip_emoji(b)}",
                size=11, color=C['white'], ha="left", zorder=6,
            )

        # 引言框底色與外框
        quote_patch = mpa.FancyBboxPatch(
            (QUOTE_X, analysis_bot),
            QUOTE_W, fh(ANALYSIS_H),
            boxstyle="round,pad=0.005",
            transform=fig.transFigure,
            facecolor=C['quote_bg'],
            edgecolor=C['quote_brd'],
            linewidth=2, zorder=4,
        )
        fig.add_artist(quote_patch)

        # 大引號裝飾
        add_text(
            QUOTE_X + QUOTE_W * 0.12,
            analysis_bot + fh(ANALYSIS_H) - fh(0.28),
            "66",   # decorative open-quote using ASCII double-6 style
            size=28, color=C['quote_brd'], weight="bold", ha="center", zorder=6,
        )

        # 引言文字（手動換行，每行約 16 字）
        q_stripped = _strip_emoji(quote)
        chunk = 16
        lines = [
            q_stripped[i:i + chunk]
            for i in range(0, len(q_stripped), chunk)
        ]
        q_total_h = len(lines) * fh(0.38)
        q_start_y = analysis_bot + fh(ANALYSIS_H) / 2 + q_total_h / 2 - fh(0.18)
        for li, ln in enumerate(lines):
            add_text(
                QUOTE_X + QUOTE_W / 2,
                q_start_y - li * fh(0.38),
                ln, size=12, color=C['white'],
                ha="center", zorder=6,
            )

        # ── ⑦ 頁尾 ───────────────────────────────────────────────────
        add_text(
            0.5, foot_cen,
            "本報告基於三大法人買賣超資料推算，僅供參考，不構成投資建議",
            size=9, color=C['sub'],
        )

        # ── ⑧ 輸出 PNG ─────────────────────────────────────────────
        buf = io.BytesIO()
        plt.savefig(
            buf, format="png", dpi=150,
            bbox_inches="tight",
            facecolor=C['bg'], edgecolor="none",
        )
        buf.seek(0)
        plt.close(fig)
        return buf.read()

    except Exception as e:
        logger.error(f"圖片生成失敗: {e}", exc_info=True)
        return None
