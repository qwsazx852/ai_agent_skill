"""
族群資金流向圖片生成器 — Pillow 高品質版
使用 PIL 實現漸層、陰影、圓角面板，仿照盤後大戶資金流向風格
"""

import io
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# ── emoji 剝離（程式化建立，避免 Unicode escape 問題）────────────────────
_EMOJI_RANGES = [
    (0x1F300, 0x1F9FF), (0x1FA00, 0x1FAFF),
    (0x2600,  0x27BF),  (0xFE00,  0xFE0F),
    (0x200D,  0x200D),  (0x23CF,  0x23CF),
    (0x23E9,  0x23FA),  (0x25AA,  0x25FE),
    (0x2B00,  0x2BFF),  (0x3030,  0x303D),
]
_EMOJI_RE = re.compile(
    "[" + "".join(
        chr(lo) if lo == hi else f"{chr(lo)}-{chr(hi)}"
        for lo, hi in _EMOJI_RANGES
    ) + "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


# ── 字型載入 ──────────────────────────────────────────────────────────────

def _find_font(bold: bool = False) -> Optional[str]:
    """
    搜尋系統 CJK 字型，優先找 Bold/Heavy 字重
    回傳 TTF/OTF/TTC 完整路徑，找不到回傳 None
    """
    try:
        import matplotlib.font_manager as fm
        try:
            fm._load_fontmanager(try_read_cache=False)
        except Exception:
            pass
        name_to = {f.name: f.fname for f in fm.fontManager.ttflist}

        if bold:
            for name in ["Noto Sans CJK TC", "Noto Sans TC",
                         "Noto Sans CJK SC", "Noto Sans CJK JP"]:
                if name in name_to:
                    return name_to[name]
        # fallback to regular
        for name in ["Noto Sans CJK TC", "Noto Sans TC",
                     "Noto Sans CJK SC", "WenQuanYi Zen Hei", "AR PL UMing TW"]:
            if name in name_to:
                return name_to[name]
    except Exception:
        pass

    # 直接掃目錄
    bold_kw  = ["bold", "heavy", "black", "medium"] if bold else []
    base_kw  = ["notosanscjk", "noto_sans_cjk", "wqy", "wenquanyi"]
    for base in ["/usr/share/fonts", "/usr/local/share/fonts",
                 os.path.expanduser("~/.fonts")]:
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for f in files:
                if not f.lower().endswith((".ttf", ".otf", ".ttc")):
                    continue
                fl = f.lower().replace("-", "").replace("_", "")
                is_cjk = any(k in fl for k in base_kw)
                is_bold = any(k in fl for k in bold_kw)
                if is_cjk and (not bold or is_bold):
                    return os.path.join(root, f)
    return None


class _Fonts:
    """按尺寸快取 ImageFont，自動回退到 default"""
    def __init__(self):
        self._bold_path   = _find_font(bold=True)
        self._regular_path = _find_font(bold=False)
        self._cache: Dict[Tuple, ImageFont.FreeTypeFont] = {}
        logger.debug(f"Bold font:   {self._bold_path}")
        logger.debug(f"Regular font:{self._regular_path}")

    def get(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        key = (size, bold)
        if key not in self._cache:
            path = (self._bold_path if bold else None) or self._regular_path
            if path:
                try:
                    self._cache[key] = ImageFont.truetype(path, size)
                    return self._cache[key]
                except Exception:
                    pass
            self._cache[key] = ImageFont.load_default(size=size)
        return self._cache[key]


# ── 繪圖工具 ──────────────────────────────────────────────────────────────

def _hex(c: str) -> Tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _gradient(w: int, h: int,
               c1: Tuple, c2: Tuple,
               vertical: bool = True) -> Image.Image:
    """線性漸層，回傳 RGBA Image"""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    t = (np.linspace(0, 1, h if vertical else w)
         .reshape(-1, 1) if vertical else
         np.linspace(0, 1, w).reshape(1, -1))
    for ch in range(3):
        val = (c1[ch] * (1 - t) + c2[ch] * t).astype(np.uint8)
        if vertical:
            arr[:, :, ch] = np.broadcast_to(val, (h, w))
        else:
            arr[:, :, ch] = np.broadcast_to(val, (h, w))
    arr[:, :, 3] = 255
    return Image.fromarray(arr, "RGBA")


def _shadow_layer(canvas_size: Tuple[int, int],
                  x: int, y: int, w: int, h: int,
                  radius: int,
                  shadow_color: Tuple = (0, 0, 0),
                  alpha: int = 140,
                  blur: int = 14,
                  offset: Tuple[int, int] = (4, 8)) -> Image.Image:
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    sx, sy = x + offset[0], y + offset[1]
    d.rounded_rectangle([sx, sy, sx + w, sy + h], radius=radius,
                         fill=(*shadow_color, alpha))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def _draw_text_centered(draw: ImageDraw.ImageDraw,
                         cx: int, cy: int, text: str,
                         font: ImageFont.FreeTypeFont,
                         fill: Tuple,
                         stroke_width: int = 0,
                         stroke_fill: Optional[Tuple] = None):
    """水平垂直置中繪製文字"""
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = cx - tw // 2 - bbox[0]
    y = cy - th // 2 - bbox[1]
    kw: dict = {"fill": fill}
    if stroke_width:
        kw["stroke_width"] = stroke_width
        kw["stroke_fill"] = stroke_fill or (0, 0, 0)
    draw.text((x, y), text, font=font, **kw)


def _draw_text_left(draw: ImageDraw.ImageDraw,
                     x: int, cy: int, text: str,
                     font: ImageFont.FreeTypeFont,
                     fill: Tuple,
                     stroke_width: int = 0,
                     stroke_fill: Optional[Tuple] = None):
    """左對齊、垂直置中繪製文字"""
    bbox = font.getbbox(text)
    th = bbox[3] - bbox[1]
    y = cy - th // 2 - bbox[1]
    kw: dict = {"fill": fill}
    if stroke_width:
        kw["stroke_width"] = stroke_width
        kw["stroke_fill"] = stroke_fill or (0, 0, 0)
    draw.text((x, y), text, font=font, **kw)


def _draw_text_right(draw: ImageDraw.ImageDraw,
                      rx: int, cy: int, text: str,
                      font: ImageFont.FreeTypeFont,
                      fill: Tuple,
                      stroke_width: int = 0,
                      stroke_fill: Optional[Tuple] = None):
    """右對齊、垂直置中繪製文字"""
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = rx - tw - bbox[0]
    y = cy - th // 2 - bbox[1]
    kw: dict = {"fill": fill}
    if stroke_width:
        kw["stroke_width"] = stroke_width
        kw["stroke_fill"] = stroke_fill or (0, 0, 0)
    draw.text((x, y), text, font=font, **kw)


# ── 自動生成分析文字 ───────────────────────────────────────────────────────

def _generate_analysis(
    top_buy: List[Dict],
    top_sell: List[Dict],
) -> Tuple[List[str], str]:
    buy3 = "、".join(_strip_emoji(t.get("name", "")) for t in top_buy[:3]) or "—"
    sell2 = "、".join(_strip_emoji(t.get("name", "")) for t in top_sell[:2]) or "—"

    b1 = f"大戶資金聚焦：{buy3}，資金明顯流入"

    if top_buy:
        total = sum(t.get("net_flow_yi", 0) for t in top_buy)
        avg3  = sum(t.get("avg_change_pct", 0) for t in top_buy[:3]) / 3
        b2 = f"買超前三強均漲 +{avg3:.2f}%，{total:.0f}億強勢入場"
    else:
        b2 = "買超資料暫無，請關注後續法人動向"

    b3 = f"{sell2} 遭法人調節，資金轉向上游題材"

    any_high = any(t.get("avg_change_pct", 0) > 3.0 for t in top_buy)
    b4 = "市場輪動加速，聚焦高成長與低基期標的" if any_high else "族群分化明顯，選股優於選市"

    quote = "資金不會說謊，大戶的選擇，就是下一波趨勢的線索！"
    return [b1, b2, b3, b4], quote


# ── 主要生成函式 ───────────────────────────────────────────────────────────

def generate_sector_flow_image(
    top_buy: List[Dict],
    top_sell: List[Dict],
    date: str,
    stocks_analyzed: int = 0,
) -> Optional[bytes]:
    """
    生成高品質族群資金流向圖片（Pillow 版）

    Returns:
        PNG bytes or None
    """
    try:
        fonts = _Fonts()

        # ── 配色 ──────────────────────────────────────────────────────────
        BG        = _hex("#0d0d1a")
        TITLE_G1  = _hex("#1e1e42")   # 標題漸層上
        TITLE_G2  = _hex("#0d0d1a")   # 標題漸層下
        BUY_G1    = _hex("#c0001e")   # 買超標頭漸層上
        BUY_G2    = _hex("#800012")   # 買超標頭漸層下
        SELL_G1   = _hex("#007040")   # 賣超標頭漸層上
        SELL_G2   = _hex("#004428")   # 賣超標頭漸層下
        BUY_BG    = _hex("#160408")   # 買超面板底色
        SELL_BG   = _hex("#040e08")   # 賣超面板底色
        BUY_BRD   = _hex("#ff3355")
        SELL_BRD  = _hex("#00dd66")
        COL_BG    = _hex("#181e2c")   # 欄位標頭底色
        ROW_A     = _hex("#0d0d1a")
        ROW_B     = _hex("#131322")
        ANAL_BG   = _hex("#1a1600")   # 分析區底色
        ANAL_BRD  = _hex("#ffcc00")
        QUOTE_BG  = _hex("#10102a")
        QUOTE_BRD = _hex("#ff8800")
        WHITE     = (255, 255, 255)
        GOLD      = _hex("#ffd700")
        SILVER    = _hex("#c8c8c8")
        BRONZE    = _hex("#cd7f32")
        SUB       = _hex("#7a7a9a")
        BUY_VAL   = _hex("#ff7070")
        SELL_VAL  = _hex("#55ee88")
        POS       = _hex("#44dd77")
        NEG       = _hex("#ff5555")
        DECO_LINE = _hex("#ffcc00")

        # ── Layout (px) ────────────────────────────────────────────────────
        W         = 1600
        PAD       = 24          # 外邊距
        GAP       = 18          # 左右面板間距
        TITLE_H   = 200
        SEC_H     = 64          # 族群標頭高
        COL_H     = 46          # 欄位標頭高
        ROW_H     = 56          # 資料行高
        ANAL_H    = 220         # 分析區高
        FOOT_H    = 44
        RADIUS    = 14          # 圓角半徑

        n         = max(len(top_buy), len(top_sell), 1)
        PANEL_H   = SEC_H + COL_H + n * ROW_H
        H         = TITLE_H + PANEL_H + ANAL_H + FOOT_H + PAD * 3

        PW        = (W - PAD * 2 - GAP) // 2   # 單一面板寬
        LX        = PAD                          # 左面板 x
        RX        = PAD + PW + GAP              # 右面板 x
        PANEL_Y   = TITLE_H + PAD               # 面板頂部 y
        ANAL_Y    = PANEL_Y + PANEL_H + PAD     # 分析區頂部 y
        FOOT_Y    = ANAL_Y + ANAL_H + PAD // 2

        # ── 建立畫布（RGBA 支援陰影合成）────────────────────────────────
        img = Image.new("RGBA", (W, H), (*BG, 255))

        # ── ① 標題漸層背景 ────────────────────────────────────────────
        title_grad = _gradient(W, TITLE_H, TITLE_G1, TITLE_G2)
        img.paste(title_grad, (0, 0))

        # 上下裝飾金線
        draw = ImageDraw.Draw(img)
        for yy, thick in [(3, 3), (TITLE_H - 4, 2)]:
            draw.rectangle([PAD, yy, W - PAD, yy + thick], fill=(*DECO_LINE, 200))

        # 標題文字
        t_cx = W // 2
        f_title = fonts.get(54, bold=True)
        f_sub   = fonts.get(24, bold=False)
        f_info  = fonts.get(19, bold=False)

        _draw_text_centered(draw, t_cx, 72, "盤後族群資金流向",
                            f_title, GOLD, stroke_width=2,
                            stroke_fill=_hex("#0d0d1a"))
        _draw_text_centered(draw, t_cx, 128,
                            "三大法人在買什麼？賣什麼？",
                            f_sub, WHITE)
        _draw_text_centered(draw, t_cx, 167,
                            f"{date}　|　分析 {stocks_analyzed} 支主題股票",
                            f_info, SUB)

        # ── ② 面板陰影 ────────────────────────────────────────────────
        for px in [LX, RX]:
            shadow = _shadow_layer((W, H), px, PANEL_Y, PW, PANEL_H,
                                   RADIUS, shadow_color=(0, 0, 0),
                                   alpha=160, blur=18, offset=(6, 10))
            img = Image.alpha_composite(img, shadow)

        draw = ImageDraw.Draw(img)

        # ── ③ 面板主體 ────────────────────────────────────────────────
        def draw_panel(px: int, items: List[Dict], is_buy: bool):
            bg     = BUY_BG   if is_buy else SELL_BG
            brd    = BUY_BRD  if is_buy else SELL_BRD
            g1, g2 = (BUY_G1, BUY_G2) if is_buy else (SELL_G1, SELL_G2)
            v_col  = BUY_VAL  if is_buy else SELL_VAL
            arrow  = "▲" if is_buy else "▼"
            label  = f"法人買超  TOP{len(items)}  {arrow}" if is_buy \
                     else f"法人賣超  TOP{len(items)}  {arrow}"

            # 面板底色 + 邊框
            draw.rounded_rectangle(
                [px, PANEL_Y, px + PW, PANEL_Y + PANEL_H],
                radius=RADIUS, fill=(*bg, 255),
                outline=(*brd, 255), width=2,
            )

            # 族群標頭漸層
            hdr_grad = _gradient(PW - 4, SEC_H - 4, g1, g2)
            img.paste(hdr_grad, (px + 2, PANEL_Y + 2))
            # 重畫圓角遮罩（擦掉標頭直角）
            draw.rounded_rectangle(
                [px, PANEL_Y, px + PW, PANEL_Y + PANEL_H],
                radius=RADIUS, outline=(*brd, 255), width=2,
            )

            f_sec  = fonts.get(26, bold=True)
            f_col  = fonts.get(19, bold=False)
            f_name = fonts.get(22, bold=False)
            f_val  = fonts.get(22, bold=True)
            f_chg  = fonts.get(20, bold=False)
            f_rank = fonts.get(18, bold=True)

            # 標頭文字
            _draw_text_centered(draw,
                                px + PW // 2,
                                PANEL_Y + SEC_H // 2,
                                label, f_sec, WHITE)

            # 欄位標頭背景 + 文字
            col_y = PANEL_Y + SEC_H
            draw.rectangle([px + 2, col_y, px + PW - 2, col_y + COL_H],
                           fill=(*COL_BG, 255))

            # 欄位定義 (x比例, 文字, 對齊)
            COL_RANK  = int(px + PW * 0.055)
            COL_NAME  = int(px + PW * 0.105)
            COL_VAL_R = int(px + PW * 0.790)
            COL_CHG_R = int(px + PW * 0.975)

            col_cy = col_y + COL_H // 2
            for cx_or_x, text, align in [
                (COL_RANK,  "排名",      "c"),
                (COL_NAME,  "族群",      "l"),
                (COL_VAL_R, "大戶差(億)", "r"),
                (COL_CHG_R, "漲幅",      "r"),
            ]:
                if align == "c":
                    _draw_text_centered(draw, cx_or_x, col_cy, text, f_col, SUB)
                elif align == "l":
                    _draw_text_left(draw, cx_or_x, col_cy, text, f_col, SUB)
                else:
                    _draw_text_right(draw, cx_or_x, col_cy, text, f_col, SUB)

            # 資料行
            BADGE_R   = 20
            RANK_COLS = [GOLD, SILVER, BRONZE]

            for i in range(n):
                ry  = col_y + COL_H + i * ROW_H
                cy  = ry + ROW_H // 2
                row_bg = ROW_A if i % 2 == 0 else ROW_B
                draw.rectangle([px + 2, ry, px + PW - 2, ry + ROW_H],
                               fill=(*row_bg, 255))

                if i < len(items):
                    item = items[i]

                    # 排名徽章
                    badge_c = RANK_COLS[i] if i < 3 else _hex("#2a3040")
                    draw.ellipse(
                        [COL_RANK - BADGE_R, cy - BADGE_R,
                         COL_RANK + BADGE_R, cy + BADGE_R],
                        fill=(*badge_c, 255),
                    )
                    num_c = _hex("#1a1a1a") if i < 3 else SILVER
                    _draw_text_centered(draw, COL_RANK, cy,
                                        str(i + 1), f_rank, num_c)

                    # 族群名稱
                    name = _strip_emoji(
                        f"{item.get('emoji','')}{item.get('name','')}"
                    )
                    _draw_text_left(draw, COL_NAME, cy, name, f_name, WHITE)

                    # 大戶差
                    flow = item.get("net_flow_yi", 0)
                    f_str = f"+{flow:.2f}億" if flow >= 0 else f"{flow:.2f}億"
                    _draw_text_right(draw, COL_VAL_R, cy, f_str, f_val, v_col)

                    # 漲幅
                    chg = item.get("avg_change_pct", 0)
                    chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
                    _draw_text_right(draw, COL_CHG_R, cy, chg_str,
                                     f_chg, POS if chg >= 0 else NEG)

        draw_panel(LX, top_buy,  is_buy=True)
        draw_panel(RX, top_sell, is_buy=False)

        # ── ④ 分析觀察區 ─────────────────────────────────────────────
        bullets, quote = _generate_analysis(top_buy, top_sell)

        ANALY_W = int((W - PAD * 2) * 0.62)
        QUOTE_X = PAD + ANALY_W + GAP
        QUOTE_W = W - PAD - QUOTE_X

        # 陰影
        for ax, aw in [(PAD, ANALY_W), (QUOTE_X, QUOTE_W)]:
            sh = _shadow_layer((W, H), ax, ANAL_Y, aw, ANAL_H,
                               RADIUS, alpha=130, blur=14, offset=(4, 8))
            img = Image.alpha_composite(img, sh)
        draw = ImageDraw.Draw(img)

        # 分析面板
        draw.rounded_rectangle(
            [PAD, ANAL_Y, PAD + ANALY_W, ANAL_Y + ANAL_H],
            radius=RADIUS, fill=(*ANAL_BG, 255),
            outline=(*ANAL_BRD, 255), width=2,
        )

        f_ahdr  = fonts.get(24, bold=True)
        f_abody = fonts.get(21, bold=False)

        _draw_text_left(draw, PAD + 22, ANAL_Y + 30,
                        "分析觀察", f_ahdr, GOLD)

        for idx, bullet in enumerate(bullets):
            by = ANAL_Y + 68 + idx * 38
            _draw_text_left(draw, PAD + 22, by,
                            f"◆  {_strip_emoji(bullet)}", f_abody, WHITE)

        # 引言框
        draw.rounded_rectangle(
            [QUOTE_X, ANAL_Y, QUOTE_X + QUOTE_W, ANAL_Y + ANAL_H],
            radius=RADIUS, fill=(*QUOTE_BG, 255),
            outline=(*QUOTE_BRD, 255), width=2,
        )

        f_qdeco = fonts.get(52, bold=True)
        f_qtext = fonts.get(22, bold=False)

        # 裝飾引號
        _draw_text_left(draw, QUOTE_X + 18, ANAL_Y + 18,
                        '"', f_qdeco, (*QUOTE_BRD, 200))

        # 引言文字自動換行（每 14 字換行）
        q_clean = _strip_emoji(quote)
        chunk   = 14
        lines   = [q_clean[i:i + chunk] for i in range(0, len(q_clean), chunk)]
        line_h  = 38
        total_h = len(lines) * line_h
        q_start = ANAL_Y + (ANAL_H - total_h) // 2 + 10
        qcx     = QUOTE_X + QUOTE_W // 2
        for li, ln in enumerate(lines):
            _draw_text_centered(draw, qcx, q_start + li * line_h,
                                ln, f_qtext, WHITE)

        # ── ⑤ 頁尾 ───────────────────────────────────────────────────
        f_foot = fonts.get(17, bold=False)
        _draw_text_centered(draw, W // 2, FOOT_Y + FOOT_H // 2,
                            "本報告基於三大法人買賣超資料推算，僅供參考，不構成投資建議",
                            f_foot, SUB)

        # ── 輸出 RGB PNG ──────────────────────────────────────────────
        out = img.convert("RGB")
        buf = io.BytesIO()
        out.save(buf, format="PNG", optimize=False)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        logger.error(f"圖片生成失敗: {e}", exc_info=True)
        return None
