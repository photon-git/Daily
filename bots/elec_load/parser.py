"""
elec_load parser
迎峰度夏最大用电负荷情况文本解析器 → 标准化 JSON
"""

import os, json, re
from openai import OpenAI

SYSTEM_PROMPT = """你是电力系统负荷数据解析专家。

从用户输入的任意格式文本中，提取并推断以下数据，输出严格JSON：

字段说明：
- report_date：报送日期（如"2026年7月26日"）
- date_label：当日日期标签（如"7月26日"）
- next_date_label：次日日期标签（如"7月27日"）
- today_max_company：当日公司经营区最大负荷（亿千瓦，保留两位小数）
- today_max_grid：当日全国最大负荷（亿千瓦）
- today_peak_cut_company：当日公司经营区削峰负荷（万千瓦）
- today_peak_cut_grid：当日全国削峰负荷（万千瓦），无则填"/"
- summer_max_company：度夏以来公司经营区最大负荷（亿千瓦）
- summer_max_grid：度夏以来全国最大负荷（亿千瓦）
- summer_peak_cut_company：度夏以来公司经营区最大削峰负荷（万千瓦）
- summer_peak_cut_grid：度夏以来全国最大削峰负荷（万千瓦），无则填"/"
- record_high_company：度夏以来公司经营区创新高次数（整数）
- record_high_grid：度夏以来全国/省级电网创新高次数（整数）
- prev_max_company：前一日公司经营区最大负荷（亿千瓦）
- prev_max_grid：前一日全国最大负荷（亿千瓦）
- next_max_company：次日公司经营区预测值（亿千瓦）
- next_max_grid：次日全国预测值（亿千瓦）
- note：公司经营区及各省市创新高情况说明，必须从原文中原封不动复制粘贴，不得改写、总结或缩减。若有多条编号（1. 2. 等），每条之间用\n分隔。原文中"公司经营区及各省市创新高情况"之后的内容、或以"1."/"2."等编号开头的内容均属于此字段。无则填""

注意：
- 数值只保留数字和小数点，不含单位
- 找不到的字段填"/"
- 日期从文本推断，找不到才填""
- note 字段必须原文复制，禁止任何改动

只输出JSON，不要任何解释。

输出格式：
{
  "report_date": "2026年7月26日",
  "date_label": "7月26日",
  "next_date_label": "7月27日",
  "today_max_company": "11.86",
  "today_max_grid": "14.42",
  "today_peak_cut_company": "127.8",
  "today_peak_cut_grid": "/",
  "summer_max_company": "12.70",
  "summer_max_grid": "15.53",
  "summer_peak_cut_company": "176.7",
  "summer_peak_cut_grid": "/",
  "record_high_company": "2",
  "record_high_grid": "3",
  "prev_max_company": "12.08",
  "prev_max_grid": "15.07",
  "next_max_company": "12.05",
  "next_max_grid": "15.00",
  "note": "1.预计7月29日，上海、江苏负荷创历史新高。\n2.今年度夏以来，公司经营区最大负荷累计3次创新高..."
}"""


def parse_elec_load(raw_text: str) -> dict:
    from datetime import datetime
    today = datetime.now().strftime("%Y年%m月%d日")
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        max_tokens=4000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"（今天是{today}，仅当输入中没有明确日期时才参考此日期）\n\n{raw_text}"},
        ],
        response_format={"type": "json_object"},
    )
    text = response.choices[0].message.content.strip()
    print(f"[elec_load parser] finish_reason={response.choices[0].finish_reason}")
    print(f"[elec_load parser] raw response: {text[:500]}")
    if not text:
        raise ValueError("DeepSeek 返回空内容")
    match = re.search(r'\{.*\}', text, re.DOTALL)
    data = json.loads(match.group() if match else text)
    # 清掉 note 里的标题行
    if "note" in data and data["note"]:
        data["note"] = re.sub(r'^公司经营区及各省市创新高情况[：:]\s*', '', data["note"]).strip()
    return data
