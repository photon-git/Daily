"""
迎峰度夏最大用电负荷情况 PNG 渲染器
顶部 logo/标题/元信息栏完全复用日报风格（matplotlib）
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
from PIL import Image as PI, ImageDraw as PD, ImageFont as PF

_HERE     = os.path.dirname(os.path.abspath(__file__))
_ROOT     = os.path.dirname(os.path.dirname(_HERE))   # daily/
ASSETS    = os.path.join(_ROOT, "assets")
FONTS_DIR = os.path.join(_ROOT, "fonts")

BJ_PATH  = os.path.join(ASSETS, "bj.png")
LM_PATH  = os.path.join(ASSETS, "lm.png")
JB_PATH  = os.path.join(ASSETS, "jiaobiao.png")

FONT_R = os.path.join(FONTS_DIR, "SourceHanSansSC-Regular.otf")
FONT_B = os.path.join(FONTS_DIR, "SourceHanSansSC-Bold.otf")
FONT_H = os.path.join(FONTS_DIR, "SourceHanSansSC-Heavy.otf")
FONT_MS = os.path.join(FONTS_DIR, "msyh-b.ttf")

# ── 颜色（与日报一致）
WHITE  = "#FFFFFF"
DARK   = "#00524F"
TEAL   = "#1E7976"
TEAL_L = "#2B9B97"
CELL_B = "#BCDFE5"
CELL_W = "#EEFDFC"
CELL_G = "#E5F8F6"
BORDER = "#437A83"

# ── 画布宽度（与日报一致）
PX_W   = 1920
TOT_H_FIXED = 2727
DPI    = 100
TBL_PAD = 37
TBL_W   = 743 + 511 + 511   # = 1765，等于三列之和
TBL_X   = (PX_W - TBL_W) // 2  # 居中
RADIUS  = 40

# ── 顶部固定锚点（与日报一致）
HDR_H    = 220
TITLE_CY = 395
SUB_CY   = 613
META_Y   = 626
META_H   = 140

# 表格起始 y
TBL_Y    = 941

# 表格行高
COL_HDR_H = 139   # 列标题行（公司经营区/全国）
ROW_H     = 129   # 普通数据行
ROW_H2    = 129   # 同上
BAND_H    = 129   # 深色条带行

# 列宽：标签 | 公司经营区 | 全国
COL0 = 743
COL1 = 511
COL2 = 511

# 底部说明区
NOTE_HDR_H = 110
NOTE_ROW_H = 72
NOTE_PAD   = 30
FOOTER_H   = 120

# ── 字体缓存
_FC = {}
def _fp(size, weight='r'):
    key = (size, weight)
    if key in _FC: return _FC[key]
    path = {
        'h': FONT_H, 'b': FONT_B,
        'r': FONT_R, 'm': FONT_MS,
    }.get(weight, FONT_R)
    fp = FontProperties(fname=path, size=size) if os.path.exists(path) \
         else FontProperties(size=size)
    _FC[key] = fp
    return fp

# ── 图片素材缓存
_IC = {}
def _img(path):
    if path not in _IC:
        _IC[path] = mpimg.imread(path) if os.path.exists(path) else None
    return _IC[path]

# ── 文字居中绘制（matplotlib）
def _tc(ax, x, y, w, h, text, fp, color, zorder=5, clip=None, star=False):
    if star:
        t1 = ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                     fontproperties=fp, color="#FF0000", zorder=zorder)
        if clip: t1.set_clip_path(clip); t1.set_clip_on(True)
        ox = fp.get_size() * len(text) * 0.31 + 10
        t2 = ax.text(x + w/2 + ox, y + h/2, "★", ha='left', va='center',
                     fontproperties=fp, color="#FF0000", zorder=zorder)
        if clip: t2.set_clip_path(clip); t2.set_clip_on(True)
        return t1
    t = ax.text(x + w/2, y + h/2, text,
                ha='center', va='center', fontproperties=fp,
                color=color, zorder=zorder)
    if clip:
        t.set_clip_path(clip); t.set_clip_on(True)
    return t

# ── Pillow 文字自动换行渲染（用于底部说明）
def _mpl_wrap(fig, text, max_w_px, fp):
    """用 matplotlib renderer 测量文字宽度并换行"""
    renderer = fig.canvas.get_renderer()
    tmp_ax = fig.add_axes([0,0,0,0])
    tmp_ax.set_xlim(0, PX_W); tmp_ax.set_ylim(0, 100)
    tmp_ax.axis('off')
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        t = tmp_ax.text(0, 0, test, fontproperties=fp)
        bb = t.get_window_extent(renderer=renderer)
        t.remove()
        if bb.width > max_w_px and cur:
            lines.append(cur); cur = ch
        else:
            cur = test
    if cur: lines.append(cur)
    fig.delaxes(tmp_ax)
    return lines


def _wrap_text(text, max_width_pt, fp):
    """用 PIL 估算宽度换行，适配 matplotlib 字号"""
    pf = None
    for p in [FONT_B, FONT_R]:
        if os.path.exists(p):
            try: pf = PF.truetype(p, int(fp.get_size())); break
            except: pass
    if pf is None:
        return [text]
    from PIL import ImageDraw as PD2, Image as PI2
    tmp = PI2.new("RGB", (1, 1))
    draw = PD2.Draw(tmp)
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        bb = draw.textbbox((0,0), test, font=pf)
        if bb[2] > max_width_pt and cur:
            lines.append(cur); cur = ch
        else:
            cur = test
    if cur: lines.append(cur)
    return lines


def _pil_text(text, w, h, fs, color_hex, bg_hex, bold=False):
    img = PI.new("RGBA", (int(w), int(h)))
    r,g,b = tuple(int(bg_hex.lstrip('#')[i:i+2],16) for i in (0,2,4))
    img.paste((r,g,b,255), [0,0,int(w),int(h)])
    draw = PD.Draw(img)
    pf = None
    candidates = [FONT_B, FONT_R] if bold else [FONT_R, FONT_B]
    for p in candidates:
        if os.path.exists(p):
            try: pf = PF.truetype(p, fs); break
            except: pass
    if pf is None: pf = PF.load_default()
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        bb = draw.textbbox((0,0), test, font=pf)
        if bb[2] > w - 100 and cur:
            lines.append(cur); cur = ch
        else:
            cur = test
    if cur: lines.append(cur)
    lh = fs + 14
    ty = int((h - len(lines)*lh) / 2)
    cr,cg,cb = tuple(int(color_hex.lstrip('#')[i:i+2],16) for i in (0,2,4))
    for ln in lines:
        bb = draw.textbbox((0,0), ln, font=pf)
        tx = 30
        draw.text((tx, ty), ln, font=pf, fill=(cr,cg,cb,255))
        ty += lh
    return np.array(img) / 255.0


def render_elec_load_png(data: dict, output_path: str) -> str:
    note   = data.get("note", "")
    tbl_h  = COL_HDR_H + 7 * ROW_H
    NY     = 941 + 1146   # 说明框起始 y

    # ── 第一步：用临时 figure 测量说明框行数，确定总高度
    if note:
        tmp_fig = plt.figure(figsize=(PX_W/DPI, 100/DPI), dpi=DPI)
        # 先按 \n 拆成自然段，再对每段做自动换行
        note_segments = [s.strip() for s in note.split('\n') if s.strip()]
        note_lines_mpl = []
        for seg in note_segments:
            wrapped = _mpl_wrap(tmp_fig, seg, TBL_W - 80, _fp(38,'b'))
            note_lines_mpl.extend(wrapped)
            note_lines_mpl.append("")  # 段落间空一行
        if note_lines_mpl and note_lines_mpl[-1] == "":
            note_lines_mpl.pop()  # 去掉末尾多余空行
        plt.close(tmp_fig)
        note_h = NOTE_HDR_H + sum(58 if ln else 20 for ln in note_lines_mpl) + NOTE_PAD * 2
    else:
        note_lines_mpl = []
        note_h = 0

    FOOTER = 120   # 底部留白（含注释行）
    TOT_H  = NY + note_h + FOOTER if note else NY + tbl_h + FOOTER

    fig = plt.figure(figsize=(PX_W/DPI, TOT_H/DPI), dpi=DPI)
    ax  = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PX_W); ax.set_ylim(0, TOT_H)
    ax.axis('off'); ax.invert_yaxis()

    # ══ ① 背景 ══
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

    # ══ ② 角标 logo ══
    jb = _img(JB_PATH)
    if jb is not None:
        jb_h = int(HDR_H * 0.75)
        jb_w = int(jb.shape[1] * jb_h / jb.shape[0])
        jb_y = (HDR_H - jb_h) // 2
        ax.imshow(jb, extent=[60, 60+jb_w, jb_y+jb_h, jb_y], aspect='auto', zorder=2)

    # ══ ③ 主标题 ══
    shadow = (181/255, 209/255, 227/255, 0.67)
    title  = "迎峰度夏最大用电负荷情况"
    ax.text(PX_W/2+8, TITLE_CY+10, title,
            ha='center', va='top', fontproperties=_fp(90,'h'),
            color=shadow, zorder=3)
    ax.text(PX_W/2, TITLE_CY, title,
            ha='center', va='top', fontproperties=_fp(90,'h'),
            color="#000000", zorder=4)


    # ══ ⑤ 元信息栏（圆角渐变，与日报一致） ══
    MX = 80; MW = PX_W - MX*2
    meta_clip = FancyBboxPatch((MX, META_Y), MW, META_H,
                               boxstyle="round,pad=0,rounding_size=27",
                               facecolor="none", edgecolor="none", zorder=0)
    ax.add_patch(meta_clip)
    grad = np.linspace(0, 1, 256).reshape(1, 256)
    cmap = LinearSegmentedColormap.from_list('mg', [
        (0.00, (1., 1., 1., 1.0)),
        (0.76, (1., 1., 1., 0.1233)),
        (1.00, (0.059, 0.365, 0.345, 0.35)),
    ])
    im = ax.imshow(np.tile(cmap(grad), (MW, 1, 1)).transpose(1, 0, 2),
                   extent=[MX, MX+MW, META_Y+META_H, META_Y], aspect='auto', zorder=2)
    im.set_clip_path(meta_clip); im.set_clip_on(True)
    ax.text(MX+60,    META_Y+META_H/2, data.get("dept", "用电监测分析专班"),
            va='center', fontproperties=_fp(40), color="#000000", zorder=4)
    ax.text(MX+MW-60, META_Y+META_H/2, data.get("report_date", ""),
            ha='right', va='center', fontproperties=_fp(40), color="#000000", zorder=4)

    # ══ ⑥ 表格 ══
    ys   = TBL_Y
    x0   = TBL_X
    x1   = x0 + COL0
    x2   = x1 + COL1
    x3   = x0 + TBL_W

    clip = FancyBboxPatch((x0, ys), TBL_W, tbl_h,
                          boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                          facecolor="none", edgecolor="none", zorder=0)
    ax.add_patch(clip)
    def C(p):
        p.set_clip_path(clip); p.set_clip_on(True); return p

    # 列标题行
    cy = ys
    C(ax.add_patch(mpatches.Rectangle((x0, cy), COL0, COL_HDR_H,
                   facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=3)))
    C(ax.add_patch(mpatches.Rectangle((x1, cy), COL1, COL_HDR_H,
                   facecolor=CELL_B, edgecolor=BORDER, lw=0.8, zorder=3)))
    C(ax.add_patch(mpatches.Rectangle((x2, cy), COL2, COL_HDR_H,
                   facecolor=CELL_B, edgecolor=BORDER, lw=0.8, zorder=3)))
    _tc(ax, x1, cy, COL1, COL_HDR_H, "公司经营区", _fp(42,'b'), DARK, clip=clip)
    _tc(ax, x2, cy, COL2, COL_HDR_H, "全国",       _fp(42,'b'), DARK, clip=clip)
    cy += COL_HDR_H

    d = data
    # 创新高判断：今日值 >= 度夏以来最大值
    def _is_record(today_key, summer_key):
        try:
            return float(d.get(today_key, 0)) >= float(d.get(summer_key, 0))
        except:
            return False

    rf = set(d.get("record_fields", []))  # 兜底：也保留 parser 的判断
    if _is_record("today_max_company", "summer_max_company"): rf.add("today_max_company")
    if _is_record("today_max_grid",    "summer_max_grid"):    rf.add("today_max_grid")
    if _is_record("today_peak_cut_company", "summer_peak_cut_company"): rf.add("today_peak_cut_company")
    if _is_record("today_peak_cut_grid",    "summer_peak_cut_grid"):    rf.add("today_peak_cut_grid")

    def data_row(label, v1, v2, h=ROW_H, f1=None, f2=None):
        nonlocal cy
        C(ax.add_patch(mpatches.Rectangle((x0, cy), COL0, h,
                       facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=2)))
        C(ax.add_patch(mpatches.Rectangle((x1, cy), COL1, h,
                       facecolor=CELL_W, edgecolor=BORDER, lw=0.8, zorder=2)))
        C(ax.add_patch(mpatches.Rectangle((x2, cy), COL2, h,
                       facecolor=CELL_W, edgecolor=BORDER, lw=0.8, zorder=2)))
        _tc(ax, x0, cy, COL0, h, label,  _fp(38,'b'), WHITE, clip=clip)
        _tc(ax, x1, cy, COL1, h, str(v1), _fp(38,'m'), DARK, clip=clip, star=(f1 in rf))
        _tc(ax, x2, cy, COL2, h, str(v2), _fp(38,'m'), DARK, clip=clip, star=(f2 in rf))
        cy += h

    def band_row(label, v1, v2, h=BAND_H):
        nonlocal cy
        C(ax.add_patch(mpatches.Rectangle((x0, cy), COL0, h,
                       facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=3)))
        C(ax.add_patch(mpatches.Rectangle((x1, cy), COL1, h,
                       facecolor=CELL_B, edgecolor=BORDER, lw=0.8, zorder=2)))
        C(ax.add_patch(mpatches.Rectangle((x2, cy), COL2, h,
                       facecolor=CELL_B, edgecolor=BORDER, lw=0.8, zorder=2)))
        _tc(ax, x0, cy, COL0, h, label,  _fp(38,'b'), WHITE, clip=clip)
        _tc(ax, x1, cy, COL1, h, str(v1), _fp(38,'m'), DARK,  clip=clip)
        _tc(ax, x2, cy, COL2, h, str(v2), _fp(38,'m'), DARK,  clip=clip)
        cy += h

    def light_band_row(label, v1, v2, h=BAND_H, cell_color=CELL_W):
        nonlocal cy
        C(ax.add_patch(mpatches.Rectangle((x0, cy), COL0, h,
                       facecolor=TEAL, edgecolor=TEAL_L, lw=0.8, zorder=3)))
        C(ax.add_patch(mpatches.Rectangle((x1, cy), COL1, h,
                       facecolor=cell_color, edgecolor=BORDER, lw=0.8, zorder=2)))
        C(ax.add_patch(mpatches.Rectangle((x2, cy), COL2, h,
                       facecolor=cell_color, edgecolor=BORDER, lw=0.8, zorder=2)))
        _tc(ax, x0, cy, COL0, h, label,  _fp(38,'b'), WHITE, clip=clip)
        _tc(ax, x1, cy, COL1, h, str(v1), _fp(38,'m'), DARK,  clip=clip)
        _tc(ax, x2, cy, COL2, h, str(v2), _fp(38,'m'), DARK,  clip=clip)
        cy += h

    date_lbl = data.get("date_label", "当日")
    next_lbl = data.get("next_date_label", "次日")

    data_row(f"{date_lbl}最大负荷(亿千瓦)",
             d.get("today_max_company","/"), d.get("today_max_grid","/"),
             f1="today_max_company", f2="today_max_grid")
    data_row(f"{date_lbl}削峰负荷(万千瓦)",
             d.get("today_peak_cut_company","/"), d.get("today_peak_cut_grid","/"),
             f1="today_peak_cut_company", f2="today_peak_cut_grid")
    band_row("度夏以来最大负荷(亿千瓦)",
             d.get("summer_max_company","/"), d.get("summer_max_grid","/"))
    band_row("度夏最大削峰负荷(万千瓦)",
             d.get("summer_peak_cut_company","/"), d.get("summer_peak_cut_grid","/"))
    light_band_row("度夏以来创新高次数",
                   d.get("record_high_company","/"), d.get("record_high_grid","/"))
    light_band_row("前一日最大负荷(亿千瓦)",
             d.get("prev_max_company","/"), d.get("prev_max_grid","/"), cell_color=CELL_G)
    band_row(f"{next_lbl}预测值(亿千瓦)",
                   d.get("next_max_company","/"), d.get("next_max_grid","/"))

    # 外框
    ax.add_patch(FancyBboxPatch((x0, ys), TBL_W, tbl_h,
                 boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                 facecolor="none", edgecolor=BORDER, lw=1.2, zorder=6))

    # ══ ⑦ 底部说明框 ══
    if note:
        ny    = NY
        nw    = TBL_W
        nh    = note_h

        n_clip = FancyBboxPatch((x0, ny), nw, nh,
                                boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                                facecolor="none", edgecolor="none", zorder=0)
        ax.add_patch(n_clip)
        def N(p): p.set_clip_path(n_clip); p.set_clip_on(True); return p

        N(ax.add_patch(mpatches.Rectangle((x0, ny), nw, NOTE_HDR_H,
                       facecolor=TEAL, edgecolor="none", zorder=3)))
        t = ax.text(x0+nw/2, ny+NOTE_HDR_H/2, "公司经营区及各省市创新高情况",
                    ha='center', va='center', fontproperties=_fp(40,'b'),
                    color=WHITE, zorder=5)
        t.set_clip_path(n_clip); t.set_clip_on(True)

        # 正文：用 matplotlib 直接画，与第一个表格渲染方式一致
        N(ax.add_patch(mpatches.Rectangle((x0, ny+NOTE_HDR_H), nw, nh-NOTE_HDR_H,
                       facecolor=WHITE, edgecolor="none", zorder=2)))
        ty = ny + NOTE_HDR_H + 30
        left_x   = x0 + 40                                       # 顶格 x
        indent_x = x0 + 40 + int(_fp(38,'b').get_size() * 1.8)  # 首行缩进 x
        has_num  = any(ln and len(ln) >= 2 and ln[0].isdigit() and ln[1] == '.' for ln in note_lines_mpl)
        first_in_seg = True  # 是否是段落的第一行
        for ln in note_lines_mpl:
            if ln:
                is_num_line = has_num and len(ln) >= 2 and ln[0].isdigit() and ln[1] == '.'
                if is_num_line:
                    # 编号行：缩进
                    x_start = indent_x
                    first_in_seg = False
                    # 记录编号宽度供续行对齐用
                    num_prefix = ln[:2]  # "1." "2."
                elif first_in_seg:
                    # 非编号段落首行：缩进
                    x_start = indent_x
                    first_in_seg = False
                else:
                    # 续行：顶格
                    x_start = left_x
                t = ax.text(x_start, ty, ln, va='top',
                            fontproperties=_fp(38,'b'), color=DARK, zorder=4)
                t.set_clip_path(n_clip); t.set_clip_on(True)
                ty += 58
            else:
                first_in_seg = True
                ty += 20  # 段落间距缩小

        ax.add_patch(FancyBboxPatch((x0, ny), nw, nh,
                     boxstyle=f"round,pad=0,rounding_size={RADIUS}",
                     facecolor="none", edgecolor=BORDER, lw=1.2, zorder=6))

        # 底注放框外，星星红色
        t1 = ax.text(x0+40, ny+nh+20, "注：", va='top',
                     fontproperties=_fp(34,'b'), color=DARK, zorder=4)
        ax.text(x0+40+_fp(34,'b').get_size()*2.2, ny+nh+20, "★",  va='top',
                fontproperties=_fp(34,'b'), color="#FF0000", zorder=4)
        ax.text(x0+40+_fp(34,'b').get_size()*3.4, ny+nh+20, " 表示创新高", va='top',
                fontproperties=_fp(34,'b'), color=DARK, zorder=4)

    # ── 保存
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fig.savefig(output_path, dpi=DPI, facecolor='none')
    plt.close(fig); plt.clf()
    import gc; gc.collect()
    return output_path


def _count_note_lines(note: str, max_chars=26) -> int:
    if not note: return 0
    lines, cur = 0, 0
    for ch in note:
        cur += 1
        if cur >= max_chars:
            lines += 1; cur = 0
    return lines + 1
