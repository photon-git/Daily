"""
elec_week_renderer.py
电量周度数据 PNG 渲染器 —— 完全按 PPT XML 参数还原
所有坐标/尺寸/颜色/字体均从 assets/电量周度数据_模板.pptx 直接读取
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

_HERE     = os.path.dirname(os.path.abspath(__file__))
ASSETS    = os.path.join(_HERE, "assets")
FONTS_DIR = os.path.join(_HERE, "fonts")
OUT_DIR   = os.path.join(_HERE, "output")

BG_PATH   = os.path.join(ASSETS, "bg.png")
LOGO_PATH = os.path.join(ASSETS, "logo.png")

FONT_R = os.path.join(FONTS_DIR, "msyh.ttf")
FONT_B = os.path.join(FONTS_DIR, "msyh-b.ttf")

# PPT 幻灯片宽度 508mm → 输出宽 1080px
W     = 1080
SCALE = W / 508.0

def mm(v): return int(round(v * SCALE))

# ── PPT XML 精确坐标 (mm) ─────────────────────────────────────────────────────
# 图片 8  (logo)       x=-4.83  y=0.06   w=69.53  h=57.68
LOGO_X = mm(-4.83); LOGO_Y = mm(0.06);  LOGO_W = mm(69.53); LOGO_H = mm(57.68)
# TextBox 4 (logo文字) x=55.61  y=15.50  w=147.07 h=39.47
LTEXT_X= mm(55.61); LTEXT_Y= mm(8.00);  LTEXT_W= mm(147.07); LTEXT_H= mm(39.47)
# 矩形 26  (标题背景)  x=1.34   y=45.54  w=508    h=51.84  noFill+阴影
TITLE_X= mm(1.34);  TITLE_Y= mm(45.54); TITLE_W= mm(508.00); TITLE_H= mm(51.84)
# TextBox 3 (日期范围) x=1.34   y=95.62  w=508    h=19.63
DATE_X = mm(1.34);  DATE_Y = mm(95.62); DATE_W = mm(508.00); DATE_H = mm(19.63)
# 圆角矩形 2 (地区栏)  x=11.56  y=120.09 w=486.59 h=40.20
META_X = mm(11.56); META_Y = mm(120.09);META_W = mm(486.59); META_H = mm(40.20)
# TextBox 4 (地区文字) x=11.47  y=130.74 w=486.67 h=27.02
MTEXT_X= mm(11.47); MTEXT_Y= mm(130.74);MTEXT_W= mm(486.67); MTEXT_H= mm(27.02)
# Table 4              x=9.42   y=167.32 w=489.41 h=604.65
TABLE_X= mm(9.42);  TABLE_Y= mm(167.32);TABLE_W= mm(489.41); TABLE_H= mm(604.65)
# TextBox 3 (备注)     x=12.28  y=773.29
NOTES_X= mm(12.28); NOTES_Y= mm(773.29)

# ── 表格列宽/行高 (mm，直接来自 PPT XML) ──────────────────────────────────────
COL_MM = [132.29, 172.74, 94.84, 89.54]
ROW_MM = [62.22, 90.43, 90.45, 90.35, 90.40, 90.40, 90.40]

# ── 颜色 (从 PPT XML srgbClr 读取) ───────────────────────────────────────────
C_HEADER  = (0x0F, 0x79, 0x7B)   # 表头背景 #0F797B
C_R1_LEFT = (0xF5, 0xFF, 0xFF)   # row1 周期列背景
C_R2_LEFT = (0xEB, 0xFF, 0xFA)   # row2 周期列背景
C_R1_DATA = (0xF4, 0xFF, 0xFF)   # 采集行数据列
C_R2_DATA = (0xCB, 0xEA, 0xF2)   # 售电行数据列
C_M1_DATA = (0xF5, 0xFF, 0xFF)
C_M2_DATA = (0xCB, 0xEA, 0xF1)
C_Y1_DATA = (0xF5, 0xFF, 0xFE)
C_Y2_DATA = (0xCB, 0xEA, 0xF2)
C_TEXT    = (0x10, 0x56, 0x50)   # 主文字色 #105650
C_WHITE   = (255, 255, 255)
C_LOGO_TXT= (0x59, 0x59, 0x5A)   # logo 文字 #59595A
# 圆角矩形渐变: accent1(#4F81BD) lumMod=20%+lumOff=80% → #DBE5F1, 终止 bg1=white
C_META_L  = (219, 229, 241)       # #DBE5F1
C_META_R  = (255, 255, 255)
C_GRID    = (217, 217, 217)       # 表格内分隔线 bg1*85% = #D9D9D9


# ── 字体 ─────────────────────────────────────────────────────────────────────
def _font(size, bold=False):
    path = FONT_B if bold else FONT_R
    for p in [path, FONT_R, FONT_B]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

def pt(v):
    """PPT pt → px，基于 SCALE"""
    return max(8, int(round(v * SCALE * 25.4 / 72)))


# ── 绘图辅助 ──────────────────────────────────────────────────────────────────
def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def _th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

def _center(draw, x, y, w, h, text, font, color):
    bb = draw.textbbox((0, 0), text, font=font)
    tx = x + (w - (bb[2]-bb[0])) // 2 - bb[0]
    ty = y + (h - (bb[3]-bb[1])) // 2 - bb[1]
    draw.text((tx, ty), text, font=font, fill=color)

def _wrap_center(draw, x, y, w, h, text, font, color, ls=None):
    """自动折行，整体居中。ls=None 时行距=字高*1.5（PPT spcPct=150%）"""
    lines, cur = [], ""
    for ch in text:
        if ch == '\n':
            lines.append(cur); cur = ""
        else:
            if _tw(draw, cur+ch, font) > w - mm(2.5)*2:
                lines.append(cur); cur = ch
            else:
                cur += ch
    if cur: lines.append(cur)
    char_h = _th(draw, "测", font)
    lh = ls if ls is not None else int(char_h * 1.5)
    total = char_h + (len(lines)-1)*lh
    sy = y + (h - total) // 2
    for i, line in enumerate(lines):
        lw = _tw(draw, line, font)
        draw.text((x + (w-lw)//2, sy + i*lh), line, font=font, fill=color)

def _gradient_rect_rounded(img, x, y, w, h, c_top, c_bottom, radius):
    # 先画渐变
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(h):
        t = i / max(h-1, 1)
        arr[i, :, 0] = int(c_bottom[0]*(1-t) + c_top[0]*t)
        arr[i, :, 1] = int(c_bottom[1]*(1-t) + c_top[1]*t)
        arr[i, :, 2] = int(c_bottom[2]*(1-t) + c_top[2]*t)
    grad = Image.fromarray(arr, "RGB")
    # 圆角蒙版
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w-1, h-1], radius=radius, fill=255)
    img.paste(grad, (x, y), mask)


# ── 主渲染函数 ────────────────────────────────────────────────────────────────
def render_elec_week_png(data: dict, output_path: str = None) -> str:
    defaults = {
        "week_range":  "",
        "report_date": "",
        "region":      "公司经营区",
        "month_range": "",
        "year_range":  "",
    }
    data = {**defaults, **data}

    # PPT 字体大小（pt） → px
    # logo文字: 36pt bold  标题: 72pt bold  其余: 40pt  备注: 32pt
    f_logo   = _font(pt(36), bold=True)
    f_title  = _font(pt(72), bold=True)
    f_date   = _font(pt(40), bold=False)
    f_meta   = _font(pt(40), bold=True)
    f_hdr    = _font(pt(40), bold=True)
    f_period = _font(pt(40), bold=True)
    f_label  = _font(pt(40), bold=False)
    f_value  = _font(pt(40), bold=False)
    f_yoy    = _font(pt(40), bold=False)
    f_notes  = _font(pt(32), bold=False)

    # 预计算备注高度
    notes_text = data.get("notes", "")
    tmp_draw = ImageDraw.Draw(Image.new("RGB", (W, 50)))
    notes_lines = []
    if notes_text:
        buf = "备注：" + notes_text
        cur = ""
        for ch in buf:
            if _tw(tmp_draw, cur+ch, f_notes) > TABLE_W - mm(2):
                notes_lines.append(cur); cur = ch
            else:
                cur += ch
        if cur: notes_lines.append(cur)
    # 备注颜色: schemeClr bg1 lumMod=50% → white*50% = #808080
    C_NOTES = (128, 128, 128)
    nl_h = _th(tmp_draw, "测", f_notes)  # spcPct=100%，无额外行距
    notes_block_h = len(notes_lines) * nl_h if notes_lines else 0

    total_h = NOTES_Y + notes_block_h + mm(18)

    # 画布 + 背景
    img = Image.new("RGB", (W, total_h), (240, 248, 252))
    if os.path.exists(BG_PATH):
        bg = Image.open(BG_PATH).convert("RGB").resize((W, total_h), Image.LANCZOS)
        img.paste(bg, (0, 0))
    draw = ImageDraw.Draw(img)

    # ── Logo 图片 (图片 8, x=-4.83 y=0.06) ────────────────────────────────
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA").resize((LOGO_W, LOGO_H), Image.LANCZOS)
        img.paste(logo, (max(0, LOGO_X), LOGO_Y), logo)

    # ── Logo 文字 (TextBox 4, 两行, sz=36pt bold, color=#59595A) ──────────
    # PPT: "用电需求分析预测" 第一行, "（ 全国用电监测分析 ）" 第二行, spcAft=1.2pt
    line_gap = pt(1.2)  # spcAft=1.2pt
    lh1 = _th(draw, "测", f_logo)
    lh2 = _th(draw, "测", f_logo)
    total_logo_txt = lh1 + line_gap + lh2
    ly = LTEXT_Y + (LTEXT_H - total_logo_txt) // 2
    for txt, dy in [("用电需求分析预测", 0), ("（ 全国用电监测分析 ）", lh1 + line_gap)]:
        lw = _tw(draw, txt, f_logo)
        draw.text((LTEXT_X + (LTEXT_W - lw)//2, ly + dy), txt, font=f_logo, fill=C_LOGO_TXT)

    # ── 主标题 (矩形 26, sz=72pt bold, tx1=黑色, outerShdw 下方 40%透明黑) ──
    # 用 RGBA 图层绘制阴影再合成
    shadow_layer = Image.new("RGBA", (W, total_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    _center(sd, TITLE_X+1, TITLE_Y+2, TITLE_W, TITLE_H, "电量周度数据", f_title, (0, 0, 0, 102))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, shadow_layer)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    _center(draw, TITLE_X, TITLE_Y, TITLE_W, TITLE_H, "电量周度数据", f_title, (0, 0, 0))

    # ── 日期范围 (TextBox 3, sz=40pt, 非粗体, 英文括号, align=CENTER, 黑色)
    wr = data.get("week_range", "")
    _center(draw, DATE_X, DATE_Y, DATE_W, DATE_H,
            f"({wr})" if wr else "", f_date, (0, 0, 0))

    # ── 地区栏渐变圆角矩形 (圆角矩形 2, gradient 从下#DBE5F1→上white, radius=3mm)
    # 圆角半径：PPT 默认 adj=16667/100000，短边=META_H，radius≈16.7%×h
    meta_radius = int(META_H * 16667 / 100000)
    _gradient_rect_rounded(img, META_X, META_Y, META_W, META_H, C_META_L, C_META_R, radius=meta_radius)
    draw = ImageDraw.Draw(img)

    # ── 地区文字 (TextBox 4, x=11.47 y=130.74 w=486.67 h=27.02, sz=40pt bold, 黑色)
    # 文字在 TextBox 内垂直居中，左右各留 5mm padding
    region     = data.get("region", "公司经营区")
    report_date= data.get("report_date", "")
    mty = MTEXT_Y + (MTEXT_H - _th(draw, "测", f_meta)) // 2 - mm(7.5)
    draw.text((MTEXT_X + mm(20), mty), f"地区范围：{region}", font=f_meta, fill=(0, 0, 0))
    rw_txt = f"报送日期：{report_date}"
    draw.text((MTEXT_X + MTEXT_W - mm(20) - _tw(draw, rw_txt, f_meta), mty),
              rw_txt, font=f_meta, fill=(0, 0, 0))

    # ── 表格 ─────────────────────────────────────────────────────────────────
    COL_W = [mm(v) for v in COL_MM]
    COL_W[-1] = TABLE_W - sum(COL_W[:-1])
    ROW_H = [mm(v) for v in ROW_MM]
    ROW_H[-1] = TABLE_H - sum(ROW_H[:-1])

    def cx(c): return TABLE_X + sum(COL_W[:c])
    def ry(r): return TABLE_Y + sum(ROW_H[:r])

    # 先铺白色底，防止背景图透色
    draw.rectangle([TABLE_X, TABLE_Y, TABLE_X+TABLE_W, TABLE_Y+TABLE_H], fill=C_WHITE)

    # 表头 (fill=#0F797B, text=white, sz=40pt bold, lnSpc=150%)
    draw.rectangle([TABLE_X, ry(0), TABLE_X+TABLE_W, ry(1)], fill=C_HEADER)
    for c, hdr in enumerate(["周期", "口径", "数值\n(亿千瓦时)", "同比\n增速"]):
        _wrap_center(draw, cx(c), ry(0), COL_W[c], ROW_H[0], hdr, f_hdr, C_WHITE)

    sections = [
        {"period": "周电量",     "date": "",
         "d": data.get("week",  {}), "r": (1, 2), "c1d": C_R1_DATA, "c2d": C_R2_DATA},
        {"period": "月累计电量", "date": data.get("month_range", ""),
         "d": data.get("month", {}), "r": (3, 4), "c1d": C_M1_DATA, "c2d": C_M2_DATA},
        {"period": "年累计电量", "date": data.get("year_range",  ""),
         "d": data.get("year",  {}), "r": (5, 6), "c1d": C_Y1_DATA, "c2d": C_Y2_DATA},
    ]

    for sec in sections:
        r1, r2 = sec["r"]
        sh = ROW_H[r1] + ROW_H[r2]   # 合并行高

        # 周期列背景（整体一个颜色 F5FFFF）
        draw.rectangle([cx(0), ry(r1), cx(1), ry(r1)+sh], fill=C_R1_LEFT)

        # 采集行：数值列 + 同比列
        for idx, key in enumerate(["collect", "collect_yoy"]):
            col = idx + 2
            val = sec["d"].get(key, "")
            draw.rectangle([cx(col), ry(r1), cx(col+1), ry(r2)], fill=sec["c1d"])
            font = f_value if col == 2 else f_yoy
            _center(draw, cx(col), ry(r1), COL_W[col], ROW_H[r1], val, font, C_TEXT)

        # 采集行：口径列 (sz=40pt, align=CENTER, 折行)
        draw.rectangle([cx(1), ry(r1), cx(2), ry(r2)], fill=sec["c1d"])
        _wrap_center(draw, cx(1), ry(r1), COL_W[1], ROW_H[r1],
                     "采集电量（含采集覆盖的分布式光伏和自备电厂自发自用电量）",
                     f_label, C_TEXT)

        # 售电行：数值列 + 同比列
        for idx, key in enumerate(["sale", "sale_yoy"]):
            col = idx + 2
            val = sec["d"].get(key, "")
            draw.rectangle([cx(col), ry(r2), cx(col+1), ry(r2)+ROW_H[r2]], fill=sec["c2d"])
            font = f_value if col == 2 else f_yoy
            _center(draw, cx(col), ry(r2), COL_W[col], ROW_H[r2], val, font, C_TEXT)

        # 售电行：口径列
        draw.rectangle([cx(1), ry(r2), cx(2), ry(r2)+ROW_H[r2]], fill=sec["c2d"])
        _wrap_center(draw, cx(1), ry(r2), COL_W[1], ROW_H[r2],
                     "售电量（营销口径）", f_label, C_TEXT)

        # 周期文字（最后绘制）PPT: 两段 sz=40pt bold, lnSpc=150%, 整体居中
        pt_text   = sec["period"]
        date_text = f"({sec['date']})" if sec["date"] else ""
        char_h = _th(draw, "测", f_period)
        lh150  = int(char_h * 1.5)
        if date_text:
            total_txt = char_h + lh150  # 两行：第一行字高 + 150%间距到第二行起点
            sy = ry(r1) + (sh - total_txt) // 2
            for ti, txt in enumerate([pt_text, date_text]):
                tw = _tw(draw, txt, f_period)
                draw.text((cx(0) + (COL_W[0]-tw)//2, sy + ti*lh150), txt, font=f_period, fill=C_TEXT)
        else:
            _wrap_center(draw, cx(0), ry(r1), COL_W[0], sh, pt_text, f_period, C_TEXT)

        # 采集/售电分隔线
        draw.line([cx(1), ry(r2), cx(4), ry(r2)], fill=C_GRID, width=1)

    # 表格外框 + 列线 + 段间分隔线（PPT XML 所有边框均为 bg1*85%=#D9D9D9）
    draw.rectangle([TABLE_X, TABLE_Y, TABLE_X+TABLE_W, TABLE_Y+TABLE_H],
                   outline=C_GRID, width=1)
    for c in [1, 2, 3]:
        draw.line([cx(c), TABLE_Y, cx(c), TABLE_Y+TABLE_H], fill=C_GRID, width=1)
    for r in [1, 3, 5]:
        draw.line([TABLE_X, ry(r), TABLE_X+TABLE_W, ry(r)], fill=C_GRID, width=1)

    # ── 备注 (TextBox 3, sz=32pt, align=LEFT) ────────────────────────────────
    ny = NOTES_Y
    for line in notes_lines:
        draw.text((NOTES_X, ny), line, font=f_notes, fill=C_NOTES)
        ny += nl_h

    # 裁剪到实际高度
    final_h = ny + mm(12)
    img = img.crop((0, 0, W, final_h))

    os.makedirs(OUT_DIR, exist_ok=True)
    if not output_path:
        output_path = os.path.join(OUT_DIR, f"elec_week_{datetime.now().strftime('%Y-%m-%d')}.png")
    img.save(output_path, "PNG")
    print(f"✅ 已生成：{output_path}  ({W}×{final_h}px)")
    return output_path


if __name__ == "__main__":
    MOCK = {
        "week_range":  "2026年6月29日-2026年7月5日",
        "report_date": "2026年7月6日",
        "region":      "公司经营区",
        "month_range": "7月1日-5日",
        "year_range":  "1月1日-7月5日",
        "week":  {"collect": "1490.34", "collect_yoy": "-2.8%", "sale": "1376.47", "sale_yoy": "-2.6%"},
        "month": {"collect": "1073.01", "collect_yoy": "-5.0%", "sale": "990.93",  "sale_yoy": "-4.9%"},
        "year":  {"collect": "35296.88","collect_yoy": "4.4%",  "sale": "32532.54","sale_yoy": "4.4%"},
        "notes": "一是本周电量负增长，主要受江浙等地降雨天气影响，平均最高气温较同期低4.8℃，居民用电量同比下降15.4%。"
                 "二是周采集电量增速低于售电量增速，主要由于江苏、浙江、湖南、山东、上海、安徽等省份连续阴雨天气，"
                 "分布式光伏出力下降，自用电量减少。",
    }
    render_elec_week_png(MOCK, output_path="output/elec_week_test.png")
