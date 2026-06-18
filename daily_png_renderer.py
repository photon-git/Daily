"""
Agent⑥ 日负荷预测卡片 —— matplotlib 直接出 PNG
1920px 宽，高度随数据自动变化
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.font_manager import FontProperties
import matplotlib.image as mpimg
from matplotlib.colors import LinearSegmentedColormap
from datetime import date, datetime

# ── 路径（全部相对本文件自动定位）──────────────────────
_HERE     = os.path.dirname(os.path.abspath(__file__))
BJ_PATH   = os.path.join(_HERE, "assets/bj.png")
JB_PATH   = os.path.join(_HERE, "assets/jiaobiao.png")
LM_PATH   = os.path.join(_HERE, "assets/lm.png")
OUT_DIR   = os.path.join(_HERE, "output")
FONTS_DIR = os.path.join(_HERE, "fonts")
FONT_PATH = os.path.join(FONTS_DIR, "msyh.ttf")
FONT_BOLD = os.path.join(FONTS_DIR, "msyh-b.ttf")
FONT_SHS_R= os.path.join(FONTS_DIR, "SourceHanSansSC-Regular.otf")
FONT_SHS_B= os.path.join(FONTS_DIR, "SourceHanSansSC-Bold.otf")
FONT_FB   = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

# ── 颜色 ─────────────────────────────────────────────
WHITE = "#FFFFFF"
DARK  = "#00524F"
GRAY  = "#666666"
LINE_C= "#BCDFE5"
RADIUS= 40
COL1_W= 506
COL2_W= 1256
TBL_W = COL1_W + COL2_W
TBL_X = (1920 - TBL_W) // 2
TH_H  = 248
ROW_H_V = 200

# ── 图片素材缓存（模块级，只读一次）────────────────────
_IMG_CACHE = {}
def _load_img(path):
    if path not in _IMG_CACHE:
        _IMG_CACHE[path] = mpimg.imread(path) if os.path.exists(path) else None
    return _IMG_CACHE[path]

# ── 字体缓存 ──────────────────────────────────────────
_FONT_CACHE = {}
def get_font(size=12, bold=False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = ([FONT_BOLD, FONT_SHS_B, FONT_PATH, FONT_SHS_R, FONT_FB] if bold
                  else [FONT_PATH, FONT_SHS_R, FONT_FB])
    fp = next((FontProperties(fname=p, size=size) for p in candidates if os.path.exists(p)),
              FontProperties(size=size))
    _FONT_CACHE[key] = fp
    return fp

# ── 字宽估算（不触发 canvas 渲染）────────────────────
# 中文字符约等于字号×1.0，ASCII约字号×0.6
def _est_text_width(text, font_size):
    w = 0
    for ch in text:
        w += font_size * (0.6 if ord(ch) < 256 else 1.0)
    return w

def _wrap_by_width(text, max_w, font_size, is_date=False):
    """按估算宽度换行"""
    if is_date and '(' in text:
        idx = text.index('(')
        return [text[:idx], text[idx:]] if idx > 0 else [text]
    # 用1.4保守系数，微软雅黑实际比标称宽
    char_w = font_size * 1.4
    chars_per_line = max(int((max_w - 48) / char_w), 1)
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= chars_per_line:
            lines.append(cur); cur = ""
    if cur: lines.append(cur)
    return lines if lines else [text]

def _fit_font_size(text, max_w, base_size=36, min_size=16):
    """估算不换行时适配列宽的字号"""
    fs = base_size
    while fs > min_size:
        if _est_text_width(text, fs) <= max_w - 20:
            break
        fs -= 2
    return fs


# ── Pillow 文字渲染（模块级，预测表和复盘表共用）────────
from PIL import Image as PILImage, ImageDraw as PILDraw, ImageFont as PILFont

def _pil_text_img(text, cell_w, cell_h, font_size, color, bg):
    """用 Pillow 把文字渲染到指定尺寸图片，自动换行，绝对不溢出"""
    PAD  = 24
    img  = PILImage.new("RGBA", (int(cell_w), int(cell_h)), (0,0,0,0))
    draw = PILDraw.Draw(img)
    r,g,b = tuple(int(bg.lstrip('#')[i:i+2],16) for i in (0,2,4))
    img.paste((r,g,b,255), [0,0,int(cell_w),int(cell_h)])

    pil_fp = None
    for p in [FONT_BOLD, FONT_SHS_B, FONT_PATH, FONT_SHS_R, FONT_FB]:
        if os.path.exists(p):
            try: pil_fp = PILFont.truetype(p, font_size); break
            except: pass
    if pil_fp is None:
        pil_fp = PILFont.load_default()

    words = list(text)
    lines, cur = [], ""
    for ch in words:
        test = cur + ch
        bb   = draw.textbbox((0,0), test, font=pil_fp)
        if bb[2] > cell_w - PAD*2 and cur:
            lines.append(cur); cur = ch
        else:
            cur = test
    if cur: lines.append(cur)

    line_h  = font_size + 8
    total_h = len(lines) * line_h
    ty      = int((cell_h - total_h) / 2)
    cr,cg,cb = tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))
    for line in lines:
        bb  = draw.textbbox((0,0), line, font=pil_fp)
        tx  = int((cell_w - (bb[2]-bb[0])) / 2)  # 水平居中
        draw.text((tx, ty), line, font=pil_fp, fill=(cr,cg,cb,255))
        ty += line_h
    return np.array(img) / 255.0


def render_daily_png(data: dict, output_path: str = None) -> str:
    DPI   = 100
    PX_W  = 1920
    INCH_W= PX_W / DPI

    HDR_H        = 220
    TITLE_H      = 380
    META_H       = 150
    META_MARGIN_B= 50
    TBL_HDR      = TH_H
    ROW_H        = ROW_H_V
    COL_HDR      = 180
    SEP_H        = 60
    FOOTER_H     = 100
    LINE_H       = 46
    PAD_V        = 28

    rv_rows_data = data.get("review", [])
    rv_cw = [int(TBL_W * r) for r in [0.17, 0.16, 0.16, 0.16, 0.35]]
    rv_cw[-1] = TBL_W - sum(rv_cw[:-1])

    # 预算行高（纯文字估算，不渲染）
    row_heights = []
    for row in rv_rows_data:
        cells = [row.get("date",""), row.get("actual",""),
                 row.get("forecast",""), row.get("accuracy",""), row.get("reason","")]
        max_lines = max(
            len(_wrap_by_width(c, cw_i, 44 if ci==4 else 36, is_date=(ci==0)))
            if ci in (0, 4) else 1
            for ci,(cw_i,c) in enumerate(zip(rv_cw, cells)))
        row_heights.append(max(ROW_H, PAD_V*2 + max_lines*LINE_H))

    n_fc  = len(data.get("forecast", []))
    fc_h  = TBL_HDR + n_fc * ROW_H
    rv_h  = TBL_HDR + COL_HDR + sum(row_heights)
    TOT_H = HDR_H + TITLE_H + META_H + META_MARGIN_B + fc_h + SEP_H + rv_h + FOOTER_H

    fig = plt.figure(figsize=(INCH_W, TOT_H/DPI), dpi=DPI)
    ax  = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PX_W); ax.set_ylim(0, TOT_H)
    ax.axis('off'); ax.invert_yaxis()

    # ── ① 背景 + 光晕 ────────────────────────────────
    bj = _load_img(BJ_PATH)
    if bj is not None:
        ax.imshow(bj, extent=[0, PX_W, TOT_H, 0], aspect='auto', zorder=0)

    lm = _load_img(LM_PATH)
    if lm is not None:
        half   = lm[:, lm.shape[1]//2:, :]
        disp_h = int(TOT_H * 0.5)
        disp_w = int(half.shape[1] * disp_h / lm.shape[0])
        lm_y   = (TOT_H - disp_h) // 2
        ax.imshow(half, extent=[0, disp_w, lm_y+disp_h, lm_y],
                  aspect='auto', zorder=1, alpha=0.85)

    # ── ② 角标 ───────────────────────────────────────
    jb = _load_img(JB_PATH)
    if jb is not None:
        jb_h = int(HDR_H * 0.75)
        jb_w = int(jb.shape[1] * jb_h / jb.shape[0])
        jb_y = (HDR_H - jb_h) // 2
        ax.imshow(jb, extent=[60, 60+jb_w, jb_y+jb_h, jb_y], aspect='auto', zorder=2)

    y = HDR_H

    # ── ③ 主标题 ─────────────────────────────────────
    f_title = get_font(90, bold=True)
    f_sub   = get_font(42)
    shadow  = (181/255, 209/255, 227/255, 0.67)
    ax.text(PX_W/2+7, y+170+11, "公司经营区日最大用电负荷预测",
            ha='center', va='center', fontproperties=f_title, color=shadow, zorder=3)
    ax.text(PX_W/2, y+170, "公司经营区日最大用电负荷预测",
            ha='center', va='center', fontproperties=f_title, color="#000000", zorder=4)
    ax.text(PX_W/2, y+310, f"（预测日期：{data.get('forecast_date','')}）",
            ha='center', va='center', fontproperties=f_sub, color="#000000", zorder=4)
    y += TITLE_H

    # ── ④ 元信息行 ───────────────────────────────────
    META_X, META_W, META_R = 80, 1760, 27
    grad = np.linspace(0, 1, 256).reshape(256, 1)
    cmap = LinearSegmentedColormap.from_list('mg', [
        (0.0,  (1., 1., 1., 1.0)),
        (0.75, (1., 1., 1., 0.12)),
        (1.0,  (0.059, 0.365, 0.345, 0.35)),
    ])
    ax.imshow(np.tile(cmap(grad), (1, META_W, 1)),
              extent=[META_X, META_X+META_W, y+META_H, y], aspect='auto', zorder=2)
    f_meta = get_font(40, bold=True)
    ax.text(META_X+60,        y+META_H/2, data.get("dept","用电监测分析专班"),
            va='center', fontproperties=f_meta, color="#000000", zorder=4)
    ax.text(META_X+META_W-60, y+META_H/2, data.get("report_date",""),
            ha='right', va='center', fontproperties=f_meta, color="#000000", zorder=4)
    y += META_H + META_MARGIN_B

    # ── ⑤ 预测表 ─────────────────────────────────────
    f_th  = get_font(44, bold=True)
    f_td  = get_font(40, bold=True)
    f_val = get_font(46, bold=True)

    def draw_forecast_table(y_start):
        rows  = data.get("forecast", [])
        tbl_h = TBL_HDR + len(rows) * ROW_H
        clip  = FancyBboxPatch((TBL_X, y_start), TBL_W, tbl_h,
                               boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                               facecolor="none", edgecolor="none", zorder=0)
        ax.add_patch(clip)
        def C(p): p.set_clip_path(clip); p.set_clip_on(True); return p

        C(ax.add_patch(mpatches.Rectangle((TBL_X, y_start), TBL_W, TBL_HDR,
                       facecolor="#1E7976", edgecolor="none", zorder=3)))
        ax.plot([TBL_X+COL1_W]*2, [y_start, y_start+TBL_HDR], color="#2B9B97", lw=1.5, zorder=4)
        ax.text(TBL_X+COL1_W+COL2_W/2, y_start+TBL_HDR/2, "最大负荷（亿千瓦）",
                ha='center', va='center', fontproperties=f_th, color=WHITE, zorder=5)

        for i, row in enumerate(rows):
            y0  = y_start + TBL_HDR + i * ROW_H
            val = row.get("value", "/")
            is_last_row = (i == len(rows) - 1)

            C(ax.add_patch(mpatches.Rectangle((TBL_X,        y0), COL1_W, ROW_H,
                           facecolor="#BCDFE5", edgecolor="#437A83", lw=0.8, zorder=2)))
            C(ax.add_patch(mpatches.Rectangle((TBL_X+COL1_W, y0), COL2_W, ROW_H,
                           facecolor="#EEFDFC", edgecolor="#437A83", lw=0.8, zorder=2)))
            ax.text(TBL_X+COL1_W/2, y0+ROW_H/2, row["label"],
                    ha='center', va='center', fontproperties=f_td, color=DARK, zorder=3)

            if is_last_row and val != "/":
                # 预警信息有内容时用 Pillow 渲染，自动换行，居中
                img_arr = _pil_text_img(val, COL2_W, ROW_H, 46, "#437A83", "#EEFDFC")
                im = ax.imshow(img_arr,
                               extent=[TBL_X+COL1_W, TBL_X+COL1_W+COL2_W, y0+ROW_H, y0],
                               aspect='auto', zorder=3)
                im.set_clip_path(clip); im.set_clip_on(True)
                # 边框补在 imshow 上层
                C(ax.add_patch(mpatches.Rectangle((TBL_X+COL1_W, y0), COL2_W, ROW_H,
                               facecolor='none', edgecolor="#437A83", lw=0.8, zorder=5)))
            else:
                fc = "#aaaaaa" if val == "/" else "#437A83"
                ax.text(TBL_X+COL1_W+COL2_W/2, y0+ROW_H/2, val,
                        ha='center', va='center', fontproperties=f_val, color=fc, zorder=3)

        ax.add_patch(FancyBboxPatch((TBL_X, y_start), TBL_W, tbl_h,
                     boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                     facecolor="none", edgecolor="#437A83", lw=1.2, zorder=6))

    draw_forecast_table(y)
    y += TBL_HDR + n_fc * ROW_H

    # ── ⑥ 复盘表 ─────────────────────────────────────
    y += SEP_H
    rv_start = y    # 记录复盘表起始 y，用于计算实际高度
    rv_tbl_h = rv_h
    rv_clip  = FancyBboxPatch((TBL_X, y), TBL_W, rv_tbl_h,
                              boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                              facecolor="none", edgecolor="none", zorder=0)
    ax.add_patch(rv_clip)
    def RC(p): p.set_clip_path(rv_clip); p.set_clip_on(True); return p

    RC(ax.add_patch(mpatches.Rectangle((TBL_X, y), TBL_W, TBL_HDR,
                    facecolor="#1E7976", edgecolor="none", zorder=3)))
    t = ax.text(TBL_X+TBL_W/2, y+TBL_HDR/2, "昨日公司经营区负荷预测情况复盘",
                ha='center', va='center', fontproperties=f_th, color=WHITE, zorder=5)
    t.set_clip_path(rv_clip); t.set_clip_on(True)
    y += TBL_HDR

    col_hdrs = ["时间","负荷实际值\n（亿千瓦）","负荷预测值\n（亿千瓦）","预测准确率","偏差原因"]
    f_ch = get_font(34, bold=True)
    x = TBL_X
    for cw_i, hdr in zip(rv_cw, col_hdrs):
        RC(ax.add_patch(mpatches.Rectangle((x, y), cw_i, COL_HDR,
                        facecolor="#BCDFE5", edgecolor="#437A83", lw=0.8, zorder=2)))
        t = ax.text(x+cw_i/2, y+COL_HDR/2, hdr,
                    ha='center', va='center', fontproperties=f_ch,
                    color=DARK, zorder=3, linespacing=1.5)
        t.set_clip_path(rv_clip); t.set_clip_on(True)
        x += cw_i
    y += COL_HDR

    for ri, row in enumerate(rv_rows_data):
        cells = [row.get("date",""), row.get("actual",""),
                 row.get("forecast",""), row.get("accuracy",""), row.get("reason","")]
        actual_row_h = row_heights[ri]
        is_last = (ri == len(rv_rows_data) - 1)

        cell_lines = []
        for ci, (cw_i, cell) in enumerate(zip(rv_cw, cells)):
            if ci in (0, 4):
                cell_lines.append(_wrap_by_width(cell, cw_i, 32 if ci==4 else 36, is_date=(ci==0)))
            else:
                cell_lines.append([cell])

        x = TBL_X
        for ci, (cw_i, cell) in enumerate(zip(rv_cw, cells)):
            bg = "#FFFFFF" if is_last else ("#BCDFE5" if ci==0 else "#EEFDFC")

            if ci == 4:
                # 偏差原因：Pillow 渲染，绝对不溢出
                img_arr = _pil_text_img(cell, cw_i, actual_row_h, 44, DARK, bg)
                im = ax.imshow(img_arr,
                          extent=[x, x+cw_i, y+actual_row_h, y],
                          aspect='auto', zorder=3)
                im.set_clip_path(rv_clip)
                im.set_clip_on(True)
                # 补边框
                RC(ax.add_patch(mpatches.Rectangle((x, y), cw_i, actual_row_h,
                             facecolor='none', edgecolor="#437A83", lw=0.8, zorder=4)))
            else:
                RC(ax.add_patch(mpatches.Rectangle((x, y), cw_i, actual_row_h,
                                facecolor=bg, edgecolor="#437A83", lw=0.8, zorder=2)))
                text = "\n".join(cell_lines[ci])
                fs   = _fit_font_size(text, cw_i) if ci in (1,2,3) else 36
                fp   = get_font(fs, bold=True)
                t = ax.text(x+cw_i/2, y+actual_row_h/2, text,
                            ha='center', va='center', fontproperties=fp,
                            color=DARK, zorder=3, linespacing=1.4)
                t.set_clip_path(rv_clip); t.set_clip_on(True)

            x += cw_i
        y += actual_row_h

    # 用实际高度画外框，确保圆角覆盖整张表
    actual_rv_h = y - rv_start
    ax.add_patch(FancyBboxPatch((TBL_X, rv_start), TBL_W, actual_rv_h,
                 boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                 facecolor="none", edgecolor="#437A83", lw=1.2, zorder=6))

    # ── ⑦ Footer ─────────────────────────────────────
    ax.add_patch(mpatches.Rectangle((0, y), PX_W, FOOTER_H, color="#eef4f6", zorder=2))
    ax.plot([0, PX_W], [y, y], color=LINE_C, lw=2, zorder=3)
    ax.text(PX_W/2, y+FOOTER_H/2,
            f"用电监测分析专班 · 内部参考资料 · 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ha='center', va='center', fontproperties=get_font(26), color="#aaaaaa", zorder=3)

    # ── 保存 ─────────────────────────────────────────
    if not output_path:
        output_path = f"{OUT_DIR}/daily_{date.today().strftime('%Y-%m-%d')}.png"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=DPI, bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    print(f"✅ 已生成：{output_path}  ({PX_W}×{TOT_H}px)")
    return output_path


if __name__ == '__main__':
    MOCK = {
        'forecast_date': '2026年6月19日',
        'report_date':   '2026年6月18日',
        'dept':          '用电监测分析专班',
        'forecast': [
            {'label': '6月19日(星期五)', 'value': '10.20'},
            {'label': '未来七天',        'value': '10.85'},
            {'label': '预警信息',        'value': '已触发橙色预警（用电高峰时段11:00-15:00）', 'is_alert': True},
        ],
        'review': [{
            'date':     '6月18日(星期四)',
            'actual':   '10.05',
            'forecast': '9.90',
            'accuracy': '98.5%',
            'reason':   '华东地区出现强对流天气，工业用户错峰生产部分抵消，实际负荷略低于此前修正值',
        }]
    }
    render_daily_png(MOCK, output_path=f"{OUT_DIR}/daily_test.png")
