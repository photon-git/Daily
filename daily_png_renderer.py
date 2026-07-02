"""
日负荷预测卡片渲染器
固定画幅 1925×2466px（标准数据：3预测行 + 1复盘行）
主标题：思源Heavy 90pt，中心 y=452
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

# ── 路径 ────────────────────────────────────────────────
_HERE     = os.path.dirname(os.path.abspath(__file__))
BJ_PATH   = os.path.join(_HERE, "assets/bj.png")
JB_PATH   = os.path.join(_HERE, "assets/jiaobiao.png")
LM_PATH   = os.path.join(_HERE, "assets/lm.png")
OUT_DIR   = os.path.join(_HERE, "output")
FONTS_DIR = os.path.join(_HERE, "fonts")
FONT_R    = os.path.join(FONTS_DIR, "SourceHanSansSC-Regular.otf")
FONT_B    = os.path.join(FONTS_DIR, "SourceHanSansSC-Bold.otf")
FONT_H    = os.path.join(FONTS_DIR, "SourceHanSansSC-Heavy.otf")
FONT_FB   = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

# ── 颜色 ────────────────────────────────────────────────
WHITE  = "#FFFFFF"
DARK   = "#00524F"
TEAL   = "#1E7976"
TEAL_L = "#2B9B97"
CELL_B = "#BCDFE5"
CELL_W = "#EEFDFC"
BORDER = "#437A83"
LINE_C = "#BCDFE5"

# ── 画布（固定） ─────────────────────────────────────────
PX_W  = 1925
DPI   = 100

# ── 表格几何 ─────────────────────────────────────────────
TBL_PAD = 37
TBL_W   = 1850
TBL_X   = TBL_PAD
RADIUS  = 40

# 预测表列宽：标签 | 最大负荷 | 降温数值 | 降温占比
COL1_W = 460
COL2_W = 516
COL3_W = 437
COL4_W = 437

# 预测表行高
FC_TH1  = 124    # 第一层表头（"其中，降温负荷"）
FC_TH2  = 108    # 第二层表头（列名）
FC_ROW  = 200    # 数据行

# 复盘表行高
RV_HDR  = 139    # 标题行
RV_CH   = 164    # 列名行
RV_ROW  = 248    # 数据行

# 复盘表列宽（5列，合计 TBL_W）
rv_cw = [507, 338, 341, 320, 0]
rv_cw[4] = TBL_W - sum(rv_cw[:4])   # 341

# ── 固定 Y 锚点 ──────────────────────────────────────────
HDR_H      = 220    # logo 区
TITLE_CY   = 452    # 主标题中心 y（Heavy 90pt）
SUB_CY     = 613    # 副标题中心 y
META_Y     = 763    # 元信息栏顶
META_H     = 140
FC_TBL_Y   = 957    # 预测表顶

FOOTER_H   = 100

# ── 字体缓存 ─────────────────────────────────────────────
_FC = {}
def _fp(size, weight='r'):
    key = (size, weight)
    if key in _FC: return _FC[key]
    if weight == 'h':
        cands = [FONT_H, FONT_B, FONT_FB]
    elif weight == 'b':
        cands = [FONT_B, FONT_H, FONT_FB]
    else:
        cands = [FONT_R, FONT_B, FONT_FB]
    fp = next((FontProperties(fname=p, size=size) for p in cands if os.path.exists(p)),
              FontProperties(size=size))
    _FC[key] = fp
    return fp

# ── 图片素材缓存 ─────────────────────────────────────────
_IC = {}
def _img(path):
    if path not in _IC:
        _IC[path] = mpimg.imread(path) if os.path.exists(path) else None
    return _IC[path]

# ── Pillow 文字渲染（自动换行，绝对不溢出）───────────────
from PIL import Image as PI, ImageDraw as PD, ImageFont as PF

def _pil_cell(text, cw, ch, fs, color, bg, bold=True, pad=48):
    PAD = pad
    img = PI.new("RGBA", (int(cw), int(ch)))
    r,g,b = tuple(int(bg.lstrip('#')[i:i+2],16) for i in (0,2,4))
    img.paste((r,g,b,255), [0,0,int(cw),int(ch)])
    draw = PD.Draw(img)
    pf = None
    cands = ([FONT_B, FONT_H, FONT_R, FONT_FB] if bold else [FONT_R, FONT_B, FONT_FB])
    for p in cands:
        if os.path.exists(p):
            try: pf = PF.truetype(p, fs); break
            except: pass
    if pf is None: pf = PF.load_default()
    lines, cur = [], ""
    for ch_ in text:
        test = cur + ch_
        bb = draw.textbbox((0,0), test, font=pf)
        if bb[2] > cw - PAD*2 and cur:
            lines.append(cur); cur = ch_
        else:
            cur = test
    if cur: lines.append(cur)
    lh = fs + 10
    ty = int((ch - len(lines)*lh) / 2)
    cr,cg,cb = tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))
    for line in lines:
        bb = draw.textbbox((0,0), line, font=pf)
        tx = int((cw - (bb[2]-bb[0])) / 2)
        draw.text((tx, ty), line, font=pf, fill=(cr,cg,cb,255))
        ty += lh
    return np.array(img) / 255.0


def render_daily_png(data: dict, output_path: str = None) -> str:
    n_fc = len(data.get("forecast", []))
    n_rv = len(data.get("review",   []))

    # 总高度由行数决定（标准 3+1 = 2466）
    fc_tbl_h = FC_TH1 + FC_TH2 + n_fc * FC_ROW
    rv_tbl_h = RV_HDR + RV_CH  + n_rv * RV_ROW
    rv_tbl_y = FC_TBL_Y + fc_tbl_h + 60   # 60px 间隔
    TOT_H    = rv_tbl_y + rv_tbl_h + 20

    fig = plt.figure(figsize=(PX_W/DPI, TOT_H/DPI), dpi=DPI)
    ax  = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PX_W); ax.set_ylim(0, TOT_H)
    ax.axis('off'); ax.invert_yaxis()

    # ── ① 背景 ───────────────────────────────────────────
    bj = _img(BJ_PATH)
    if bj is not None:
        ax.imshow(bj, extent=[0, PX_W, TOT_H, 0], aspect='auto', zorder=0)

    lm = _img(LM_PATH)
    if lm is not None:
        half   = lm[:, lm.shape[1]//2:, :]
        disp_h = int(TOT_H * 0.5)
        disp_w = int(half.shape[1] * disp_h / lm.shape[0])
        lm_y   = (TOT_H - disp_h) // 2
        ax.imshow(half, extent=[0, disp_w, lm_y+disp_h, lm_y],
                  aspect='auto', zorder=1, alpha=0.85)

    # ── ② 角标 logo ──────────────────────────────────────
    jb = _img(JB_PATH)
    if jb is not None:
        jb_h = int(HDR_H * 0.75)
        jb_w = int(jb.shape[1] * jb_h / jb.shape[0])
        jb_y = (HDR_H - jb_h) // 2
        ax.imshow(jb, extent=[60, 60+jb_w, jb_y+jb_h, jb_y], aspect='auto', zorder=2)

    # ── ③ 主标题（Heavy 90，中心 y=452）────────────────
    shadow = (181/255, 209/255, 227/255, 0.67)
    ax.text(PX_W/2+8, TITLE_CY+10, "公司经营区日最大用电负荷预测",
            ha='center', va='top', fontproperties=_fp(90,'h'),
            color=shadow, zorder=3)
    ax.text(PX_W/2, TITLE_CY, "公司经营区日最大用电负荷预测",
            ha='center', va='top', fontproperties=_fp(90,'h'),
            color="#000000", zorder=4)

    # ── ④ 副标题 ─────────────────────────────────────────
    ax.text(PX_W/2, SUB_CY, f"（预测日期：{data.get('forecast_date','')}）",
            ha='center', va='top', fontproperties=_fp(48),
            color="#000000", zorder=4)

    # ── ⑤ 元信息栏 ───────────────────────────────────────
    MX = 80; MW = PX_W - MX*2
    grad = np.linspace(0, 1, 256).reshape(1, 256)   # 纵向：行方向
    cmap = LinearSegmentedColormap.from_list('mg', [
        (0.00, (1., 1., 1., 1.0)),
        (0.76, (1., 1., 1., 0.1233)),
        (1.00, (0.059, 0.365, 0.345, 0.35)),
    ])
    ax.imshow(np.tile(cmap(grad), (MW, 1, 1)).transpose(1, 0, 2),
              extent=[MX, MX+MW, META_Y+META_H, META_Y], aspect='auto', zorder=2)
    ax.text(MX+60,     META_Y+META_H/2, data.get("dept","用电监测分析专班"),
            va='center', fontproperties=_fp(40), color="#000000", zorder=4)
    ax.text(MX+MW-60,  META_Y+META_H/2, data.get("report_date",""),
            ha='right', va='center', fontproperties=_fp(40), color="#000000", zorder=4)

    # ── ⑥ 预测表 ─────────────────────────────────────────
    def draw_forecast_table():
        ys    = FC_TBL_Y
        rows  = data.get("forecast", [])
        tbl_h = fc_tbl_h
        x_c1  = TBL_X + COL1_W
        x_c2  = x_c1  + COL2_W
        x_c3  = x_c2  + COL3_W

        clip = FancyBboxPatch((TBL_X, ys), TBL_W, tbl_h,
                              boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                              facecolor="none", edgecolor="none", zorder=0)
        ax.add_patch(clip)
        def C(p): p.set_clip_path(clip); p.set_clip_on(True); return p

        # ── 表头（两层高度合计）─────────────────────────────
        TH_TOTAL = FC_TH1 + FC_TH2

        # 第一层：标签列跨两层、最大负荷列跨两层、右侧降温负荷上层跨两列
        C(ax.add_patch(mpatches.Rectangle((TBL_X, ys), COL1_W, TH_TOTAL,
                       facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=3)))
        C(ax.add_patch(mpatches.Rectangle((x_c1,  ys), COL2_W, TH_TOTAL,
                       facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=3)))
        C(ax.add_patch(mpatches.Rectangle((x_c2,  ys), COL3_W+COL4_W, FC_TH1,
                       facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=3)))
        # 第二层：降温负荷下两列
        C(ax.add_patch(mpatches.Rectangle((x_c2, ys+FC_TH1), COL3_W, FC_TH2,
                       facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=3)))
        C(ax.add_patch(mpatches.Rectangle((x_c3, ys+FC_TH1), COL4_W, FC_TH2,
                       facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=3)))

        # 表头文字
        ax.text(x_c1 + COL2_W/2+ 18, ys + TH_TOTAL/2, "最大负荷（亿千瓦）",
                ha='center', va='center', fontproperties=_fp(40,'b'),
                color=WHITE, zorder=5, linespacing=1.5)
        ax.text(x_c2 + (COL3_W+COL4_W)/2, ys + FC_TH1/2, "其中，降温负荷",
                ha='center', va='center', fontproperties=_fp(40,'b'), color=WHITE, zorder=5)
        ax.text(x_c2 + COL3_W/2 + 18, ys + FC_TH1 + FC_TH2/2, "数值（亿千瓦）",
                ha='center', va='center', fontproperties=_fp(38,'b'), color=WHITE, zorder=5)
        ax.text(x_c3 + COL4_W/2, ys + FC_TH1 + FC_TH2/2, "占比",
                ha='center', va='center', fontproperties=_fp(38,'b'), color=WHITE, zorder=5)

        # 数据行
        for i, row in enumerate(rows):
            y0       = ys + FC_TH1 + FC_TH2 + i * FC_ROW
            is_last  = (i == len(rows) - 1)
            val      = row.get("value",         "/")
            cooling  = row.get("cooling_value", "")
            ratio    = row.get("cooling_ratio",  "")

            # 标签列
            C(ax.add_patch(mpatches.Rectangle((TBL_X, y0), COL1_W, FC_ROW,
                           facecolor=CELL_B, edgecolor=BORDER, lw=0.8, zorder=2)))
            ax.text(TBL_X+COL1_W/2, y0+FC_ROW/2, row.get("label",""),
                    ha='center', va='center', fontproperties=_fp(36,'h'), color=DARK, zorder=3)

            if is_last:
                # 预警信息：后三列合并
                span_w = COL2_W + COL3_W + COL4_W
                C(ax.add_patch(mpatches.Rectangle((x_c1, y0), span_w, FC_ROW,
                               facecolor=CELL_W, edgecolor=BORDER, lw=0.8, zorder=2)))
                if val and val != "/":
                    img_arr = _pil_cell(val, span_w, FC_ROW, 36, BORDER, CELL_W)
                    im = ax.imshow(img_arr,
                                   extent=[x_c1, x_c1+span_w, y0+FC_ROW, y0],
                                   aspect='auto', zorder=3)
                    im.set_clip_path(clip); im.set_clip_on(True)
                    C(ax.add_patch(mpatches.Rectangle((x_c1, y0), span_w, FC_ROW,
                                   facecolor='none', edgecolor=BORDER, lw=0.8, zorder=5)))
                else:
                    ax.text(x_c1+span_w/2, y0+FC_ROW/2, "/",
                            ha='center', va='center', fontproperties=_fp(36,'b'),
                            color=DARK, zorder=3)
            else:
                for xv, cw, txt, bg in [
                    (x_c1, COL2_W, val,            CELL_W),
                    (x_c2, COL3_W, cooling or "/", CELL_B),
                    (x_c3, COL4_W, ratio   or "/", CELL_B),
                ]:
                    C(ax.add_patch(mpatches.Rectangle((xv, y0), cw, FC_ROW,
                                   facecolor=bg, edgecolor=BORDER, lw=0.8, zorder=2)))
                    fc = DARK
                    ax.text(xv+cw/2, y0+FC_ROW/2, txt,
                            ha='center', va='center', fontproperties=_fp(36,'b'),
                            color=fc, zorder=3)

        # 外框
        ax.add_patch(FancyBboxPatch((TBL_X, ys), TBL_W, tbl_h,
                     boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                     facecolor="none", edgecolor=BORDER, lw=1.2, zorder=6))

    draw_forecast_table()

    # ── ⑦ 复盘表 ─────────────────────────────────────────
    def draw_review_table():
        ys   = rv_tbl_y
        rows = data.get("review", [])

        rv_clip = FancyBboxPatch((TBL_X, ys), TBL_W, rv_tbl_h,
                                 boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                                 facecolor="none", edgecolor="none", zorder=0)
        ax.add_patch(rv_clip)
        def R(p): p.set_clip_path(rv_clip); p.set_clip_on(True); return p

        # 标题行
        R(ax.add_patch(mpatches.Rectangle((TBL_X, ys), TBL_W, RV_HDR,
                       facecolor=TEAL, edgecolor="none", zorder=3)))
        t = ax.text(TBL_X+TBL_W/2, ys+RV_HDR/2, "昨日公司经营区负荷预测情况复盘",
                    ha='center', va='center', fontproperties=_fp(44,'b'), color=WHITE, zorder=5)
        t.set_clip_path(rv_clip); t.set_clip_on(True)
        y = ys + RV_HDR

        # 列名行
        col_names = ["时间", "负荷实际值\n（亿千瓦）", "负荷预测值\n（亿千瓦）", "预测准确率", "偏差原因"]
        x = TBL_X
        for cw, nm in zip(rv_cw, col_names):
            R(ax.add_patch(mpatches.Rectangle((x, y), cw, RV_CH,
                           facecolor=CELL_B, edgecolor=BORDER, lw=0.8, zorder=2)))
            t = ax.text(x+cw/2, y+RV_CH/2, nm,
                        ha='center', va='center', fontproperties=_fp(34,'b'),
                        color=DARK, zorder=3, linespacing=1.5)
            t.set_clip_path(rv_clip); t.set_clip_on(True)
            x += cw
        y += RV_CH

        # 数据行
        for ri, row in enumerate(rows):
            cells   = [row.get("date",""), row.get("actual",""),
                       row.get("forecast",""), row.get("accuracy",""), row.get("reason","")]
            is_last = (ri == len(rows)-1)
            x = TBL_X
            for ci, (cw, cell) in enumerate(zip(rv_cw, cells)):
                bg = "#FFFFFF" if is_last else (CELL_B if ci==0 else CELL_W)
                if ci == 4:
                    arr = _pil_cell(cell, cw, RV_ROW, 40, DARK, bg)
                    im  = ax.imshow(arr, extent=[x, x+cw, y+RV_ROW, y],
                                    aspect='auto', zorder=3)
                    im.set_clip_path(rv_clip); im.set_clip_on(True)
                    R(ax.add_patch(mpatches.Rectangle((x, y), cw, RV_ROW,
                                   facecolor='none', edgecolor=BORDER, lw=0.8, zorder=4)))
                else:
                    R(ax.add_patch(mpatches.Rectangle((x, y), cw, RV_ROW,
                                   facecolor=bg, edgecolor=BORDER, lw=0.8, zorder=2)))
                    # 日期列直接显示原始文本（一行）
                    txt = cell
                    fc = "#aaaaaa" if txt in ("/","") else DARK
                    t = ax.text(x+cw/2, y+RV_ROW/2, txt,
                                ha='center', va='center', fontproperties=_fp(36,'b'),
                                color=fc, zorder=3, linespacing=1.4)
                    t.set_clip_path(rv_clip); t.set_clip_on(True)
                x += cw
            y += RV_ROW

        # 外框
        ax.add_patch(FancyBboxPatch((TBL_X, ys), TBL_W, rv_tbl_h,
                     boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                     facecolor="none", edgecolor=BORDER, lw=1.2, zorder=6))

    draw_review_table()

    # ── 保存 ─────────────────────────────────────────────
    if not output_path:
        output_path = os.path.join(OUT_DIR, f"daily_{date.today().strftime('%Y-%m-%d')}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=DPI, facecolor='none')
    plt.close(fig); plt.clf()
    import gc; gc.collect()
    print(f"✅ 已生成：{output_path}  ({PX_W}×{TOT_H}px)")
    return output_path


if __name__ == '__main__':
    MOCK = {
        'forecast_date': '2026年7月1日',
        'report_date':   '2026年6月30日',
        'dept':          '用电监测分析专班',
        'forecast': [
            {'label': '7月1日(星期三)', 'value': '10.75', 'cooling_value': '1.62', 'cooling_ratio': '15.1%'},
            {'label': '未来七天',       'value': '11.45', 'cooling_value': '2.28', 'cooling_ratio': '19.9%'},
            {'label': '预警信息',       'value': '/', 'is_alert': True},
        ],
        'review': [{
            'date':     '6月29日(星期一)',
            'actual':   '10.70',
            'forecast': '10.51',
            'accuracy': '98.2%',
            'reason':   '/',
        }]
    }
    render_daily_png(MOCK, output_path=os.path.join(OUT_DIR, "daily_test.png"))
