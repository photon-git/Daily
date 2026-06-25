"""
weekly_parser.py
每周政策信息文本解析器
支持直接粘贴原始格式文本
"""

import os, json, re
from openai import OpenAI

SYSTEM_PROMPT = """你是每周政策信息报告解析专家。

将输入的政策信息文本解析为结构化JSON。

规则：
- title：固定为"每周政策信息"
- time_range：提取时间范围，格式如"2026年6月15日-2026年6月21日"
- sections：按"一、二、三、四、"划分章节
  - heading：章节标题，如"一、中央有关精神"
  - items：该章节下的每条政策
    - index：编号，如"1"
    - title：条目标题（去掉编号前缀）
    - body：正文内容
    - source：来源（括号里的，如"新华社"），没有则为""

只输出JSON，不要解释。

输出格式：
{
  "title": "每周政策信息",
  "time_range": "2026年6月15日-2026年6月21日",
  "sections": [
    {
      "heading": "一、中央有关精神",
      "items": [
        {
          "index": "1",
          "title": "条目标题",
          "body": "正文内容",
          "source": "新华社"
        }
      ]
    }
  ]
}"""


def parse_weekly_report(raw_text: str) -> dict:
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=4000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": raw_text},
        ],
        response_format={"type": "json_object"},
    )
    text = response.choices[0].message.content.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return json.loads(match.group() if match else text)
