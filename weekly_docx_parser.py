"""
weekly_docx_parser.py
直接解析 Word 文档，保留加粗信息
输出结构化 dict 供 weekly_png_renderer 使用
"""

import re
from docx import Document

# Unicode 上标/下标字符 → 普通数字/字母映射
_SUP_MAP = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ', '0123456789+-n')
_SUB_MAP = str.maketrans('₀₁₂₃₄₅₆₇₈₉₊₋', '0123456789+-')
_SUP_CHARS = set('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ')
_SUB_CHARS = set('₀₁₂₃₄₅₆₇₈₉₊₋')

def _convert_unicode_scripts(text: str) -> list:
    """把含 Unicode 上下标字符的文本拆分成 [(片段, 类型)] 列表
    类型: 'normal' / 'super' / 'sub'
    """
    segments = []
    cur, cur_type = '', 'normal'
    for ch in text:
        if ch in _SUP_CHARS:
            t = 'super'; c = ch.translate(_SUP_MAP)
        elif ch in _SUB_CHARS:
            t = 'sub';   c = ch.translate(_SUB_MAP)
        else:
            t = 'normal'; c = ch
        if t != cur_type:
            if cur: segments.append((cur, cur_type))
            cur, cur_type = c, t
        else:
            cur += c
    if cur: segments.append((cur, cur_type))
    return segments


def parse_weekly_docx(docx_path: str) -> dict:
    doc = Document(docx_path)
    paras = [p for p in doc.paragraphs if p.text.strip()]

    # 提取标题和时间
    title = paras[0].text.strip() if paras else "每周政策信息"
    time_range = ""
    if len(paras) > 1:
        t = paras[1].text.strip()
        m = re.search(r'(\d{4})年(\d+)月(\d+)日.+?(\d+)月(\d+)日', t)
        if m:
            y, m1, d1, m2, d2 = m.groups()
            time_range = f"{y}.{m1}.{d1}-{y}.{m2}.{d2}"
        else:
            time_range = t.strip("（）()")

    # 跳过目录（找到正文开始位置）
    # 正文特征：章节标题"一、二、三、四、"不含页码
    start_idx = 0
    for i, p in enumerate(paras):
        text = p.text.strip()
        if re.match(r'^[一二三四五六七八九十]、', text) and '\t' not in text:
            # 第一个不含tab的章节标题 = 正文开始
            start_idx = i
            break

    body_paras = paras[start_idx:]

    # 解析章节和条目
    sections = []
    current_section = None
    current_item = None

    for para in body_paras:
        text = para.text.strip()
        if not text:
            continue

        # 章节标题：一、二、三、四、
        if re.match(r'^[一二三四五六七八九十]、', text) and not re.match(r'^\d+\.', text):
            current_section = {"heading": text, "items": []}
            sections.append(current_section)
            current_item = None
            continue

        # 条目标题：1. 2. 3. ...
        if re.match(r'^\d+[\.．]', text) and current_section is not None:
            # 提取来源（末尾括号）
            source_match = re.search(r'[（(]([^）)]+)[）)]$', text)
            source = source_match.group(1) if source_match else ""
            clean_title = re.sub(r'\s*[（(][^）)]+[）)]\s*$', '', text).strip()
            # 去掉编号前缀
            idx_match = re.match(r'^(\d+)[\.．]\s*', clean_title)
            index = idx_match.group(1) if idx_match else str(len(current_section["items"])+1)
            item_title = re.sub(r'^\d+[\.．]\s*', '', clean_title)
            current_item = {
                "index": index,
                "title": item_title,
                "body_runs": [],   # [(text, is_bold), ...]
                "source": source
            }
            current_section["items"].append(current_item)
            continue

        # 正文段落（属于当前条目）
        if current_item is not None:
            # 提取末尾来源
            full_text = text
            source_match = re.search(r'[（(]([^）)]{2,10})[）)]\s*$', full_text)
            if source_match and not current_item["source"]:
                current_item["source"] = source_match.group(1)
                full_text = full_text[:source_match.start()].strip()

            # 按 run 提取加粗信息，上标加 ^ 前缀，下标加 _ 前缀
            runs = []
            for run in para.runs:
                if not run.text:
                    continue
                bold = bool(run.bold)
                rPr = run._r.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}vertAlign')
                if rPr is not None:
                    val = rPr.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                    if val == 'superscript':
                        runs.append((f"^{run.text}", bold))
                        continue
                    elif val == 'subscript':
                        runs.append((f"_{run.text}", bold))
                        continue
                # 处理 Unicode 上下标字符（如 CO₂ 里的 ₂）
                for seg_text, seg_type in _convert_unicode_scripts(run.text):
                    if seg_type == 'super':
                        runs.append((f"^{seg_text}", bold))
                    elif seg_type == 'sub':
                        runs.append((f"_{seg_text}", bold))
                    else:
                        runs.append((seg_text, bold))
            if runs:
                # 如果已有正文，加换行
                if current_item["body_runs"]:
                    current_item["body_runs"].append(("\n", False))
                current_item["body_runs"].extend(runs)

    # 转成最终格式（body_runs 保留，同时生成纯文本 body 供高度估算）
    for sec in sections:
        for item in sec["items"]:
            item["body"] = "".join(t for t, _ in item["body_runs"])

    return {
        "title": title,
        "time_range": time_range,
        "sections": sections
    }


if __name__ == "__main__":
    import json
    data = parse_weekly_docx(
        '/apdcephfs_tj5/share_303641714/hunyuan/bruceyhao/agent/daily/assets/'
        '每周政策信息（6月15日到6月21日）-定稿(3).docx'
    )
    print(f"标题: {data['title']}")
    print(f"时间: {data['time_range']}")
    for sec in data["sections"]:
        print(f"\n{sec['heading']}")
        for item in sec["items"]:
            print(f"  [{item['index']}] {item['title'][:40]}")
            bold_parts = [t for t,b in item["body_runs"] if b]
            if bold_parts:
                print(f"       加粗片段: {bold_parts[:2]}")
