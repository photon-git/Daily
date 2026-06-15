"""
run_daily.py —— 自然语言输入 → 直接出图
用法：python3 run_daily.py
粘贴任意格式的负荷预测文字，Ctrl+D 提交
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from daily_parser      import parse_daily_report
from daily_png_renderer import render_daily_png
import json
from datetime import datetime

def run(raw_text: str):
    print("\n⚙️  解析文本中...")
    data = parse_daily_report(raw_text)
    print(f"   ✅ 预测日期：{data.get('forecast_date')}")
    print(f"   ✅ 发布日期：{data.get('report_date')}")
    for row in data.get('forecast', []):
        print(f"   📊 {row['label']}：{row['value']}")
    for row in data.get('review', []):
        print(f"   📋 复盘 {row['date']}：实际{row['actual']} 预测{row['forecast']} 准确率{row['accuracy']}")

    print("\n🎨 生成图片中...")
    today = datetime.now().strftime("%Y-%m-%d")
    out = os.path.join(os.path.dirname(__file__), f"output/daily_{today}.png")
    path = render_daily_png(data, output_path=out)
    print(f"   ✅ 图片已生成：{path}")
    return path

def main():
    print("=" * 55)
    print("  日负荷预测图片生成工具")
    print("  支持口语/微信消息/正式报告等任意格式")
    print("=" * 55)
    print("请粘贴预测文字，按 Ctrl+D 提交：\n")
    try:
        raw = sys.stdin.read().strip()
    except KeyboardInterrupt:
        sys.exit(0)
    if not raw:
        print("❌ 无输入")
        sys.exit(1)
    run(raw)

if __name__ == "__main__":
    main()
