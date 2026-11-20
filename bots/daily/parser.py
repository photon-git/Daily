"""
Agent⑦ 日负荷预测文本解析器
支持口语、微信群消息、流水账等各种自然语言输入
输出标准化 JSON 供 daily_png_renderer.py 使用
"""

import os, json, re
from openai import OpenAI

# 夏季恢复：将以下字段说明和 JSON 示例放回 SYSTEM_PROMPT，停用冬季取暖字段及规则。
# 1. 明日具体日期+星期，value=最大负荷（亿千瓦，保留两位小数），cooling_value=降温负荷数值（亿千瓦，保留两位小数，无则省略），cooling_ratio=降温负荷占比（格式"15.1%"，无则省略）
# 2. 未来七天，value=七天内最大负荷峰值，cooling_value=降温负荷数值（无则省略），cooling_ratio=降温负荷占比（无则省略）
# cooling_value/cooling_ratio 若文中有降温负荷信息则填入，否则省略该字段
# {"label": "6月10日(星期二)", "value": "9.83", "cooling_value": "0.70", "cooling_ratio": "7.1%"},
# {"label": "未来七天", "value": "10.63", "cooling_value": "1.48", "cooling_ratio": "13.9%"},

SYSTEM_PROMPT = """你是电力系统日负荷预测报告解析专家。

从用户输入的任意格式文本中（口语、微信消息、正式报告等）提取关键信息，输出严格JSON。

字段说明：
- forecast_date：预测目标日期，格式"YYYY年M月D日"（明天的日期）
- report_date：报告发布日期，格式"YYYY年M月D日"（今天）
- dept：发布部门，默认"用电监测分析专班"
- forecast：预测表，3行固定：
  1. 明日具体日期+星期，value=最大负荷（亿千瓦，保留两位小数），heating_value=取暖负荷数值（亿千瓦，保留两位小数，无则省略），heating_ratio=取暖负荷占比（如"8.6%"，无则省略）
  2. 未来七天，value=七天内最大负荷峰值（亿千瓦，保留两位小数），heating_value=对应取暖负荷数值，heating_ratio=对应取暖负荷占比（无则省略）
  3. 预警信息，value=预警内容（无则填"/"），is_alert=true
- review：昨日复盘，每行含：
  - date：昨日日期+星期，格式"M月D日(星期X)"
  - actual：实际负荷（亿千瓦，保留两位小数）
  - forecast：预测值（亿千瓦，保留两位小数）
  - accuracy：准确率（格式"99.3%"）
  - reason：偏差原因（无则填"/"）

注意：
- 数值统一保留两位小数
- 星期用中文：一二三四五六日
- 日期若只有月日，结合上下文推断年份
- 当前为冬季版，提取“取暖负荷”“采暖负荷”或“供暖负荷”为 heating_value/heating_ratio；不要把降温负荷填入取暖字段
- 取暖负荷数值统一为亿千瓦、保留两位小数；占比保留原文口径，不擅自补造缺失数据
- 冬季不输出 cooling_value/cooling_ratio 字段，夏季规则保留在代码注释中

只输出JSON，不要任何解释。

输出格式：
{
  "forecast_date": "2026年11月20日",
  "report_date": "2026年11月19日",
  "dept": "用电监测分析专班",
  "forecast": [
    {"label": "11月20日(星期五)", "value": "10.29", "heating_value": "0.89", "heating_ratio": "8.6%"},
    {"label": "未来七天", "value": "10.42", "heating_value": "1.02", "heating_ratio": "9.8%"},
    {"label": "预警信息", "value": "/", "is_alert": true}
  ],
  "review": [
    {
      "date": "11月18日(星期三)",
      "actual": "10.22",
      "forecast": "10.17",
      "accuracy": "99.5%",
      "reason": "/"
    }
  ]
}"""


def parse_daily_report(raw_text: str) -> dict:
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    for attempt in range(3):
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            max_tokens=4000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": raw_text},
            ],
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content
        text = text.strip() if text else ""
        finish = response.choices[0].finish_reason
        print(f"[daily parser] attempt={attempt+1} finish_reason={finish}")
        print(f"[daily parser] raw response: {text[:500]}")
        if text and finish != "length":
            break
    if not text:
        raise ValueError("DeepSeek 连续返回空内容")
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return json.loads(match.group() if match else text)


# ── 测试 ──────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        """今天是2026年11月19日。预测11月20日星期五最大负荷10.29亿千瓦，
        取暖负荷0.89亿千瓦，占比8.6%。未来七天最大负荷10.42亿千瓦，
        取暖负荷1.02亿千瓦，占比9.8%。预警信息/。
        11月18日星期三复盘：实际10.22亿千瓦，预测10.17亿千瓦，准确率99.5%，偏差原因/。""",
    ]

    # 夏季 API 试跑输入保留，恢复时可替换冬季 tests：
    # tests = [
    #     # 口语流水账
    #     """各位，今天是6月9日，明天6月10日（周二）预计全网最大负荷9.83亿千瓦，
    #     降温负荷0.70亿千瓦，占比7.1%。未来七天峰值预计10.63亿千瓦，降温负荷1.48亿千瓦占13.9%，
    #     暂无预警。昨天6月8日实际跑了9.39，我们预测的是9.52，准确率98.6%，偏差不大。""",
    #
    #     # 微信群消息风格
    #     """6/10号数据：
    #     明天11号（周四）预测10.2亿，降温0.95/9.3%
    #     七天最高10.9亿，降温1.6/14.7%
    #     预警：无
    #     昨天10号复盘：实际9.8 预测9.75 准确率99.5% 原因/""",
    #
    #     # 正式风格+偏差原因
    #     """预测日期是明天6月12日星期五，最大负荷预计9.60亿千瓦，降温负荷0.55亿千瓦，占比5.7%。
    #     七天内高点在10.40亿千瓦，降温1.30亿千瓦，13%左右，无预警信息。
    #     昨天6月10日复盘一下：实际用电9.75亿千瓦，我们报的是9.50亿千瓦，准确率97.4%，
    #     偏差原因是华南地区气温比预期高了2度左右，空调负荷超了预期。"""
    # ]

    for i, text in enumerate(tests, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}:")
        print(text.strip()[:80] + "...")
        result = parse_daily_report(text)
        print(f"\n解析结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
