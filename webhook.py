"""
飞书 Webhook 服务
接收飞书消息 → 解析 → 出图 → 回传
支持：日报（默认）、周报（文字含"周报"或"每周政策"）
"""

import os, sys, json, time, requests
from fastapi import FastAPI, Request, Response, BackgroundTasks
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daily_parser        import parse_daily_report
from daily_png_renderer  import render_daily_png
from weekly_parser       import parse_weekly_report
from weekly_png_renderer import render_weekly_png

app = FastAPI()

# 日报机器人凭证
APP_ID     = os.environ.get("FEISHU_APP_ID",    "cli_aab8fe3742bcdcd6")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "O2MMQJbSlw5MJfmcPXmq8b3yxFurGXem")

# 周报机器人凭证（单独应用）
WEEKLY_APP_ID     = os.environ.get("FEISHU_WEEKLY_APP_ID",     APP_ID)
WEEKLY_APP_SECRET = os.environ.get("FEISHU_WEEKLY_APP_SECRET", APP_SECRET)

# 去重
_processed: dict = {}
_DEDUP_TTL = 300

def _is_processed(msg_id: str, mode: str = "daily") -> bool:
    key = f"{mode}:{msg_id}"
    now = time.time()
    expired = [k for k, v in _processed.items() if now - v > _DEDUP_TTL]
    for k in expired: del _processed[k]
    if key in _processed: return True
    _processed[key] = now
    return False

def get_token(weekly=False):
    aid = WEEKLY_APP_ID if weekly else APP_ID
    asc = WEEKLY_APP_SECRET if weekly else APP_SECRET
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": aid, "app_secret": asc}, timeout=10)
    return r.json().get("tenant_access_token", "")

def upload_image(img_path: str, token: str) -> str:
    with open(img_path, "rb") as f:
        r = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/images",
            headers={"Authorization": f"Bearer {token}"},
            data={"image_type": "message"},
            files={"image": ("image.png", f, "image/png")},
            timeout=30)
    result = r.json()
    print(f"[upload_image] status={r.status_code} response={result}")
    return result.get("data", {}).get("image_key", "")

def send_message(chat_id: str, msg_type: str, content: dict, token: str):
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": chat_id, "msg_type": msg_type, "content": json.dumps(content)},
        timeout=10)

def _cleanup_old_images(out_dir: str, keep: int = 3):
    """只保留最新的 keep 张图片"""
    pngs = sorted(
        [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith('.png')],
        key=os.path.getmtime)
    for f in pngs[:-keep]:
        try: os.remove(f)
        except: pass

def _is_weekly(text: str) -> bool:
    """判断是否周报"""
    keywords = ["周报", "每周政策", "每周信息", "weekly"]
    return any(kw in text[:20] for kw in keywords)

def _run_once(fn, *args, **kwargs):
    """执行一次，若失败重试一次，仍失败抛出异常"""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"[retry] 首次失败: {e}，1秒后重试")
        time.sleep(1)
        return fn(*args, **kwargs)


def process_in_background(text: str, chat_id: str, mode: str = "daily"):
    out_path = None
    weekly   = (mode == "weekly")
    try:
        token   = get_token(weekly)
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d%H%M%S')

        if weekly:
            data     = parse_weekly_report(text)
            out_path = os.path.join(out_dir, f"weekly_{ts}.png")
            paths    = _run_once(render_weekly_png, data, output_path=out_path)
            for p in (paths if isinstance(paths, tuple) else (paths,)):
                if not p: continue
                key = upload_image(p, token)
                if key:
                    send_message(chat_id, "image", {"image_key": key}, token)
                else:
                    send_message(chat_id, "text", {"text": "❌ 图片上传失败"}, token)
                if os.path.exists(p): os.remove(p)
        else:
            data     = parse_daily_report(text)
            out_path = os.path.join(out_dir, f"daily_{ts}.png")
            _run_once(render_daily_png, data, output_path=out_path)
            image_key = upload_image(out_path, token)
            if image_key:
                send_message(chat_id, "image", {"image_key": image_key}, token)
                os.remove(out_path)
            else:
                send_message(chat_id, "text", {"text": "❌ 图片上传失败"}, token)
        _cleanup_old_images(out_dir, keep=3)
    except Exception as e:
        import traceback
        err_detail = traceback.format_exc()
        print(f"[error] {err_detail}")
        if out_path and os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass
        try: send_message(chat_id, "text", {"text": f"❌ 生成失败：{str(e)}"}, get_token(weekly))
        except: pass


def process_file_in_background(file_key: str, msg_id: str, chat_id: str):
    """下载飞书文件 → 解析 Word → 出图（使用周报机器人凭证）"""
    out_path = None
    tmp_docx = None
    try:
        token   = get_token(weekly=True)
        print(f"[file bg] token={'ok' if token else 'EMPTY'} file_key={file_key}")
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)

        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/resources/{file_key}"
        print(f"[file bg] 下载 {url}")
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"type": "file"}, timeout=30)
        print(f"[file bg] 下载状态={r.status_code} 大小={len(r.content)}")
        if r.status_code != 200:
            print(f"[file bg] 下载失败 body={r.text[:200]}")
            send_message(chat_id, "text", {"text": f"❌ 文件下载失败({r.status_code})"}, token)
            return

        tmp_docx = os.path.join(out_dir, f"tmp_{file_key}.docx")
        with open(tmp_docx, "wb") as f:
            f.write(r.content)

        from weekly_docx_parser import parse_weekly_docx
        data     = parse_weekly_docx(tmp_docx)
        ts       = datetime.now().strftime('%Y%m%d%H%M%S')
        out_path = os.path.join(out_dir, f"weekly_{ts}.png")
        paths    = _run_once(render_weekly_png, data, output_path=out_path)
        for p in (paths if isinstance(paths, tuple) else (paths,)):
            if not p: continue
            key = upload_image(p, token)
            if key:
                send_message(chat_id, "image", {"image_key": key}, token)
            else:
                send_message(chat_id, "text", {"text": "❌ 图片上传失败"}, token)
            if os.path.exists(p): os.remove(p)
        _cleanup_old_images(out_dir, keep=3)

    except Exception as e:
        import traceback
        err_detail = traceback.format_exc()
        print(f"[file error] {err_detail}")
        try: send_message(chat_id, "text", {"text": f"❌ 解析失败：{str(e)}"}, get_token(weekly=True))
        except: pass
    finally:
        if tmp_docx and os.path.exists(tmp_docx):
            os.remove(tmp_docx)


@app.post("/webhook")
async def webhook_daily(request: Request, background_tasks: BackgroundTasks):
    """日报机器人入口"""
    return await _handle_webhook(request, background_tasks, mode="daily")

@app.post("/webhook/weekly")
async def webhook_weekly(request: Request, background_tasks: BackgroundTasks):
    """周报机器人入口（支持文字+文件）"""
    return await _handle_webhook(request, background_tasks, mode="weekly")

async def _handle_webhook(request: Request, background_tasks: BackgroundTasks, mode: str):
    body = await request.json()

    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}

    event = body.get("event", {})
    if body.get("header", {}).get("event_type") != "im.message.receive_v1":
        return Response("ok")

    msg     = event.get("message", {})
    chat_id = msg.get("chat_id", "")
    msg_id  = msg.get("message_id", "")

    if _is_processed(msg_id, mode): return Response("ok")

    sender = event.get("sender", {})
    if sender.get("sender_type") == "app": return Response("ok")

    # 只允许群消息，私聊直接忽略
    if msg.get("chat_type") != "group": return Response("ok")

    mentions = event.get("message", {}).get("mentions", [])
    msg_type = msg.get("message_type", "")

    # 文件消息：周报机器人直接处理，不需要 @
    if msg_type == "file" and mode == "weekly":
        try:
            raw_content = msg.get("content", "{}")
            print(f"[weekly file] msg_id={msg_id} chat_id={chat_id} raw_content={raw_content}")
            content   = json.loads(raw_content)
            file_key  = content.get("file_key", "")
            file_name = content.get("file_name", "") or ""
            print(f"[weekly file] file_key={file_key} file_name={file_name}")
            if not file_key:
                print("[weekly file] 无 file_key，跳过")
            elif file_name and not file_name.lower().endswith(".docx"):
                print(f"[weekly file] 非 docx 文件({file_name})，跳过")
            else:
                # file_name 为空时也尝试处理（飞书部分场景不返回 file_name）
                token = get_token(weekly=True)
                send_message(chat_id, "text", {"text": "⚙️ 正在解析文档并生成图片，请稍候..."}, token)
                background_tasks.add_task(process_file_in_background, file_key, msg_id, chat_id)
        except Exception as ex:
            print(f"[weekly file] 解析消息异常: {ex}")
        return Response("ok")

    # weekly 路由只处理文件，文字消息一律忽略
    if mode == "weekly": return Response("ok")

    # 文字消息：需要 @ 机器人
    if not mentions: return Response("ok")

    if msg_type == "text":
        try:
            text = json.loads(msg.get("content", "{}")).get("text", "").strip()
            if "@" in text:
                text = text.split(">")[-1].strip() if ">" in text else text
        except:
            return Response("ok")
        if not text: return Response("ok")
        token = get_token(weekly=False)
        send_message(chat_id, "text", {"text": "⚙️ 正在解析并生成图片，请稍候..."}, token)
        background_tasks.add_task(process_in_background, text, chat_id, mode)

    return Response("ok", status_code=200)


@app.get("/")
async def health():
    return {"status": "ok", "service": "daily-forecast-webhook"}

