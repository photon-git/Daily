"""
飞书 Webhook 服务
接收飞书消息 → 解析 → 出图 → 回传
"""

import os, sys, json, hashlib, hmac, base64, tempfile, requests
from fastapi import FastAPI, Request, Response, BackgroundTasks
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daily_parser       import parse_daily_report
from daily_png_renderer import render_daily_png

app = FastAPI()

APP_ID     = os.environ.get("FEISHU_APP_ID",     "cli_aab8fe3742bcdcd6")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET",  "O2MMQJbSlw5MJfmcPXmq8b3yxFurGXem")

# 去重：记录已处理的消息ID和时间，5分钟内同一消息不重复处理
import time
_processed: dict = {}   # {msg_id: timestamp}
_DEDUP_TTL = 300        # 5分钟

def _is_processed(msg_id: str) -> bool:
    now = time.time()
    # 清理过期记录
    expired = [k for k, v in _processed.items() if now - v > _DEDUP_TTL]
    for k in expired:
        del _processed[k]
    # 检查是否已处理
    if msg_id in _processed:
        return True
    _processed[msg_id] = now
    return False

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
            files={"image": ("image.png", f, "image/png")},
            timeout=30
        )
    result = r.json()
    print(f"[upload_image] status={r.status_code} response={result}")
    return result.get("data", {}).get("image_key", "")

# ── 发送消息 ──────────────────────────────────────────
def send_message(chat_id: str, msg_type: str, content: dict, token: str):
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": chat_id, "msg_type": msg_type, "content": json.dumps(content)},
        timeout=10
    )

def _cleanup_old_images(out_dir: str, keep: int = 5):
    """只保留最新的 keep 张图片，其余删除"""
    pngs = sorted(
        [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith('.png')],
        key=os.path.getmtime
    )
    for f in pngs[:-keep]:
        try: os.remove(f)
        except: pass

def process_in_background(text: str, chat_id: str):
    """后台处理：解析 + 出图 + 发送，不阻塞 webhook 响应"""
    out_path = None
    try:
        token = get_token()
        data  = parse_daily_report(text)
        out_dir  = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"daily_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
        render_daily_png(data, output_path=out_path)
        image_key = upload_image(out_path, token)
        print(f"[webhook] image_key={image_key}")
        if image_key:
            send_message(chat_id, "image", {"image_key": image_key}, token)
            # 上传成功后删除本地文件
            os.remove(out_path)
        else:
            send_message(chat_id, "text", {"text": "❌ 图片上传失败，请稍后重试"}, token)
        # 清理多余旧图，最多保留5张
        _cleanup_old_images(out_dir, keep=5)
    except Exception as e:
        print(f"[error] {e}")
        if out_path and os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass
        try:
            send_message(chat_id, "text", {"text": f"❌ 生成失败：{str(e)}"}, get_token())
        except:
            pass


# ── Webhook 主入口 ────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
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
    msg_id  = msg.get("message_id", "")

    # 去重：同一条消息只处理一次（跨进程文件锁）
    if _is_processed(msg_id):
        return Response("ok")

    # 过滤机器人自己发的消息
    sender = event.get("sender", {})
    if sender.get("sender_type") == "app":
        return Response("ok")

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

    # 只处理 @ 机器人的消息，忽略普通群消息
    mentions = event.get("message", {}).get("mentions", [])
    if not mentions:
        return Response("ok")

    if not text:
        return Response("ok")

    token = get_token()

    # 立即返回 200，后台异步处理（防止飞书超时重试）
    background_tasks.add_task(process_in_background, text, chat_id)
    return Response("ok", status_code=200)


@app.get("/")
async def health():
    return {"status": "ok", "service": "daily-forecast-webhook"}
