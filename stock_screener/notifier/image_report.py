"""
族群資金流向圖片生成器
輸出深色主題的 PNG，格式仿照盤後大戶資金流向報告
"""

import io
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# emoji 字元範圍（CJK 字型不支援）
_EMOJI_RE = re.compile(
    "["
    u"\U0001F300-\U0001F9FF"
    u"\U00002702-\U000027B0"
    u"\U0000FE00-\U0000FE0F"  # variation selectors
    u"\U00002640-\U00002642"
    u"\U00002600-\U00002B55"
    u"\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """移除 CJK 字型不支援的 emoji，保留中英文"""
    return _EMOJI_RE.sub("", text).strip()


def _find_cjk_font() -> Optional[str]:
    """
    尋找系統上可用的 CJK 字型，回傳完整路徑或 None
    優先順序: Noto Sans CJK TC > WenQuanYi > 任何含 noto/cjk 的字型
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
        keywords = ["notosanscjk", "noto_sans_cjk", "wqy", "wenquanyi"]
        for base in ["/usr/share/fonts", "/usr/local/share/fonts",
                     os.path.expanduser("~/.fonts")]:
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for f in files:
                    if not f.lower().endswith((".ttf", ".otf", ".ttc")):
                        continue
                    if any(kw in f.lower().replace("-", "").replace("_", "")
                           for kw in keywords):
                        path = os.path.join(root, f)
                        logger.debug(f"找到字型檔案: {path}")
                        return path
    except Exception as e:
        logger.debug(f"字型搜尋失敗: {e}")
    return None


def generate_sector_flow_image(
    top_buy: List[Dict],
    top_sell: List[Dict],
    date: str,
    stocks_analyzed: int = 0,
) -> Optional[bytes]:
    """
    生成族群資金流向圖片（深色主題，仿照盤後大戶資金流向格式）

    Args:
        top_buy:  買超族群列表 [{name, emoji, net_flow_yi, avg_change_pct}, ...]
        top_sell: 賣超族群列表
        date:     報告日期字串
        stocks_analyzed: 分析股票總數

    Returns:
        PNG bytes，生成失敗回傳 None
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpa
        from matplotlib.font_manager import FontProperties

        # ── 字型 ──────────────────────────────────────────────
        font_path = _find_cjk_font()
        FP: Optional[FontProperties] = (
            FontProperties(fname=font_path) if font_path else None
        )
        matplotlib.rcParams["axes.unicode_minus"] = False
        if FP:
            matplotlib.rcParams["font.family"] = [FP.get_name(), "DejaVu Sans"]

        # ── 顏色定義 ──────────────────────────────────────────
        C = dict(
            bg      = "#0d1117",
            hdr_bg  = "#161b22",
            buy_hdr = "#7f1d1d",   # 買超標題背景（深紅）
            sell_hdr= "#14532d",   # 賣超標題背景（深綠）
            col_hdr = "#1f2937",   # 欄位標頭背景
            row_a   = "#0d1117",   # 奇數行背景
            row_b   = "#161b22",   # 偶數行背景
            white   = "#f0f6fc",   # 主文字
            gold    = "#fbbf24",   # 標題金色 / 第一名排名
            silver  = "#e5e7eb",   # 第二名排名
            bronze  = "#d97706",   # 第三名排名
            sub     = "#8b949e",   # 次要文字
            border  = "#30363d",   # 邊框
            buy_val = "#fca5a5",   # 買超金額
            sell_val= "#86efac",   # 賣超金額
            pos     = "#4ade80",   # 正漲幅
            neg     = "#f87171",   # 負漲幅
        )

        # ── Layout（英寸）────────────────────────────────────
        FW     = 13.0    # 圖片寬度
        TITLE  = 1.5     # 標題區高度
        SEC    = 0.52    # 族群標頭高度
        COL_H  = 0.42    # 欄位標頭高度
        ROW    = 0.50    # 每筆資料行高度
        FOOT   = 0.32    # 頁尾高度
        GAP    = 0.10    # 中間間距（英寸換算後為 0）

        n = max(len(top_buy), len(top_sell), 1)
        FH = TITLE + SEC + COL_H + n * ROW + FOOT

        fig = plt.figure(figsize=(FW, FH), facecolor=C["bg"], dpi=150)

        # 英寸 → figure 座標比例
        def fh(inches: float) -> float:
            return inches / FH

        # ── 各區域 bottom y 座標（figure 標準化）────────────
        TITLE_BOT = 1 - fh(TITLE)
        SEC_BOT   = TITLE_BOT - fh(SEC)
        COL_BOT   = SEC_BOT - fh(COL_H)

        def row_bot(i: int) -> float:
            return COL_BOT - fh((i + 1) * ROW)

        FOOT_CEN = fh(FOOT) / 2

        # ── 通用繪圖函式 ──────────────────────────────────────
        def add_rect(x, y, w, h_in, color, zorder=1, radius=0.0):
            if radius > 0:
                r = mpa.FancyBboxPatch(
                    (x, y), w, fh(h_in),
                    boxstyle=f"round,pad={radius}",
                    transform=fig.transFigure,
                    facecolor=color, edgecolor="none", zorder=zorder,
                )
            else:
                r = mpa.Rectangle(
                    (x, y), w, fh(h_in),
                    transform=fig.transFigure,
                    facecolor=color, edgecolor="none", zorder=zorder,
                )
            fig.add_artist(r)

        def add_text(x, y, s, size=11, color=None, weight="normal",
                     ha="center", va="center", zorder=5):
            color = color or C["white"]
            kw: dict = dict(
                transform=fig.transFigure,
                fontsize=size, color=color,
                fontweight=weight, ha=ha, va=va, zorder=zorder,
            )
            if FP:
                kw["fontproperties"] = FP
            fig.text(x, y, s, **kw)

        # ── 標題區 ────────────────────────────────────────────
        add_rect(0, TITLE_BOT, 1.0, TITLE, C["hdr_bg"], zorder=1, radius=0.005)

        t_cen = TITLE_BOT + fh(TITLE) / 2
        add_text(0.5, t_cen + fh(0.3), "盤後族群資金流向",
                 size=26, color=C["gold"], weight="bold")
        add_text(0.5, t_cen - fh(0.1), "三大法人（外資＋投信＋自營商）在買什麼？賣什麼？",
                 size=12, color=C["white"])
        add_text(0.5, t_cen - fh(0.48),
                 f"{date}　|　分析 {stocks_analyzed} 支主題股票",
                 size=10, color=C["sub"])

        # ── 兩欄面板 ──────────────────────────────────────────
        LX, LW = 0.010, 0.486
        RX, RW = 0.504, 0.486

        def draw_panel(px: float, pw: float, items: List[Dict], is_buy: bool):
            sec_color = C["buy_hdr"] if is_buy else C["sell_hdr"]
            val_color = C["buy_val"] if is_buy else C["sell_val"]
            arrow     = "▲" if is_buy else "▼"
            side_label = (
                f"法人買超  TOP{len(items)}  {arrow}"
                if is_buy else
                f"法人賣超  TOP{len(items)}  {arrow}"
            )

            # 族群標頭（紅/綠色背景）
            add_rect(px, SEC_BOT, pw, SEC, sec_color, zorder=2)
            add_text(px + pw / 2, SEC_BOT + fh(SEC) / 2, side_label,
                     size=14, color=C["white"], weight="bold")

            # 欄位標頭
            add_rect(px, COL_BOT, pw, COL_H, C["col_hdr"], zorder=2)

            # 欄位定義: (x比例, 欄標題, 資料對齊, 欄標題對齊)
            # 排名8% | 族群45% | 大戶差(億)30% | 漲幅17%
            col_defs = [
                (0.040, "排名",      "center", "center"),
                (0.090, "族群",      "left",   "left"),
                (0.800, "大戶差(億)", "right",  "right"),
                (0.975, "漲幅",      "right",  "right"),
            ]
            for ratio, label, _, align in col_defs:
                add_text(px + pw * ratio, COL_BOT + fh(COL_H) / 2,
                         label, size=10, color=C["sub"], ha=align)

            # 資料列
            rank_colors = [C["gold"], C["silver"], C["bronze"]]

            for i, item in enumerate(items):
                ry = row_bot(i)
                add_rect(px, ry, pw, ROW,
                         C["row_a"] if i % 2 == 0 else C["row_b"], zorder=2)
                cy = ry + fh(ROW) / 2

                # 排名數字
                rc = rank_colors[i] if i < 3 else "#9ca3af"
                add_text(px + pw * 0.040, cy, str(i + 1),
                         size=14, color=rc, weight="bold", ha="center")

                # 族群名稱（去除 emoji，CJK 字型不支援）
                name = _strip_emoji(f"{item.get('emoji', '')}{item['name']}")
                add_text(px + pw * 0.090, cy, name,
                         size=11, color=C["white"], ha="left")

                # 大戶差（億）
                flow = item["net_flow_yi"]
                f_str = f"+{flow:.2f}億" if flow > 0 else f"{flow:.2f}億"
                add_text(px + pw * 0.800, cy, f_str,
                         size=11, color=val_color, weight="bold", ha="right")

                # 漲幅
                chg = item["avg_change_pct"]
                chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
                add_text(px + pw * 0.975, cy, chg_str,
                         size=11, color=C["pos"] if chg >= 0 else C["neg"],
                         ha="right")

            # 填滿空列（讓兩欄等高）
            for i in range(len(items), n):
                ry = row_bot(i)
                add_rect(px, ry, pw, ROW,
                         C["row_a"] if i % 2 == 0 else C["row_b"], zorder=2)

        draw_panel(LX, LW, top_buy,  is_buy=True)
        draw_panel(RX, RW, top_sell, is_buy=False)

        # ── 頁尾 ──────────────────────────────────────────────
        add_text(0.5, FOOT_CEN,
                 "本報告基於三大法人買賣超資料推算，僅供參考，不構成投資建議",
                 size=9, color=C["sub"])

        # ── 輸出 ──────────────────────────────────────────────
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150,
                    bbox_inches="tight", facecolor=C["bg"], edgecolor="none")
        buf.seek(0)
        plt.close(fig)
        return buf.read()

    except Exception as e:
        logger.error(f"圖片生成失敗: {e}", exc_info=True)
        return None
