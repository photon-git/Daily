"""
run_weekly.py —— 每周政策信息一键出图
支持两种输入：
  1. Word 文件：python3 run_weekly.py report.docx
  2. 自然语言：python3 run_weekly.py（粘贴文字 → Ctrl+D）
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from weekly_png_renderer import render_weekly_png
from datetime import datetime

OUT_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
DEFAULT_DOCX= os.path.join(os.path.dirname(os.path.abspath(__file__)),
              "assets/每周政策信息（6月15日到6月21日）-定稿(3).docx")


def run(data: dict) -> str:
    print(f"   标题：{data['title']}")
    print(f"   时间：{data['time_range']}")
    for sec in data.get('sections', []):
        print(f"   {sec['heading']} ({len(sec['items'])}条)")

    print("\n🎨 生成图片中...")
    today = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    out   = os.path.join(OUT_DIR, f"weekly_{today}.png")
    path  = render_weekly_png(data, output_path=out)
    print(f"   ✅ 已生成：{path}")
    return path


def from_docx(docx_path: str) -> str:
    """Word 文件 → 出图（不需要 API）"""
    from weekly_docx_parser import parse_weekly_docx
    print(f"\n📄 解析 Word 文档：{os.path.basename(docx_path)}")
    data = parse_weekly_docx(docx_path)
    return run(data)


def from_text(raw_text: str) -> str:
    """自然语言 → DeepSeek 解析 → 出图"""
    from weekly_parser import parse_weekly_report
    print("\n⚙️  Agent 解析文本中...")
    data = parse_weekly_report(raw_text)
    return run(data)


def main():
    # 有命令行参数且是 docx 文件
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.exists(path):
            print(f"❌ 文件不存在：{path}")
            sys.exit(1)
        if path.endswith('.docx'):
            from_docx(path)
        else:
            # 当作文本文件
            with open(path, encoding='utf-8') as f:
                from_text(f.read())
        return

    # 无参数：判断是否有默认 docx
    if os.path.exists(DEFAULT_DOCX):
        print("📎 检测到默认 Word 文档，直接解析（无需 API）")
        print("   如需输入文字，请运行：python3 run_weekly.py --text")
        from_docx(DEFAULT_DOCX)
        return

    # 文字输入模式
    print("=" * 55)
    print("  每周政策信息图片生成工具")
    print("  支持 Word 文件或自然语言文字输入")
    print("=" * 55)
    print("请粘贴政策信息文字，按 Ctrl+D 提交：\n")
    try:
        raw = sys.stdin.read().strip()
    except KeyboardInterrupt:
        sys.exit(0)
    if not raw:
        print("❌ 无输入")
        sys.exit(1)
    from_text(raw)


if __name__ == '__main__':
    # --text 强制文字输入模式
    if '--text' in sys.argv:
        sys.argv.remove('--text')
        print("请粘贴政策信息文字，按 Ctrl+D 提交：\n")
        try:
            raw = sys.stdin.read().strip()
        except KeyboardInterrupt:
            sys.exit(0)
        from_text(raw)
    else:
        main()
