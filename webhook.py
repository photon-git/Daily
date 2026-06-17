"""
飞书 Webhook 服务
接收飞书消息 → 解析 → 出图 → 回传
"""

import os, sys, json, hashlib, hmac, base64, tempfile, requests
from fastapi import FastAPI, Request, Response
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daily_parser       import parse_daily_report
from daily_png_renderer import render_daily_png

app = FastAPI()

APP_ID     = os.environ.get("FEISHU_APP_ID",     "cli_aab8fe3742bcdcd6")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET",  "O2MMQJbSlw5MJfmcPXmq8b3yxFurGXem")
VERIFY_TOKEN = os.environ.get("FEISHU_VERIFY_TOKEN", "")

# ── 获取飞书 access token ─────────────────────────────
def get_token():
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=10
    )
    return r.json().get("tenant_access_token", "")

# ── 上传图片到飞书 ────────────────────────────────────
def upload_image(img_path: str, token: str) -> str:
    with open(img_path, "rb") as f:
        r = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/images",
            headers={"Authorization": f"Bearer {token}"},
            data={"image_type": "message"},
            files={"image": f},
            timeout=30
        )
    return r.json().get("data", {}).get("image_key", "")

# ── 发送消息 ──────────────────────────────────────────
def send_message(chat_id: str, msg_type: str, content: dict, token: str):
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": chat_id, "msg_type": msg_type, "content": json.dumps(content)},
        timeout=10
    )

# ── Webhook 主入口 ────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()

    # 飞书 URL 验证（第一次配置时）
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}

    # 只处理消息事件
    event = body.get("event", {})
    if body.get("header", {}).get("event_type") != "im.message.receive_v1":
        return Response("ok")

    msg     = event.get("message", {})
    chat_id = msg.get("chat_id", "")

    # 只处理文字消息
    if msg.get("message_type") != "text":
        return Response("ok")

    # 提取文字内容
    try:
        text = json.loads(msg.get("content", "{}")).get("text", "").strip()
        # 去掉 @机器人 前缀
        if "@" in text:
            text = text.split(">")[-1].strip() if ">" in text else text
    except:
        return Response("ok")

    if not text:
        return Response("ok")

    token = get_token()

    # 发"处理中"提示
    send_message(chat_id, "text", {"text": "⚙️ 正在解析并生成图片，请稍候..."}, token)

    try:
        # 解析文本
        data = parse_daily_report(text)

        # 生成图片
        out_dir  = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"daily_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
        render_daily_png(data, output_path=out_path)

        # 上传并发送图片
        image_key = upload_image(out_path, token)
        if image_key:
            send_message(chat_id, "image", {"image_key": image_key}, token)
        else:
            send_message(chat_id, "text", {"text": "❌ 图片上传失败，请稍后重试"}, token)

    except Exception as e:
        send_message(chat_id, "text", {"text": f"❌ 生成失败：{str(e)}"}, token)

    return Response("ok")


@app.get("/")
async def health():
    return {"status": "ok", "service": "daily-forecast-webhook"}
