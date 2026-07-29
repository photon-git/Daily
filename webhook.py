"""
飞书 Webhook 服务
接收飞书消息 → 解析 → 出图 → 回传
支持：日报（默认）、周报（文字含"周报"或"每周政策"）
"""

import os, sys, json, time, requests
from fastapi import FastAPI, Request, Response, BackgroundTasks
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bots.daily.parser       import parse_daily_report
from bots.daily.renderer     import render_daily_png
from bots.weekly.parser      import parse_weekly_report
from bots.weekly.renderer    import render_weekly_png
from bots.province.parser    import parse_xlsx
from bots.province.renderer  import render_province_png
from bots.elec_week.parser   import parse_elec_week
from bots.elec_week.renderer import render_elec_week_png
from bots.elec_load.parser      import parse_elec_load
from bots.elec_load.renderer    import render_elec_load_png
from bots.marketing.generator   import generate_marketing_docx
from bots.marketing.template_store import get_template_path, save_template

app = FastAPI()

# 日报机器人凭证
APP_ID     = os.environ.get("FEISHU_APP_ID",     "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

# 周报机器人凭证（单独应用）
WEEKLY_APP_ID     = os.environ.get("FEISHU_WEEKLY_APP_ID",     APP_ID)
WEEKLY_APP_SECRET = os.environ.get("FEISHU_WEEKLY_APP_SECRET", APP_SECRET)

# 省份周榜机器人凭证（单独应用）
PROVINCE_APP_ID     = os.environ.get("FEISHU_PROVINCE_APP_ID",     "")
PROVINCE_APP_SECRET = os.environ.get("FEISHU_PROVINCE_APP_SECRET", "")

# 电量周度数据机器人凭证（单独应用）
ELEC_APP_ID     = os.environ.get("FEISHU_ELEC_APP_ID",     "")
ELEC_APP_SECRET = os.environ.get("FEISHU_ELEC_APP_SECRET", "")

# 迎峰度夏负荷机器人凭证
ELEC_LOAD_APP_ID     = os.environ.get("FEISHU_ELEC_LOAD_APP_ID",     "")
ELEC_LOAD_APP_SECRET = os.environ.get("FEISHU_ELEC_LOAD_APP_SECRET", "")

# 营销基本情况机器人凭证
MARKETING_APP_ID     = os.environ.get("FEISHU_MARKETING_APP_ID",     "")
MARKETING_APP_SECRET = os.environ.get("FEISHU_MARKETING_APP_SECRET", "")

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

def get_token(weekly=False, province=False, elec=False, elec_load=False, marketing=False):
    if marketing:
        aid, asc = MARKETING_APP_ID, MARKETING_APP_SECRET
    elif elec_load:
        aid, asc = ELEC_LOAD_APP_ID, ELEC_LOAD_APP_SECRET
    elif elec:
        aid, asc = ELEC_APP_ID, ELEC_APP_SECRET
    elif province:
        aid, asc = PROVINCE_APP_ID, PROVINCE_APP_SECRET
    elif weekly:
        aid, asc = WEEKLY_APP_ID, WEEKLY_APP_SECRET
    else:
        aid, asc = APP_ID, APP_SECRET
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

def upload_file(file_path: str, token: str, file_name: str = None) -> str:
    """上传文件到飞书，返回 file_key"""
    name = file_name or os.path.basename(file_path)
    with open(file_path, "rb") as f:
        r = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": "docx", "file_name": name},
            files={"file": (name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            timeout=30)
    result = r.json()
    print(f"[upload_file] status={r.status_code} response={result}")
    return result.get("data", {}).get("file_key", "")

def send_file(chat_id: str, file_key: str, token: str):
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"receive_id": chat_id, "msg_type": "file",
              "content": json.dumps({"file_key": file_key})},
        timeout=10)

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
    keywords = ["周报", "每周政策", "每周信息", "weekly"]
    return any(kw in text[:20] for kw in keywords)

def _is_elec_week(text: str) -> bool:
    keywords = ["采集电量", "售电量", "周电量", "电量周"]
    return any(kw in text[:50] for kw in keywords)

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
    weekly    = (mode == "weekly")
    elec      = (mode == "elec_week")
    elec_load = (mode == "elec_load")
    try:
        token   = get_token(weekly)
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d%H%M%S')

        if elec_load:
            data      = parse_elec_load(text)
            out_path  = os.path.join(out_dir, f"elec_load_{ts}.png")
            _run_once(render_elec_load_png, data, output_path=out_path)
            image_key = upload_image(out_path, get_token(elec_load=True))
            if image_key:
                send_message(chat_id, "image", {"image_key": image_key}, get_token(elec_load=True))
                os.remove(out_path)
            else:
                send_message(chat_id, "text", {"text": "❌ 图片上传失败"}, get_token(elec_load=True))
        elif elec:
            data     = parse_elec_week(text)
            out_path = os.path.join(out_dir, f"elec_week_{ts}.png")
            _run_once(render_elec_week_png, data, output_path=out_path)
            image_key = upload_image(out_path, get_token(elec=True))
            if image_key:
                send_message(chat_id, "image", {"image_key": image_key}, get_token(elec=True))
                os.remove(out_path)
            else:
                send_message(chat_id, "text", {"text": "❌ 图片上传失败"}, get_token(elec=True))
        elif weekly:
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

        from bots.weekly.docx_parser import parse_weekly_docx
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


def process_province_in_background(file_key: str, msg_id: str, chat_id: str, file_name: str = ""):
    """下载飞书 xlsx 文件 → 解析 → 出图 → 回传"""
    out_path = None
    tmp_xlsx = None
    try:
        token   = get_token(province=True)
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)

        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/resources/{file_key}"
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                         params={"type": "file"}, timeout=30)
        print(f"[province] 下载状态={r.status_code} 大小={len(r.content)}")
        if r.status_code != 200:
            send_message(chat_id, "text", {"text": f"❌ 文件下载失败({r.status_code})"}, token)
            return

        tmp_xlsx = os.path.join(out_dir, f"tmp_{file_key}.xlsx")
        with open(tmp_xlsx, "wb") as f:
            f.write(r.content)

        data     = parse_xlsx(tmp_xlsx, date_range="")  # date_range 从原始文件名提取
        # 用原始文件名提取日期，tmp 文件名里没有日期信息
        from bots.province.parser import _extract_date_range
        date_range = _extract_date_range(file_name) if file_name else ""
        data["date_range"] = date_range
        ts       = datetime.now().strftime('%Y%m%d%H%M%S')
        out_path = os.path.join(out_dir, f"province_{ts}.png")
        _run_once(render_province_png, data, output_path=out_path)

        image_key = upload_image(out_path, token)
        if image_key:
            send_message(chat_id, "image", {"image_key": image_key}, token)
        else:
            send_message(chat_id, "text", {"text": "❌ 图片上传失败"}, token)
        _cleanup_old_images(out_dir, keep=3)

    except Exception as e:
        import traceback
        print(f"[province error] {traceback.format_exc()}")
        try: send_message(chat_id, "text", {"text": f"❌ 生成失败：{str(e)}"}, get_token(province=True))
        except: pass
    finally:
        if tmp_xlsx and os.path.exists(tmp_xlsx):
            os.remove(tmp_xlsx)
        if out_path and os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass


def process_marketing_template(file_key: str, msg_id: str, chat_id: str):
    """下载 docx → 保存为该群模板"""
    try:
        token = get_token(marketing=True)
        r = requests.get(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/resources/{file_key}",
            headers={"Authorization": f"Bearer {token}"},
            params={"type": "file"}, timeout=30)
        if r.status_code != 200:
            send_message(chat_id, "text", {"text": f"❌ 文件下载失败({r.status_code})"}, token)
            return
        save_template(chat_id, r.content)
        send_message(chat_id, "text", {"text": "✅ 模板已更新，下次 @ 我发送电力电量内容即可生成新版 Word。"}, token)
    except Exception as e:
        import traceback; print(f"[marketing template error] {traceback.format_exc()}")
        try: send_message(chat_id, "text", {"text": f"❌ 模板保存失败：{str(e)}"}, get_token(marketing=True))
        except: pass


def process_marketing_text(text: str, chat_id: str):
    """用文字内容替换电力电量段落，回传新 Word"""
    out_path = None
    try:
        token    = get_token(marketing=True)
        out_dir  = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        ts       = datetime.now().strftime('%Y%m%d%H%M%S')
        out_path = os.path.join(out_dir, f"marketing_{ts}.docx")

        # 按换行拆成多段
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if not paragraphs:
            send_message(chat_id, "text", {"text": "❌ 未检测到有效文字内容"}, token)
            return

        tmpl = get_template_path(chat_id)
        generate_marketing_docx(paragraphs, base_docx_path=tmpl, output_path=out_path)

        file_key = upload_file(out_path, token, f"营销专业基本情况_{ts}.docx")
        if file_key:
            send_file(chat_id, file_key, token)
        else:
            send_message(chat_id, "text", {"text": "❌ 文件上传失败"}, token)
    except Exception as e:
        import traceback; print(f"[marketing text error] {traceback.format_exc()}")
        try: send_message(chat_id, "text", {"text": f"❌ 生成失败：{str(e)}"}, get_token(marketing=True))
        except: pass
    finally:
        if out_path and os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass


@app.post("/webhook")
async def webhook_daily(request: Request, background_tasks: BackgroundTasks):
    return await _handle_webhook(request, background_tasks, mode="daily")

@app.post("/webhook/weekly")
async def webhook_weekly(request: Request, background_tasks: BackgroundTasks):
    return await _handle_webhook(request, background_tasks, mode="weekly")

@app.post("/webhook/province")
async def webhook_province(request: Request, background_tasks: BackgroundTasks):
    return await _handle_webhook(request, background_tasks, mode="province")

@app.post("/webhook/elec_week")
async def webhook_elec_week(request: Request, background_tasks: BackgroundTasks):
    return await _handle_webhook(request, background_tasks, mode="elec_week")

@app.post("/webhook/elec_load")
async def webhook_elec_load(request: Request, background_tasks: BackgroundTasks):
    """迎峰度夏最大用电负荷情况机器人"""
    return await _handle_webhook(request, background_tasks, mode="elec_load")

@app.post("/webhook/marketing")
async def webhook_marketing(request: Request, background_tasks: BackgroundTasks):
    """营销专业基本情况机器人"""
    return await _handle_webhook(request, background_tasks, mode="marketing")

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

    # 文件消息路由
    if msg_type == "file":
        try:
            content   = json.loads(msg.get("content", "{}"))
            file_key  = content.get("file_key", "")
            file_name = content.get("file_name", "") or ""
            print(f"[file] mode={mode} file_key={file_key} file_name={file_name}")
            if not file_key:
                pass
            elif mode == "marketing" and (file_name.lower().endswith(".docx") or not file_name):
                # 保存为该群模板
                token = get_token(marketing=True)
                send_message(chat_id, "text", {"text": "⚙️ 正在更新模板，请稍候..."}, token)
                background_tasks.add_task(
                    process_marketing_template, file_key, msg_id, chat_id)
            elif file_name.lower().endswith(".xlsx") or file_name.lower().endswith(".xls"):
                token = get_token(province=True)
                send_message(chat_id, "text", {"text": "⚙️ 正在解析数据并生成周榜图片，请稍候..."}, token)
                background_tasks.add_task(process_province_in_background, file_key, msg_id, chat_id, file_name)
            elif file_name.lower().endswith(".docx") or not file_name:
                token = get_token(weekly=True)
                send_message(chat_id, "text", {"text": "⚙️ 正在解析文档并生成图片，请稍候..."}, token)
                background_tasks.add_task(process_file_in_background, file_key, msg_id, chat_id)
        except Exception as ex:
            print(f"[file] 解析消息异常: {ex}")
        return Response("ok")

    # weekly / province 路由只处理文件，文字消息一律忽略
    # weekly / province 路由只处理文件，文字消息忽略
    if mode in ("weekly", "province"): return Response("ok")

    # 文字消息：需要 @ 机器人
    if not mentions: return Response("ok")

    if msg_type == "text":
        try:
            text = json.loads(msg.get("content", "{}")).get("text", "").strip()
            if "@" in text:
                text = text.split(">")[-1].strip() if ">" in text else text
            # 清除残留的 @_user_xxx 占位符
            import re as _re
            text = _re.sub(r'@[_a-zA-Z0-9]+', '', text).strip()
        except:
            return Response("ok")
        if not text: return Response("ok")
        if mode == "elec_week":
            tok = get_token(elec=True)
        elif mode == "elec_load":
            tok = get_token(elec_load=True)
        elif mode == "marketing":
            tok = get_token(marketing=True)
            send_message(chat_id, "text", {"text": "⚙️ 正在生成 Word 文档，请稍候..."}, tok)
            background_tasks.add_task(process_marketing_text, text, chat_id)
            return Response("ok", status_code=200)
        else:
            tok = get_token(weekly=False)
        send_message(chat_id, "text", {"text": "⚙️ 正在解析并生成图片，请稍候..."}, tok)
        background_tasks.add_task(process_in_background, text, chat_id, mode)

    return Response("ok", status_code=200)


@app.get("/")
async def health():
    return {"status": "ok", "service": "daily-forecast-webhook"}

