#!/usr/bin/env python3
"""
LAN Clipboard Server
局域网剪贴板服务器 - 文本 & 文件共享，可选密码保护
"""

import asyncio
import io
import json
import logging
import signal
import socket
import sys
import urllib.parse
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from aiohttp import web
import qrcode
import qrcode.image.svg

HOST = "0.0.0.0"
WS_PORT = 8765
HTTP_PORT = 8766
MAX_HISTORY = 50
MAX_TEXT_SIZE = 1 * 1024 * 1024       # 1 MB
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
WS_MAX_MESSAGE = MAX_TEXT_SIZE + 64 * 1024  # 给 JSON 包装留余量

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Clean up any files left from a previous run (history is in-memory only)
for _f in UPLOAD_DIR.iterdir():
    if not _f.name.startswith("tmp_"):  # tmp_ files are mid-upload, leave for safety
        try:
            _f.unlink()
        except Exception:
            pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lan-clipboard")


def detect_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LOCAL_IP = detect_local_ip()
ADMIN_PEERS = {LOCAL_IP, "127.0.0.1", "::1", "::ffff:127.0.0.1", f"::ffff:{LOCAL_IP}"}


# ── State ─────────────────────────────────────────────────────────────────────

connected_clients: set = set()
history: list = []   # 文本 + 文件，按时间倒序（[0] 最新），单一来源


def is_admin(peer: str) -> bool:
    return peer in ADMIN_PEERS


def make_entry(entry_type, sender, password_hash="", uploader="", title="", **fields):
    now = datetime.now()
    return {
        "id": fields.pop("id", None) or uuid.uuid4().hex,
        "type": entry_type,
        "sender": sender,
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "password_hash": password_hash,
        "uploader": uploader.strip(),
        "title": title.strip(),
        **fields,
    }


def public_entry(entry: dict) -> dict:
    e = dict(entry)
    ph = e.pop("password_hash", "")
    e["locked"] = bool(ph or e.get("e2e"))
    return e


def find_entry(item_id):
    return next((e for e in history if e["id"] == item_id), None)


def delete_entry_file(entry: dict):
    if entry.get("type") == "file":
        try:
            (UPLOAD_DIR / entry["id"]).unlink(missing_ok=True)
        except Exception as exc:
            log.warning(f"Failed to delete file {entry['id']}: {exc}")


def push_history(entry: dict):
    """新条目入队，超过 MAX_HISTORY 时淘汰最旧条目并清理物理文件"""
    history.insert(0, entry)
    while len(history) > MAX_HISTORY:
        old = history.pop()
        delete_entry_file(old)


# ── WebSocket 广播 ────────────────────────────────────────────────────────────

async def broadcast(message: dict, exclude=None):
    if not connected_clients:
        return
    data = json.dumps(message, ensure_ascii=False)
    dead = set()
    for ws in list(connected_clients):
        if ws is exclude:
            continue
        try:
            await ws.send(data)
        except (ConnectionClosedOK, ConnectionClosedError):
            dead.add(ws)
        except Exception as exc:
            log.warning(f"Broadcast error: {exc}")
            dead.add(ws)
    connected_clients.difference_update(dead)


async def safe_send(ws, payload: dict):
    try:
        await ws.send(json.dumps(payload, ensure_ascii=False))
    except (ConnectionClosedOK, ConnectionClosedError):
        pass


async def send_error(ws, msg: str):
    await safe_send(ws, {"type": "error", "msg": msg})


# ── WebSocket Handler ─────────────────────────────────────────────────────────

async def ws_handler(websocket):
    peer = websocket.remote_address[0] if websocket.remote_address else "unknown"
    connected_clients.add(websocket)
    log.info(f"✅ Connected  {peer}  (online: {len(connected_clients)})")

    try:
        await safe_send(websocket, {
            "type": "init",
            "history": [public_entry(e) for e in history],
            "clients": len(connected_clients),
            "my_ip": peer,
            "server_ip": LOCAL_IP,
            "is_admin": is_admin(peer),
        })
        await broadcast({"type": "clients", "clients": len(connected_clients)},
                        exclude=websocket)

        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype = msg.get("type")

            if mtype == "push":
                base = dict(
                    uploader=str(msg.get("uploader", "")),
                    title=str(msg.get("title", "")),
                )
                if "cipher" in msg:
                    # E2E text: server never sees plaintext or password — it only relays cipher/salt/iv.
                    cipher = str(msg.get("cipher", ""))
                    salt   = str(msg.get("salt", ""))
                    iv     = str(msg.get("iv", ""))
                    if not (cipher and salt and iv):
                        await send_error(websocket, "Invalid E2E payload · 无效的加密数据")
                        continue
                    entry = make_entry("text", peer, cipher=cipher, salt=salt, iv=iv, e2e=True, **base)
                    push_history(entry)
                    log.info(f"📋 Text (E2E🔐)  {peer}  [encrypted]")
                else:
                    content = str(msg.get("content", "")).strip()
                    if not content:
                        continue
                    if len(content.encode()) > MAX_TEXT_SIZE:
                        await send_error(websocket, "Content too large · 最大 1 MB")
                        continue
                    entry = make_entry(
                        "text", peer,
                        password_hash=str(msg.get("password_hash", "")),
                        content=content, **base,
                    )
                    push_history(entry)
                    log.info(f"📋 Text  {peer}  {content[:60]!r}"
                             f"{'…' if len(content) > 60 else ''}"
                             f"{'  🔒' if entry['password_hash'] else ''}")
                # 给发送者单独回 ack（含 id），其它客户端收 new
                await safe_send(websocket,
                                {"type": "push_ack", "entry": public_entry(entry)})
                await broadcast({"type": "new", "entry": public_entry(entry)},
                                exclude=websocket)

            elif mtype == "verify":
                item_id = msg.get("id")
                provided = msg.get("password_hash", "")
                entry = find_entry(item_id)
                if entry is None:
                    await safe_send(websocket,
                                    {"type": "verify_result", "id": item_id,
                                     "ok": False, "msg": "Entry not found · 条目不存在"})
                    continue
                ok = (entry.get("password_hash", "") == provided)
                resp = {"type": "verify_result", "id": item_id, "ok": ok}
                if ok:
                    if entry["type"] == "text":
                        resp["content"] = entry["content"]
                    else:
                        resp["filename"] = entry["filename"]
                        resp["size"] = entry["size"]
                else:
                    resp["msg"] = "Wrong password · 密码错误"
                await safe_send(websocket, resp)

            elif mtype == "clear":
                if not is_admin(peer):
                    await send_error(websocket, "Admin only · 仅管理员可操作")
                    continue
                for e in history:
                    delete_entry_file(e)
                history.clear()
                log.info(f"🗑️  History cleared by {peer}")
                await broadcast({"type": "cleared"})

            elif mtype == "delete":
                item_id = msg.get("id")
                entry = find_entry(item_id)
                if entry is None:
                    await send_error(websocket, "Entry not found · 条目不存在")
                    continue
                if entry.get("e2e"):
                    # E2E entry: server cannot verify password ownership, so delete is restricted to creator/admin.
                    if not is_admin(peer) and entry.get("sender") != peer:
                        await send_error(websocket, "Permission denied · 无权删除")
                        continue
                elif entry.get("password_hash"):
                    provided_ph = msg.get("password_hash", "")
                    if (not is_admin(peer)
                            and entry.get("sender") != peer
                            and entry["password_hash"] != provided_ph):
                        await send_error(websocket, "Permission denied · 无权删除")
                        continue
                # Public entries: anyone may delete
                delete_entry_file(entry)
                history[:] = [e for e in history if e["id"] != item_id]
                log.info(f"🗑️  Deleted {item_id[:8]}… by {peer}"
                         f"{' (admin)' if is_admin(peer) else ''}")
                await broadcast({"type": "deleted", "id": item_id})

            elif mtype == "ping":
                await safe_send(websocket, {"type": "pong"})

    except (ConnectionClosedOK, ConnectionClosedError):
        pass
    except Exception as exc:
        log.error(f"Connection error {peer}: {exc}")
    finally:
        connected_clients.discard(websocket)
        log.info(f"❌ Disconnected  {peer}  (online: {len(connected_clients)})")
        await broadcast({"type": "clients", "clients": len(connected_clients)})


# ── HTTP Handlers ─────────────────────────────────────────────────────────────

async def index_handler(request):
    return web.FileResponse(
        Path(__file__).parent / "index.html",
        headers={"Cache-Control": "no-cache"},
    )


async def status_handler(request):
    peer = request.remote or ""
    return web.json_response({
        "status": "ok",
        "clients": len(connected_clients),
        "history_count": len(history),
        "local_ip": LOCAL_IP,
        "ws_port": WS_PORT,
        "http_port": HTTP_PORT,
        "url": f"http://{LOCAL_IP}:{HTTP_PORT}",
        "is_admin": is_admin(peer),
    })


async def qr_handler(request):
    url = f"http://{LOCAL_IP}:{HTTP_PORT}"
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return web.Response(
        text=buf.getvalue().decode("utf-8"),
        content_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


async def manifest_handler(request):
    return web.FileResponse(
        Path(__file__).parent / "manifest.json",
        headers={"Cache-Control": "no-cache", "Content-Type": "application/manifest+json"},
    )


async def upload_handler(request):
    """处理文件上传（多文件自动打包为 zip）"""
    peer = request.remote or "unknown"
    reader = await request.multipart()
    password_hash = uploader = title = ""
    is_e2e = False
    salt_e2e = iv_e2e = check_cipher_e2e = check_iv_e2e = ""
    tmp_files = []  # [(orig_name, tmp_path, size)]

    def cleanup_tmp():
        for _, p, _ in tmp_files:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

    try:
        async for part in reader:
            if part.name == "password_hash":
                password_hash = (await part.read()).decode()
            elif part.name == "uploader":
                uploader = (await part.read()).decode()
            elif part.name == "title":
                title = (await part.read()).decode()
            elif part.name == "e2e":
                is_e2e = (await part.read()).decode() == "1"
            elif part.name == "salt":
                salt_e2e = (await part.read()).decode()
            elif part.name == "iv":
                iv_e2e = (await part.read()).decode()
            elif part.name == "check_cipher":
                check_cipher_e2e = (await part.read()).decode()
            elif part.name == "check_iv":
                check_iv_e2e = (await part.read()).decode()
            elif part.name == "file":
                orig_name = part.filename or "unnamed"
                tmp_path = UPLOAD_DIR / f"tmp_{uuid.uuid4().hex}"
                written = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = await part.read_chunk(65536)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > MAX_FILE_SIZE:
                            f.close()
                            tmp_path.unlink(missing_ok=True)
                            cleanup_tmp()
                            return web.json_response(
                                {"ok": False, "msg": "File too large · 最大 5 GB"},
                                status=413)
                        f.write(chunk)
                if written > 0:
                    tmp_files.append((orig_name, tmp_path, written))
                else:
                    tmp_path.unlink(missing_ok=True)

        if not tmp_files:
            return web.json_response({"ok": False, "msg": "No file received · 未收到文件"}, status=400)

        file_id = uuid.uuid4().hex
        dest = UPLOAD_DIR / file_id

        if len(tmp_files) == 1:
            orig_name, tmp_path, size = tmp_files[0]
            tmp_path.rename(dest)
            filename = orig_name
        else:
            filename = (f"files_{len(tmp_files)}_"
                        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for orig_name, tmp_path, _ in tmp_files:
                    zf.write(tmp_path, orig_name)
                    tmp_path.unlink(missing_ok=True)
            size = dest.stat().st_size

        extra = {"id": file_id, "filename": filename, "size": size}
        if is_e2e:
            if not (salt_e2e and iv_e2e and check_cipher_e2e and check_iv_e2e):
                cleanup_tmp()
                return web.json_response(
                    {"ok": False, "msg": "Invalid E2E payload · 缺少加密参数"}, status=400)
            extra.update(e2e=True, salt=salt_e2e, iv=iv_e2e,
                         check_cipher=check_cipher_e2e, check_iv=check_iv_e2e)
            entry = make_entry("file", peer, "", uploader, title, **extra)
        else:
            entry = make_entry("file", peer, password_hash, uploader, title, **extra)
        push_history(entry)
        size_str = (f"{size/(1024**3):.2f}GB" if size >= 1024**3
                    else f"{size//1024}KB")
        log.info(f"📁 File{' (E2E🔐)' if is_e2e else ''}  {peer}  {filename!r}  {size_str}"
                 f"{'  🔒' if password_hash else ''}")
        await broadcast({"type": "new", "entry": public_entry(entry)})
        return web.json_response({"ok": True, "id": file_id,
                                  "entry": public_entry(entry)})

    except Exception:
        cleanup_tmp()
        raise


async def download_handler(request):
    file_id = request.match_info["file_id"]
    entry = find_entry(file_id)
    if entry is None or entry.get("type") != "file":
        return web.Response(status=404, text="File not found · 文件不存在或已被删除")

    # E2E files are already client-encrypted, so no server-side password check.
    if not entry.get("e2e") and entry.get("password_hash"):
        if request.query.get("ph", "") != entry["password_hash"]:
            return web.Response(status=403, text="Wrong password · 密码错误")

    fpath = UPLOAD_DIR / file_id
    if not fpath.exists():
        return web.Response(status=404, text="File not found · 文件已被删除")

    encoded = urllib.parse.quote(entry["filename"])
    return web.FileResponse(
        fpath,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
            "Content-Type": "application/octet-stream",
        },
    )


# ── App Builder ───────────────────────────────────────────────────────────────

def build_http_app() -> web.Application:
    app = web.Application(client_max_size=MAX_FILE_SIZE + 1024 * 1024)
    app.router.add_get("/",                    index_handler)
    app.router.add_get("/status",              status_handler)
    app.router.add_get("/qr",                  qr_handler)
    app.router.add_post("/upload",             upload_handler)
    app.router.add_get("/download/{file_id}",  download_handler)
    app.router.add_get("/manifest.json",       manifest_handler)
    app.router.add_static("/icon",             Path(__file__).parent / "icon")
    return app


# ── Main ──────────────────────────────────────────────────────────────────────

def print_qr_to_terminal(data: str):
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr.print_ascii(tty=sys.stdout.isatty())


async def main():
    url = f"http://{LOCAL_IP}:{HTTP_PORT}"
    bar = "═" * 54
    print(f"\n{bar}")
    print("  📋  LAN Clipboard  局域网剪贴板")
    print(bar)
    print(f"  Local IP   : {LOCAL_IP}")
    print(f"  Web UI     : {url}")
    print(f"  WebSocket  : ws://{LOCAL_IP}:{WS_PORT}")
    print(f"  Upload dir : {UPLOAD_DIR}")
    print("─" * 54)
    print("  Scan the QR code below, or open the URL on any device")
    print("  扫描下方二维码，或在同一局域网设备上打开上方地址")
    print()
    print_qr_to_terminal(url)
    print("  Press Ctrl+C to stop · 按 Ctrl+C 停止服务")
    print(f"{bar}\n")

    ws_server = await websockets.serve(
        ws_handler, HOST, WS_PORT, max_size=WS_MAX_MESSAGE,
    )
    runner = web.AppRunner(build_http_app())
    await runner.setup()
    site = web.TCPSite(runner, HOST, HTTP_PORT)
    await site.start()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()
    log.info("Shutting down…")
    for e in history:
        delete_entry_file(e)
    history.clear()
    ws_server.close()
    await ws_server.wait_closed()
    await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
