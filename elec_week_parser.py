"""
elec_week_parser.py
电量周度数据文本解析器 → 标准化 JSON
只提取：数值、同比增速、备注（其余字段为固定值）
"""

import os, json, re
from openai import OpenAI

SYSTEM_PROMPT = """你是电力系统电量数据解析专家。

从用户输入的任意格式文本中，只提取以下数据，输出严格JSON：

字段说明：
- week_range：本周日期范围（如"2026年6月29日-2026年7月5日"）
- report_date：报送日期（如"2026年7月6日"）
- month_range：月累计日期范围（如"7月1日-5日"）
- year_range：年累计日期范围（如"1月1日-7月5日"）
- week.collect：本周采集电量（亿千瓦时，保留两位小数，如"1490.34"）
- week.collect_yoy：本周采集电量同比增速（如"-2.8%"）
- week.sale：本周售电量（亿千瓦时，保留两位小数）
- week.sale_yoy：本周售电量同比增速
- month.collect：月累计采集电量
- month.collect_yoy：月累计采集电量同比
- month.sale：月累计售电量
- month.sale_yoy：月累计售电量同比
- year.collect：年累计采集电量
- year.collect_yoy：年累计采集电量同比
- year.sale：年累计售电量
- year.sale_yoy：年累计售电量同比
- notes：备注文字（原文照录，无则填""）

注意：
- 数值只保留数字和小数点，不含单位
- 同比格式统一为"x.x%"或"-x.x%"
- 找不到的字段填""

只输出JSON，不要任何解释。

输出格式：
{
  "week_range": "2026年6月29日-2026年7月5日",
  "report_date": "2026年7月6日",
  "month_range": "7月1日-5日",
  "year_range": "1月1日-7月5日",
  "week":  {"collect": "1490.34", "collect_yoy": "-2.8%", "sale": "1376.47", "sale_yoy": "-2.6%"},
  "month": {"collect": "1073.01", "collect_yoy": "-5.0%", "sale": "990.93",  "sale_yoy": "-4.9%"},
  "year":  {"collect": "35296.88","collect_yoy": "4.4%",  "sale": "32532.54","sale_yoy": "4.4%"},
  "notes": "一是本周电量负增长..."
}"""


def parse_elec_week(raw_text: str) -> dict:
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=1000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": raw_text},
        ],
        response_format={"type": "json_object"},
    )
    text = response.choices[0].message.content.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return json.loads(match.group() if match else text)


if __name__ == "__main__":
    test = """
    本周采集电量1490.34亿千瓦时，同比-2.8%；售电量1376.47亿千瓦时，同比-2.6%。
    月累计（7月1-5日）：采集1073.01亿千瓦时，同比-5.0%；售电990.93亿千瓦时，同比-4.9%。
    年累计（1月1日-7月5日）：采集35296.88亿千瓦时，同比4.4%；售电32532.54亿千瓦时，同比4.4%。
    备注：一是本周电量负增长，主要受江浙等地降雨天气影响，平均最高气温较同期低4.8℃，居民用电量同比下降15.4%。
    """
    import json as _json
    result = parse_elec_week(test)
    print(_json.dumps(result, ensure_ascii=False, indent=2))
