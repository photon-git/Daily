"""
weekly_png_renderer.py
每周政策信息图片生成器
输入：结构化 dict
输出：PNG 长图
"""

import os, re
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

_HERE     = os.path.dirname(os.path.abspath(__file__))
JB_PATH    = os.path.join(_HERE, "assets/jiaobiao.png")
WEEKBG_PATH= os.path.join(_HERE, "assets/weekbg.png")
TOP_PATH   = os.path.join(_HERE, "assets/top.png")
KUANG_PATH = os.path.join(_HERE, "assets/kuang.png")
OUT_DIR   = os.path.join(_HERE, "output")
FONTS_DIR = os.path.join(_HERE, "fonts")
FONT_R    = os.path.join(FONTS_DIR, "msyh.ttf")
FONT_B    = os.path.join(FONTS_DIR, "msyh-b.ttf")
FONT_FB   = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

# ── 颜色 ──────────────────────────────────────────────
BG          = (255, 255, 255)
DARK_GREEN  = (30,  90,  60)    # 章节标题
ITEM_GREEN  = (20,  100, 70)    # 条目标题
TEXT_BLACK  = (30,  30,  30)    # 正文
GRAY        = (120, 120, 120)   # 来源
HEADER_BG   = (255, 255, 255)   # 顶部背景（白色）
DIVIDER     = (180, 210, 190)   # 分割线
ITEM_BLUE   = (30,  90,  180)   # 条目标题蓝色

W = 1080   # 画布宽度（手机适配）
PAD_X = 75 # 左右边距
LINE_SP = 25  # 行间距


def _font(size, bold=False):
    path = FONT_B if bold else FONT_R
    for p in [path, FONT_R, FONT_FB]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


def _text_wrap(draw, text, font, max_w):
    """按像素宽度自动换行，返回行列表"""
    if not text:
        return [""]
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        bb = draw.textbbox((0,0), test, font=font)
        if bb[2] > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines or [""]


def _block_height(draw, text, font, max_w):
    """计算一段文字的总高度"""
    lines = _text_wrap(draw, text, font, max_w)
    bb = draw.textbbox((0,0), "测", font=font)
    line_h = bb[3] - bb[1] + LINE_SP
    return len(lines) * line_h


def render_weekly_png(data: dict, output_path: str = None) -> str:
    """
    data 结构：
    {
      "title": "每周政策信息",
      "time_range": "2026年6月15日-2026年6月21日",
      "sections": [
        {
          "heading": "一、中央有关精神",
          "items": [
            {
              "index": "1",
              "title": "中缅高层会谈...",
              "body": "国家主席习近平...",
              "source": "新华社"
            }
          ]
        }
      ]
    }
    """

    # ── 字体 ──────────────────────────────────────────
    YSBT = os.path.join(FONTS_DIR, "ysbt.ttf")
    f_main_title = ImageFont.truetype(YSBT, 108) if os.path.exists(YSBT) else _font(108, bold=True)
    f_time       = ImageFont.truetype(YSBT, 60) if os.path.exists(YSBT) else _font(60)  # 时间也用优设标题黑
    f_section    = _font(50, bold=True)
    f_item_title = _font(42, bold=True)
    f_body       = _font(35)
    f_source     = _font(36)

    content_w   = W - PAD_X * 2
    f_body_bold = _font(36, bold=True)   # 正文加粗字体（在 calc_h 前定义）

    # ── 计算总高度（干运行，精确模拟绘制）──────────────────
    tmp = Image.new("RGB", (W, 100), BG)
    d   = ImageDraw.Draw(tmp)

    def _rich_block_height(runs, max_w):
        """估算富文本段落高度"""
        line_h = d.textbbox((0,0), "测", font=f_body)[3] - d.textbbox((0,0), "测", font=f_body)[1] + LINE_SP
        cur_w, line_count = 0, 1
        for text, is_bold in runs:
            fp = f_body  # 估算用普通字体（加粗宽度相近）
            for ch in text:
                if ch == '\n':
                    line_count += 1
                    cur_w = 0
                    continue
                bb = d.textbbox((0,0), ch, font=fp)
                cw = bb[2] - bb[0]
                if cur_w + cw > max_w and cur_w > 0:
                    line_count += 1
                    cur_w = 0
                cur_w += cw
        return line_count * line_h

    def calc_h():
        """干运行：用临时画布模拟绘制，精确得到总高度"""
        tmp_img  = Image.new("RGB", (W, 99999), BG)
        tmp_draw = ImageDraw.Draw(tmp_img)
        _y = [0]   # 用列表传引用

        bb_t    = tmp_draw.textbbox((0,0), "每周政策信息", font=f_main_title)
        bb_time = tmp_draw.textbbox((0,0), "2026.6.15-2026.6.21", font=f_time)
        _y[0]   = 220 + (bb_t[3]-bb_t[1]) + 24 + (bb_time[3]-bb_time[1]) + 70

        def sim_wrap(text, font):
            lines = _text_wrap(tmp_draw, text, font, content_w)
            lh = tmp_draw.textbbox((0,0),"测",font=font)
            line_h = lh[3]-lh[1] + LINE_SP
            _y[0] += len(lines) * line_h

        def sim_rich(runs):
            line_h_ref = tmp_draw.textbbox((0,0),"测",font=f_body)
            lh = line_h_ref[3]-line_h_ref[1] + LINE_SP
            cur_w, lines = 0, 1
            for text, is_bold in runs:
                fp = f_body_bold if is_bold else f_body
                for ch in text:
                    if ch == '\n':
                        lines += 1; cur_w = 0; continue
                    bb = tmp_draw.textbbox((0,0), ch, font=fp)
                    cw = bb[2]-bb[0]
                    if cur_w + cw > content_w and cur_w > 0:
                        lines += 1; cur_w = 0
                    cur_w += cw
            _y[0] += lines * lh

        for sec in data.get("sections", []):
            _y[0] += 16
            sim_wrap(sec["heading"], f_section)
            _y[0] += 4
            for item in sec.get("items", []):
                _y[0] += 10
                sim_wrap(f"{item['index']}. {item['title']}", f_item_title)
                _y[0] += 2
                body_runs = item.get("body_runs")
                if body_runs:
                    sim_rich(body_runs)
                else:
                    body_text = item.get("body","") + (f"（{item.get('source','')}）" if item.get("source") else "")
                    sim_wrap(body_text, f_body)
                _y[0] += 2
            _y[0] += 6

        return _y[0] + 80   # 下边距

    total_h = calc_h()

    # ── 第二遍：白色画布上只绘制文字 ────────────────────
    img = Image.new("RGB", (W, total_h), (255, 255, 255))

    # 第二遍只画文字，背景/边框在最后合成
    top_h = 260   # 记录 top 高度供后用
    draw = ImageDraw.Draw(img)

    # ── Header：logo 左，标题+时间 右 ──────────────────
    y = 16
    HDR_H_PX = 120

    # 贴 logo（左上，放大）
    if os.path.exists(JB_PATH):
        jb = Image.open(JB_PATH).convert("RGBA")
        jb_h = 120
        jb_w = int(jb.width * jb_h / jb.height)
        jb = jb.resize((jb_w, jb_h), Image.LANCZOS)
        img.paste(jb, (PAD_X, 20), jb)

    # 主标题靠右，黑色加粗，字号放大
    title_text = data.get('title', '每周政策信息')
    bb = draw.textbbox((0,0), title_text, font=f_main_title)
    th = bb[3] - bb[1]
    tw = bb[2] - bb[0]
    tx = W - PAD_X - tw   # 右对齐
    ty = 220   # 继续往下
    draw.text((tx, ty), title_text, font=f_main_title, fill=TEXT_BLACK)

    # 时间右对齐，黑色（紧贴右边缘）
    time_text = f"(时间:{data.get('time_range', '')})"
    bb2 = draw.textbbox((0,0), time_text, font=f_time)
    tx2 = W - 20 - (bb2[2]-bb2[0])   # 更靠右，只留20px边距
    draw.text((tx2, ty + th + 24), time_text, font=f_time, fill=TEXT_BLACK)  # +24 增加间距

    y = ty + th + 24 + (bb2[3]-bb2[1]) + 70   # 正文从标题+时间下方开始，多留30px

    # ── 正文区域边框：贴 kuang.png，透明通道自然混合 ──
    CONTENT_TOP = y - 30
    BOX_W = W - PAD_X * 2 + 60
    BOX_X = PAD_X - 30

    # 边框在最终合成时贴，这里只记录位置
    draw = ImageDraw.Draw(img)

    def draw_text_wrapped(text, font, color, indent=0):
        """普通文本换行绘制"""
        nonlocal y
        lines = _text_wrap(draw, text, font, content_w - indent)
        bb = draw.textbbox((0,0), "测", font=font)
        line_h = bb[3] - bb[1] + LINE_SP
        for line in lines:
            draw.text((PAD_X + indent, y), line, font=font, fill=color)
            y += line_h

    def draw_rich_text(runs, color, indent=0):
        """富文本换行绘制，runs = [(text, is_bold), ...]，支持行内加粗"""
        nonlocal y
        max_w = content_w - indent
        # 先把所有 run 拼成带标记的字符序列
        # 策略：按字符逐个排列，超出宽度换行
        x_offset = 0
        line_h_ref = draw.textbbox((0,0), "测", font=f_body)[3] - draw.textbbox((0,0), "测", font=f_body)[1] + LINE_SP

        # 将 runs 展开成 (char, is_bold) 列表
        chars = []
        for text, is_bold in runs:
            for ch in text:
                chars.append((ch, is_bold))

        # 分行
        lines = []
        cur_line = []
        cur_w = 0
        for ch, is_bold in chars:
            if ch == '\n':
                lines.append(cur_line)
                cur_line = []
                cur_w = 0
                continue
            fp = f_body_bold if is_bold else f_body
            bb = draw.textbbox((0,0), ch, font=fp)
            cw = bb[2] - bb[0]
            if cur_w + cw > max_w and cur_line:
                lines.append(cur_line)
                cur_line = []
                cur_w = 0
            cur_line.append((ch, is_bold))
            cur_w += cw
        if cur_line:
            lines.append(cur_line)

        # 逐行绘制
        for line in lines:
            x = PAD_X + indent
            for ch, is_bold in line:
                fp = f_body_bold if is_bold else f_body
                draw.text((x, y), ch, font=fp, fill=color)
                bb = draw.textbbox((0,0), ch, font=fp)
                x += bb[2] - bb[0]
            y += line_h_ref

    # 各章节
    for sec in data.get("sections", []):
        y += 16
        draw_text_wrapped(sec["heading"], f_section, TEXT_BLACK)
        y += 4

        for item in sec.get("items", []):
            y += 10
            title_text = f"{item['index']}. {item['title']}"
            draw_text_wrapped(title_text, f_item_title, ITEM_BLUE)
            y += 2

            # 正文：有 body_runs 用富文本，否则普通文本
            body_runs = item.get("body_runs")
            source = item.get("source", "")
            if body_runs:
                # body_runs 已含来源，不再重复拼接
                draw_rich_text(body_runs, TEXT_BLACK)
            else:
                body_text = item.get("body", "")
                if source:
                    body_text += f"（{source}）"
                draw_text_wrapped(body_text, f_body, TEXT_BLACK)
            y += 2

        y += 6

    # ── 最终合成：背景 → 边框 → 文字 ────────────────────
    actual_h = y + 80
    text_img = img.crop((0, 0, W, actual_h))   # 文字层

    # 1. 背景层
    final = Image.new("RGB", (W, actual_h), BG)
    if os.path.exists(TOP_PATH):
        top = Image.open(TOP_PATH).convert("RGB").resize((W, top_h), Image.LANCZOS)
        final.paste(top, (0, 0))
    if os.path.exists(WEEKBG_PATH):
        remain = actual_h - top_h
        if remain > 0:
            bg = Image.open(WEEKBG_PATH).convert("RGB").resize((W, remain), Image.LANCZOS)
            final.paste(bg, (0, top_h))

    # 2. 边框层
    if os.path.exists(KUANG_PATH):
        kuang2 = Image.open(KUANG_PATH).convert("RGBA")
        box_h2 = actual_h - CONTENT_TOP
        kuang2 = kuang2.resize((BOX_W, box_h2), Image.LANCZOS)
        final.paste(kuang2, (BOX_X, CONTENT_TOP), kuang2)

    # 3. 贴 logo
    if os.path.exists(JB_PATH):
        jb2 = Image.open(JB_PATH).convert("RGBA")
        jb_h2 = 120
        jb_w2 = int(jb2.width * jb_h2 / jb2.height)
        jb2 = jb2.resize((jb_w2, jb_h2), Image.LANCZOS)
        final.paste(jb2, (PAD_X, 20), jb2)

    # 4. 文字层叠在最上（白色背景区域透出底层）
    # 用 composite：文字画布白色部分透出背景，黑色文字保留
    # 把文字层转为 RGBA，白色区域 alpha=0，文字区域 alpha=255
    import numpy as np
    txt_arr  = np.array(text_img.convert("RGB")).astype(float)
    # 白色(255,255,255)区域设为透明
    mask = np.all(txt_arr > 240, axis=2)   # 近白色区域
    alpha = np.where(mask, 0, 255).astype(np.uint8)
    txt_rgba = np.dstack([txt_arr.astype(np.uint8), alpha])
    txt_layer = Image.fromarray(txt_rgba, "RGBA")
    final = final.convert("RGBA")
    final.paste(txt_layer, (0, 0), txt_layer)
    final = final.convert("RGB")

    # 保存
    if not output_path:
        today = datetime.now().strftime('%Y-%m-%d')
        output_path = os.path.join(OUT_DIR, f"weekly_{today}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final.save(output_path, "PNG")
    print(f"✅ 已生成：{output_path}  ({W}×{actual_h}px)")
    return output_path


if __name__ == '__main__':
    MOCK = {
        'title': '每周政策信息',
        'time_range': '2026.6.15-2026.6.21',
        'sections': [
            {
                'heading': '一、中央有关精神',
                'items': [
                    {
                        'index': '1',
                        'title': '中缅高层会谈拓展中缅在可再生能源、人工智能等领域的合作',
                        'body': '国家主席习近平同来华进行国事访问的缅甸总统敏昂莱举行会谈，就深化发展中缅关系作出进一步规划。习近平指出，中方愿同缅方分享发展经验，共同打造政治上友好互信、发展上互利互惠、安全上协调互促、人文上交融互鉴的中缅命运共同体。中缅经济走廊是两国共建"一带一路"的旗舰项目，双方要在确保安全前提下，稳步推进重点项目建设，持续扩大双边贸易规模，拓展可再生能源、人工智能、数字经济等领域合作，助力缅甸发展经济、改善民生。',
                        'source': '新华社'
                    }
                ]
            },
            {
                'heading': '二、部委政策信息',
                'items': [
                    {
                        'index': '2',
                        'title': '国家发改委、工信部、生态环境部、国资委、国家能源局等五部门联合印发《关于开展重点行业节能降碳改造攻坚三年行动的通知》',
                        'body': '《通知》是继2021年、2023年两项能效政策后的深化，工作重心从标准确立转向强制清零。范围覆盖钢铁、电解铝、水泥、平板玻璃、炼油、乙烯、合成氨、甲醇、煤电9个重点行业，实施周期为2026—2028年。核心目标：工业重点行业能效标杆产能占比平均提高20个百分点，煤电提高15个百分点，基准水平以下产能基本清零；累计形成节能量1亿吨标准煤以上，减排二氧化碳2亿吨以上。保障措施：一是标准倒逼，2028年底前未达基准水平项目淘汰关停；二是电价调节，建立统一差别化电价，对不达标企业加价不超过0.1元/千瓦时；三是财政支持，对改造项目按投资额20%给予中央补助。',
                        'source': '国家发改委'
                    },
                    {
                        'index': '3',
                        'title': '国家发改委召开民营企业座谈会研究当前经济形势和系统推进"六张网"建设',
                        'body': '座谈会结合当前宏观经济形势，聚焦系统推进六张网（水网、新型电网、算力网、新一代通信网、城市地下管网、物流网）基础设施建设、扩大国内有效需求，广泛听取民营市场主体意见建议，畅通民企参与重大基建渠道。会议明确"六张网"建设兼顾传统基础设施补短板与新型基础设施布局，是挖掘内需潜力、构建现代化产业体系的重要支撑。',
                        'source': '国家发改委'
                    },
                    {
                        'index': '4',
                        'title': '工信部、商务部、国家发改委、农业农村部、国家能源局等五部门印发《关于开展2026年新能源汽车下乡活动的通知》',
                        'body': '《通知》旨在推进美丽乡村建设，激活下沉市场消费，补齐乡村绿色出行基础设施短板。本次是第八年新能源汽车下乡活动，本年度符合要求的乡村地区消费者换购新能源汽车，均可申领以旧换新补贴，不受补贴资格数量限制。《通知》部署四项关键任务：一是扩大新能源汽车在乡村的消费；二是推进汽车以旧换新进乡村；三是统筹融合已有品牌活动；四是优化乡村新能源汽车配套环境。',
                        'source': '工信部'
                    },
                    {
                        'index': '5',
                        'title': '国家能源局组织召开全国可再生能源电力开发建设月度（6月）调度视频会',
                        'body': '会议总结2026年1-4月全国可再生能源发展总体情况并部署下一步工作要求。截至2026年4月底，可再生能源发电装机突破24亿千瓦，占全国电力总装机的60.5%；新增装机7516万千瓦，占全部新增装机的70.7%；发电量1.2万亿千瓦时，占全社会用电量36.4%。重点部署七方面工作：加大新能源并网消纳、推进就地就近消纳、加快推进项目建设、做好政策落地实施、完善高比例新能源市场机制、提升企业综合竞争能力、加强工作统筹形成合力。',
                        'source': '国家能源局'
                    }
                ]
            },
            {
                'heading': '三、国内能源行业动态',
                'items': [
                    {
                        'index': '6',
                        'title': '全国首个新能源与智能网联汽车零碳标杆园区建设启动',
                        'body': '北京经开区正式启动国家级零碳园区建设工作，确立了"绿色能源供应、零碳智能制造、循环经济发展、智慧能碳管理"四位一体的建设路径，明确提出到2028年，建成全国首个新能源与智能网联汽车零碳标杆园区。该园区占地面积约9.76平方公里，共涉及25个项目，投资总额约25.7亿元。预计到2028年，园区新建可再生能源年发电量达到10.28亿度。',
                        'source': '央视财经'
                    },
                    {
                        'index': '7',
                        'title': '国家统计局发布5月份国民经济运行总体情况',
                        'body': '5月份国民经济总体平稳、结构持续优化，新动能支撑作用凸显。主要体现：一是工业生产提速，5月全国规模以上工业增加值同比增4.5%；二是服务业平稳增长，服务业生产指数同比增长4.4%；三是外贸大幅提速，当月进出口总额同比增16.9%；四是消费与投资总量承压、结构优化，高技术制造业投资成为重要亮点。',
                        'source': '国家统计局'
                    },
                    {
                        'index': '8',
                        'title': '国家统计局发布2026年5月份能源生产情况',
                        'body': '5月份规模以上工业原煤生产保持较高水平，原油生产稳定增长，天然气生产小幅下降，电力生产增速加快。原煤产量4.0亿吨，同比下降1.7%；原油产量1857万吨，同比增长0.5%；天然气产量217亿立方米，同比下降2.2%；发电量7843亿千瓦时，同比增长4.2%，比4月份加快1.6个百分点。',
                        'source': '国家统计局'
                    },
                    {
                        'index': '9',
                        'title': '2026年全国节能宣传周正式启动',
                        'body': '今年6月15日至21日是我国第36个全国节能宣传周，主题为"节能新起点低碳向未来"。国家发改委联合重庆市人民政府举办启动仪式，介绍"十五五"全面实施碳排放双控工作思路。公司将开展节能宣传进企业、进社区、进农村、进学校、进医院，发放绿色用电手册；依托网上国网APP开展e起节电专题活动；开展供电+能效服务，上门为企业开展能源能效体检。',
                        'source': '国家发改委'
                    }
                ]
            },
            # {
            #     'heading': '四、国际能源动态',
            #     'items': [
            #         {
            #             'index': '10',
            #             'title': '全球电网投资与AI算力基建叠加致使变压器出海高景气周期可持续2-3年',
            #             'body': '当前，全球AI算力建设进入爆发期，电力设备变压器正升级为算力基础设施的核心。受欧美电网老化改造、AI数据中心爆发及新能源并网扩容三重需求共振驱动，头部变压器企业普遍在手订单饱满。我国广东、江苏等地大量变压器工厂已处于满产状态，部分面向数据中心的业务订单排到2027年。业内认为，变压器出海高景气周期至少可持续2-3年，中国企业凭借交期优势加速抢占份额。',
            #             'source': '环球网'
            #         }
            #     ]
            # }
        ]
    }
    render_weekly_png(MOCK, output_path=os.path.join(OUT_DIR, 'weekly_test.png'))
