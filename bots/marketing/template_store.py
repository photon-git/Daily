"""
营销专业基本情况 Webhook 处理逻辑
- 收到 docx 文件 → 保存为该群当前模板
- 收到 @ + 文字 → 用当前模板替换电力电量段落，回传新 Word
"""
import os

_HERE    = os.path.dirname(os.path.abspath(__file__))
_ROOT    = os.path.dirname(os.path.dirname(_HERE))
TMPL_DIR = os.path.join(_ROOT, "output", "marketing_templates")

DEFAULT_TEMPLATE = os.path.join(
    _ROOT, "assets", "营销专业基本情况 （2026年7月20日）(1).docx"
)


def get_template_path(chat_id: str) -> str:
    """获取该群当前模板路径，没有则返回默认模板"""
    os.makedirs(TMPL_DIR, exist_ok=True)
    path = os.path.join(TMPL_DIR, f"{chat_id}.docx")
    return path if os.path.exists(path) else DEFAULT_TEMPLATE


def save_template(chat_id: str, docx_bytes: bytes):
    """保存上传的 docx 为该群模板"""
    os.makedirs(TMPL_DIR, exist_ok=True)
    path = os.path.join(TMPL_DIR, f"{chat_id}.docx")
    with open(path, "wb") as f:
        f.write(docx_bytes)
    return path
