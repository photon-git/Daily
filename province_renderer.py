"""
province_renderer.py
用电市场跟踪周榜 —— 用真实素材合成
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

_HERE     = os.path.dirname(os.path.abspath(__file__))
ASSETS    = os.path.join(_HERE, "assets")
OUT_DIR   = os.path.join(_HERE, "output")
FONTS_DIR = os.path.join(_HERE, "fonts")

BG_PATH       = os.path.join(ASSETS, "province_bg.png")
JB_PATH       = os.path.join(ASSETS, "province_jiaobiao.png")
TITLE_PATH    = os.path.join(ASSETS, "province_title.png")
CARD_PATH     = os.path.join(ASSETS, "province_image.png")
CARD_LONG_PATH= os.path.join(ASSETS, "province_image_long.png")
BGKUANG_PATH  = os.path.join(ASSETS, "province_bg-kuang.png")
BGKUANG0_PATH = os.path.join(ASSETS, "province_bg-kuang0.png")
CROWN_PATH    = os.path.join(ASSETS, "花瓣素材_3D立体金属金色皇冠免抠元素_193291528.png")

FONT_R    = os.path.join(FONTS_DIR, "msyh.ttf")
FONT_B    = os.path.join(FONTS_DIR, "msyh-b.ttf")
YSBT      = os.path.join(FONTS_DIR, "ysbt.ttf")
FONT_FB   = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

# ── 尺寸（按 MasterGo 量取）────────────────────────────
W              = 1200    # 画布宽
TOTAL_H        = 3927    # 画布高（参考值）
KUANG0_W, KUANG0_H = 1100, 3749   # 外框
KUANG1_W, KUANG1_H = 1060, 3695   # 内框
IMAGE_W,  IMAGE_H  = 941,  531    # 普通区块底
LONG_W,   LONG_H   = 937,  1594   # 长区块底

PAD_X          = 60
HEADER_H       = 250   # 留更多顶部空间，标题整体下移
TITLE_BAR_H    = 100
CIRCLE_OUT_R   = 100     # 外圆半径（200/2）
CIRCLE_IN_R    = 90      # 内圆半径（180/2）
CIRCLE_COLOR   = (115, 128, 95)   # #73805F
CIRCLE_LW_OUT  = 4       # 外圆粗
CIRCLE_LW_IN   = 2       # 内圆细（外圆的一半）
CIRCLE_GAP_X   = 30
CIRCLE_GAP_Y   = 50
BLK_GAP        = 36
BLK_PAD_TOP    = 30
BLK_PAD_BOT    = 40
BLK_PAD_LR     = 50

# ── 颜色 ──────────────────────────────────────────────
CIRCLE_TEXT    = (0x3A, 0x60, 0x00)   # #3A6000 圆内文字
TEXT_DARK      = (45, 70, 50)
TEXT_BLACK     = (30, 30, 30)
TEXT_GRAY      = (110, 110, 110)
WHITE          = (255, 255, 255)
DELTA_PLUS     = (200, 80, 50)     # 较上周+ 红
DELTA_MINUS    = (60, 130, 80)     # 较上周- 绿


# ── 字体加载（统一思源黑体）─────────────────────────
SHS_R = os.path.join(FONTS_DIR, "SourceHanSansSC-Regular.otf")
SHS_B = os.path.join(FONTS_DIR, "SourceHanSansSC-Bold.otf")
SHS_H = os.path.join(FONTS_DIR, "SourceHanSansSC-Heavy.otf")

def _font(size, bold=False, ysbt=False):
    """统一用思源黑体（bold/普通），ysbt 参数兼容保留但不再生效"""
    path = SHS_B if bold else SHS_R
    for p in [path, SHS_R, FONT_FB]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


# ── 素材缓存 ──────────────────────────────────────────
_CACHE = {}

def _make_gradient_circle(d, top_color=(255,255,255), bottom_color=(234,250,208)):
    """生成 d×d 的圆形渐变图（白→淡绿，180°从上到下）"""
    img = Image.new("RGBA", (d, d), (0,0,0,0))
    arr = np.zeros((d, d, 4), dtype=np.uint8)
    # 纵向线性渐变
    for y in range(d):
        t = y / max(d-1, 1)
        r = int(top_color[0]*(1-t) + bottom_color[0]*t)
        g = int(top_color[1]*(1-t) + bottom_color[1]*t)
        b = int(top_color[2]*(1-t) + bottom_color[2]*t)
        arr[y, :, 0] = r
        arr[y, :, 1] = g
        arr[y, :, 2] = b
        arr[y, :, 3] = 255
    # 圆形 alpha 蒙版
    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d-1, d-1], fill=255)
    img = Image.fromarray(arr, "RGBA")
    img.putalpha(mask)
    return img


def _draw_gradient_text(img, xy, text, font, left_color, right_color):
    """绘制横向线性渐变文字（left_color → right_color）"""
    draw = ImageDraw.Draw(img)
    bb = draw.textbbox((0, 0), text, font=font)
    w = bb[2] - bb[0]
    h = bb[3]
    pad = 10
    cw, ch = w + pad*2, h + pad*2
    # 文字 mask
    text_mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(text_mask).text((pad - bb[0], pad - bb[1]), text, font=font, fill=255)
    # 横向渐变
    grad = np.zeros((ch, cw, 3), dtype=np.uint8)
    for x in range(cw):
        t = x / max(cw-1, 1)
        grad[:, x, 0] = int(left_color[0]*(1-t) + right_color[0]*t)
        grad[:, x, 1] = int(left_color[1]*(1-t) + right_color[1]*t)
        grad[:, x, 2] = int(left_color[2]*(1-t) + right_color[2]*t)
    grad_img = Image.fromarray(grad, "RGB")
    img.paste(grad_img, (xy[0] - pad, xy[1] - pad), text_mask)


def _load(path):
    if path not in _CACHE:
        _CACHE[path] = Image.open(path).convert("RGBA") if os.path.exists(path) else None
    return _CACHE[path]


def render_province_png(data: dict, output_path: str = None) -> str:
    """
    data 结构：
    {
      "title": "用电市场跟踪周榜",
      "date_range": "6月22日-26日",
      "blocks": [
        {"title": "...", "cols": 3, "items": [
            {"name":"省", "value":27, "delta":None}, ...
        ]}
      ]
    }
    """
    f_main_title = ImageFont.truetype(SHS_H, 80) if os.path.exists(SHS_H) else _font(80, bold=True)
    f_date       = ImageFont.truetype(SHS_H, 40) if os.path.exists(SHS_H) else _font(40, bold=True)
    f_block_title= _font(32, bold=True)
    f_card_name  = _font(36, bold=True)
    f_card_val   = _font(48, bold=True)
    f_card_delta = _font(22)

    blocks = data.get("blocks", [])

    # ── 计算每个区块高度 ───────────────────────────────
    block_layouts = []
    total_h = HEADER_H + 150

    for blk in blocks:
        items = blk.get("items", [])
        is_single_row = blk.get("layout") == "single_row"
        cols  = len(items) if is_single_row else blk.get("cols", 3)
        cols  = max(cols, 1)
        rows  = 1 if is_single_row else (len(items) + cols - 1) // cols
        # 单行模式：根据列数动态缩小圆圈半径
        if is_single_row:
            est_grid_w = IMAGE_W - 2 * BLK_PAD_LR
            col_w_est  = (est_grid_w - (cols - 1) * CIRCLE_GAP_X) // cols
            dyn_r = min(CIRCLE_OUT_R, max(40, col_w_est // 2 - 8))
        else:
            dyn_r = CIRCLE_OUT_R
        circle_d = dyn_r * 2
        cell_h = circle_d + 40
        blk_h = (BLK_PAD_TOP + TITLE_BAR_H + 18
                 + rows * cell_h + (rows - 1) * CIRCLE_GAP_Y
                 + BLK_PAD_BOT)
        block_layouts.append({"h": blk_h, "rows": rows, "cols": cols, "cell_h": cell_h, "dyn_r": dyn_r})
        total_h += blk_h + BLK_GAP

    total_h += 200   # 最后一个 image 后留 200px 给框

    # ── 创建画布并铺底 ─────────────────────────────────
    img = Image.new("RGB", (W, total_h), (245, 248, 240))
    bg  = _load(BG_PATH)
    if bg is not None:
        # 平铺背景
        bw, bh = bg.size
        scaled_w = W
        scaled_h = int(bh * scaled_w / bw)
        bg_resized = bg.resize((scaled_w, scaled_h), Image.LANCZOS)
        # 纵向重复贴
        ty = 0
        while ty < total_h:
            img.paste(bg_resized.convert("RGB"), (0, ty))
            ty += scaled_h

    # 双层外框：bg-kuang0 外框 + bg-kuang 内框
    k0 = _load(BGKUANG0_PATH)
    if k0 is not None:
        kw0 = k0.resize((KUANG0_W, total_h - 100), Image.LANCZOS)  # 外框，整图高度减留白
        img.paste(kw0, ((W-KUANG0_W)//2, 50), kw0)

    k1 = _load(BGKUANG_PATH)
    if k1 is not None:
        kw1 = k1.resize((KUANG1_W, total_h - 130), Image.LANCZOS)
        img.paste(kw1, ((W-KUANG1_W)//2, 65), kw1)

    draw = ImageDraw.Draw(img)

    # ── Header 区：logo 左 + 标题居中 ──────────────────
    jb = _load(JB_PATH)
    if jb is not None:
        jh = 110                          # 角标高度（放大）
        jw = int(jb.width * jh / jb.height)
        jb_r = jb.resize((jw, jh), Image.LANCZOS)
        img.paste(jb_r, (120, 100), jb_r)   # x=90 往右移；y=80 往下移

    # 主标题（居中，左→右渐变 #456612 → #73805F）
    title_text = data.get("title", "用电市场跟踪周榜")
    bb = draw.textbbox((0,0), title_text, font=f_main_title)
    tw = bb[2]-bb[0]; th = bb[3]-bb[1]
    _draw_gradient_text(img,
        ((W-tw)//2, (HEADER_H-th)//2 + 80),     # 往下移 80px
        title_text, f_main_title,
        left_color=(0x73, 0x80, 0x5F),
        right_color=(0x45, 0x66, 0x12))

    # 日期（紧跟主标题下方，同样的渐变）
    date_text = f"({data.get('date_range','')})"
    bb_d = draw.textbbox((0,0), date_text, font=f_date)
    dw = bb_d[2]-bb_d[0]
    title_y = (HEADER_H-th)//2 + 80
    _draw_gradient_text(img,
        ((W-dw)//2, title_y + th + 30),   # 主标题下方 30px
        date_text, f_date,
        left_color=(0x73, 0x80, 0x5F),
        right_color=(0x45, 0x66, 0x12))

    y = HEADER_H + 150   # 给主标题+日期留足空间

    # ── 各区块 ─────────────────────────────────────────
    title_img = _load(TITLE_PATH)
    card_img  = _load(CARD_PATH)
    card_long = _load(CARD_LONG_PATH)
    crown_img = _load(CROWN_PATH)

    for blk, layout in zip(blocks, block_layouts):
        blk_top = y
        blk_h   = layout["h"]
        blk_x1  = PAD_X
        blk_x2  = W - PAD_X
        blk_w   = blk_x2 - blk_x1

        # 1. 区块大背景：行数>2用 image_long.png（937×1594），否则 image.png（941×531）
        rows_in_blk = layout["rows"]
        if rows_in_blk > 2 and card_long is not None:
            bg_use = card_long
            bg_w, bg_h = LONG_W, LONG_H
        elif card_img is not None:
            bg_use = card_img
            bg_w, bg_h = IMAGE_W, IMAGE_H
        else:
            bg_use = None
        if bg_use is not None:
            ci = bg_use.resize((bg_w, blk_h), Image.LANCZOS)
            img.paste(ci, ((W-bg_w)//2, blk_top), ci)
            blk_x1 = (W - bg_w) // 2
            blk_x2 = blk_x1 + bg_w
            blk_w  = bg_w

        # 2. 标题条（title.png 固定 497×89，居中）
        if title_img is not None:
            bar_w = 497
            bar_h = 89
            tb = title_img.resize((bar_w, bar_h), Image.LANCZOS)
            bar_x = (W - bar_w) // 2
            bar_y = blk_top + BLK_PAD_TOP
            img.paste(tb, (bar_x, bar_y), tb)

            # 区块标题文字（垂直水平居中）
            bt = blk.get("title", "")
            bb_b = draw.textbbox((0,0), bt, font=f_block_title)
            bw_t = bb_b[2]-bb_b[0]
            bh_t = bb_b[3]-bb_b[1]
            # 用 anchor='lt' 但补偿 ascender 让文字真正垂直居中
            tx = bar_x + (bar_w - bw_t)//2 - bb_b[0]
            ty = bar_y + (bar_h - bh_t)//2 - bb_b[1]
            draw.text((tx, ty), bt, font=f_block_title, fill=WHITE)

        # 3. 圆形卡片网格
        cols     = layout["cols"]
        cell_h   = layout["cell_h"]
        dyn_r    = layout["dyn_r"]
        dyn_in_r = max(int(dyn_r * CIRCLE_IN_R / CIRCLE_OUT_R), 20)
        # 字号随圆圈等比缩放
        scale       = dyn_r / CIRCLE_OUT_R
        f_card_name_s = _font(max(18, int(36 * scale)), bold=True)
        f_card_val_s  = _font(max(16, int(48 * scale)), bold=True)

        grid_top   = blk_top + BLK_PAD_TOP + TITLE_BAR_H + 18
        grid_left  = blk_x1 + BLK_PAD_LR
        grid_right = blk_x2 - BLK_PAD_LR
        grid_w     = grid_right - grid_left
        col_w      = (grid_w - (cols - 1) * CIRCLE_GAP_X) // cols

        items = blk.get("items", [])
        for i, item in enumerate(items):
            r = i // cols
            c = i % cols
            cell_x = grid_left + c * (col_w + CIRCLE_GAP_X)
            cell_y = grid_top  + r * (cell_h + CIRCLE_GAP_Y)

            cx = cell_x + col_w // 2
            cy = cell_y + dyn_r

            # 外圆渐变填充 + 描边
            out_d = dyn_r * 2
            grad_out = _make_gradient_circle(out_d, (255,255,255), (234,250,208))
            img.paste(grad_out, (cx - dyn_r, cy - dyn_r), grad_out)
            draw.ellipse([cx - dyn_r, cy - dyn_r, cx + dyn_r, cy + dyn_r],
                         outline=CIRCLE_COLOR, width=CIRCLE_LW_OUT)

            # 内圆渐变填充 + 描边
            in_d = dyn_in_r * 2
            grad_in = _make_gradient_circle(in_d, (255,255,255), (234,250,208))
            img.paste(grad_in, (cx - dyn_in_r, cy - dyn_in_r), grad_in)
            draw.ellipse([cx - dyn_in_r, cy - dyn_in_r, cx + dyn_in_r, cy + dyn_in_r],
                         outline=CIRCLE_COLOR, width=CIRCLE_LW_IN)

            # 皇冠（rows>2 的区块全部显示；single_row 只给第一名）
            is_single_row_blk = blk.get("layout") == "single_row"
            show_crown = (crown_img is not None and
                          (rows_in_blk > 2 or (is_single_row_blk and i == 0)))
            if show_crown:
                ch_size = max(40, int(100 * scale))
                ch = crown_img.resize((ch_size, ch_size), Image.LANCZOS)
                offset = int(dyn_r * 0.7)
                px = cx - offset - ch_size//2
                py = cy - offset - ch_size//2
                img.paste(ch, (px, py), ch)

            # 圆内文字：有 city/county 就显示三行，否则两行
            name = item.get("name", "")
            city = item.get("city")
            county = item.get("county")

            if city is not None or county is not None:
                f_label = _font(max(12, int(18 * scale)), bold=True)
                f_num   = _font(max(14, int(28 * scale)), bold=True)
                line1   = name

                def _split_parts(label, value, suffix="个"):
                    parts = [(f"{label}:", f_label), (str(value), f_num)]
                    if suffix:
                        parts.append((suffix, f_label))
                    return parts

                bb1 = draw.textbbox((0,0), line1, font=f_card_name_s)
                h1  = bb1[3]-bb1[1]

                line2_parts = _split_parts("地市", city, suffix="") if city is not None else []
                line3_parts = _split_parts("区县", county) if county is not None else []

                # 计算每行宽度和高度
                def _measure(parts):
                    if not parts: return (0, 0)
                    w, h = 0, 0
                    for txt, fnt in parts:
                        bb = draw.textbbox((0,0), txt, font=fnt)
                        w += bb[2]-bb[0]
                        h = max(h, bb[3]-bb[1])
                    return w, h

                w2, h2 = _measure(line2_parts)
                w3, h3 = _measure(line3_parts)
                gap = 10
                total_h_text = h1 + gap + (h2 if line2_parts else 0) + (gap+h3 if line3_parts else 0)
                ty = cy - total_h_text//2

                # 第一行：省名居中
                w1 = bb1[2]-bb1[0]
                draw.text((cx - w1//2 - bb1[0], ty - bb1[1]),
                          line1, font=f_card_name_s, fill=CIRCLE_TEXT)
                ty += h1 + gap

                # 二、三行整组左对齐居中
                block_w = max(w2, w3)
                left_x  = cx - block_w//2

                def _draw_parts(parts, baseline_y, x0):
                    """按基线 baseline_y 对齐绘制（baseline_y = 文字底部 y）"""
                    x = x0
                    for txt, fnt in parts:
                        bb = draw.textbbox((0,0), txt, font=fnt)
                        # bb[3] 是 baseline 到顶端的距离 + 字符高度
                        # 让 (text顶部 + bb[3]) = baseline_y
                        ty_part = baseline_y - bb[3]
                        draw.text((x - bb[0], ty_part), txt, font=fnt, fill=CIRCLE_TEXT)
                        x += bb[2]-bb[0]

                if line2_parts:
                    # baseline = ty + h2 (h2 是行最大高度)
                    _draw_parts(line2_parts, ty + h2, left_x)
                    ty += h2 + gap
                if line3_parts:
                    _draw_parts(line3_parts, ty + h3, left_x)
            else:
                # 两行模式（省名 + 数字）
                val  = str(item.get("value", ""))
                bb_n = draw.textbbox((0,0), name, font=f_card_name_s)
                bb_v = draw.textbbox((0,0), val,  font=f_card_val_s)
                nh = bb_n[3]-bb_n[1]; vh = bb_v[3]-bb_v[1]
                gap = 10
                total_text_h = nh + gap + vh
                top_y = cy - total_text_h//2
                nw = bb_n[2]-bb_n[0]
                draw.text((cx-nw//2-bb_n[0], top_y-bb_n[1]),
                          name, font=f_card_name_s, fill=CIRCLE_TEXT)
                vw = bb_v[2]-bb_v[0]
                val_y = top_y + nh + gap
                draw.text((cx-vw//2-bb_v[0], val_y-bb_v[1]),
                          val, font=f_card_val_s, fill=CIRCLE_TEXT)

        y = blk_top + blk_h + BLK_GAP

    # 保存
    if not output_path:
        today = datetime.now().strftime('%Y-%m-%d')
        output_path = os.path.join(OUT_DIR, f"province_{today}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    print(f"✅ 已生成：{output_path}  ({W}×{total_h}px)")
    return output_path


# ── 测试 ──────────────────────────────────────────────
if __name__ == "__main__":
    MOCK = {
        "title": "用电市场跟踪周榜",
        "date_range": "6月22日-26日",
        "blocks": [
            {
                "title": "报送信息覆盖情况",
                "cols": 3,
                "items": [
                    {"name": "省份", "value": 27},
                    {"name": "地市", "value": 276},
                    {"name": "区县", "value": 212},
                ]
            },
            {
                "title": "地市全覆盖的省",
                "cols": 3,
                "items": [
                    {"name": "河南", "city": "13/13", "county": 20},
                    {"name": "山东", "city": "16/16", "county": 28},
                    {"name": "安徽", "city": "16/16", "county": 22},
                    {"name": "新疆", "city": "14/14", "county": 15},
                    {"name": "辽宁", "city": "14/14", "county": 18},
                    {"name": "甘肃", "city": "14/14", "county": 19},
                    {"name": "江苏", "city": "13/13", "county": 25},
                    {"name": "浙江", "city": "11/11", "county": 30},
                    {"name": "山西", "city": "11/11", "county": 17},
                    {"name": "江西", "city": "11/11", "county": 16},
                    {"name": "福建", "city": "9/9",   "county": 14},
                    {"name": "吉林", "city": "9/9",   "county": 12},
                    {"name": "河北", "city": "11/11", "county": 21},
                    {"name": "蒙东", "city": "5/5",   "county": 8},
                    {"name": "湖北", "city": "13/13", "county": 19},
                ]
            },
            {
                "title": "本周报送信息最多的省",
                "layout": "single_row",
                "cols": 3,
                "items": [
                    {"name": "浙江", "value": 39},
                    {"name": "山东", "value": 33},
                    {"name": "新疆", "value": 16},
                ]
            },
            {
                "title": "本周报送信息最多的市",
                "layout": "single_row",
                "cols": 3,
                "items": [
                    {"name": "杭州", "value": 23},
                    {"name": "宁波", "value": 10},
                    {"name": "金华", "value": 9},
                ]
            },
        ]
    }
    render_province_png(MOCK, output_path=os.path.join(OUT_DIR, "province_test.png"))
