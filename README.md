# LAN Clipboard · 局域网剪贴板

> Share text and files instantly across all devices on your local network — no internet, no accounts, no apps required.
>
> 在局域网内跨设备即时共享文本与文件，无需互联网、无需账号、无需安装 App。

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

![Overview](docs/screenshots/overview.png)

---

## Features · 功能特性

- **Real-time sync** — WebSocket broadcasts new content to all connected devices instantly  
  实时同步，新内容通过 WebSocket 即时推送到所有在线设备
- **Text & file sharing** — paste text or upload files up to 5 GB  
  文本与文件共享，单文件最大 5 GB
- **Multi-file upload** — multiple files are auto-packaged into a zip  
  多文件自动打包为 zip 上传
- **Password protection** — lock individual items; auto-relocks after 60 s  
  单条目密码保护，解锁后 60 秒自动重新锁定
- **QR code access** — scan to open on any phone on the same Wi-Fi  
  内置二维码，手机扫码一键访问
- **Fine-grained delete permissions** — public entries can be deleted by anyone; password-protected entries require the creator, admin, or a user who has unlocked the entry  
  细粒度删除权限：公开条目任何人可删；加密条目仅创建者、管理员或已输入正确密码的用户可删
- **Admin controls** — the host machine can delete any entry or clear all history  
  主机拥有管理员权限，可删除任意条目或清空全部历史
- **Bilingual UI** — switch between Chinese and English with one click  
  中英文界面一键切换
- **Zero client dependencies** — works in any modern browser, no app needed  
  客户端零依赖，任何现代浏览器均可使用

| Text sharing · 文本共享 | File upload · 文件上传 |
|:-:|:-:|
| ![Text tab](docs/screenshots/text-tab.png) | ![File tab](docs/screenshots/file-tab.png) |

| Password protection · 密码保护 | QR code access · 二维码访问 |
|:-:|:-:|
| ![Password](docs/screenshots/password.png) | ![QR code](docs/screenshots/qr-code.png) |

---

## Quick Start · 快速启动

### Requirements · 环境要求

- Python 3.9+
- All devices on the **same local network** (Wi-Fi or wired)  
  所有设备接入**同一局域网**（Wi-Fi 或有线）

### One-click start (macOS / Linux) · 一键启动

```bash
git clone https://github.com/YOUR_USERNAME/lan-clipboard.git
cd lan-clipboard
chmod +x start.sh
./start.sh
```

The script creates a virtual environment, installs dependencies, and starts the server.  
脚本自动创建虚拟环境、安装依赖并启动服务器。

### Manual start · 手动启动

```bash
pip install -r requirements.txt
python3 server.py
```

Open the printed URL (e.g. `http://192.168.1.x:8766`) in a browser on **any device** in your network.  
用局域网内**任意设备**的浏览器打开终端输出的地址（如 `http://192.168.1.x:8766`）即可。

---

## Usage · 使用方法

| Action · 操作 | How · 方式 |
|---|---|
| Send text · 发送文本 | Text tab → type/paste → **Send** or **⌘/Ctrl + Enter** |
| Share a file · 分享文件 | File tab → drag & drop or click → **Upload & Share** |
| Copy text · 复制文本 | Click **Copy** on any text entry |
| Download a file · 下载文件 | Click **Download** on any file entry |
| Password protect · 密码保护 | Enable the lock toggle before sending |
| Switch language · 切换语言 | Click **EN / 中文** in the top-right corner |
| Delete an entry · 删除条目 | Click **Delete** → confirm inline (public: any user; locked: creator / admin / unlocked user) |
| Clear all · 清空全部 | Click **Clear All** (admin / host only) |
| Mobile access · 手机访问 | Click **QR Code** → scan with phone |

---

## How It Works · 工作原理

```
Browser  ←── WebSocket :8765 ──→  Python Server  ←── HTTP :8766 ──→  Browser
                                        │
                                   uploads/  (files stored here)
```

| Port | Protocol | Purpose |
|------|----------|---------|
| 8766 | HTTP | Web UI · File upload/download · QR code |
| 8765 | WebSocket | Real-time text sync · Password verify · Event broadcast |

---

## Configuration · 配置

Edit the constants at the top of `server.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_PORT` | `8766` | Web UI port |
| `WS_PORT` | `8765` | WebSocket port |
| `MAX_FILE_SIZE` | `5 GB` | Maximum file size |
| `MAX_TEXT_SIZE` | `1 MB` | Maximum text size |
| `MAX_HISTORY` | `50` | History limit (oldest auto-evicted) |

---

## Security Notes · 安全说明

- Designed for **trusted local networks only**. Do not expose ports to the internet.  
  仅适用于**可信局域网**，请勿将端口暴露至互联网。
- Passwords are SHA-256 hashed in the browser before transmission; the server stores only the hash.  
  密码在浏览器端 SHA-256 哈希后传输，服务器仅存储哈希值。
- The machine running the server is the **admin** and can manage all entries.  
  运行服务器的机器为**管理员**，可管理所有条目。

---

## License · 许可证

MIT

---

## Changelog · 更新日志

### v2.1.0 — 2026-05-14

**Delete permission overhaul · 删除权限重构**
- Public entries can now be deleted by **any** connected user (previously restricted to creator / admin)  
  公开条目现在**任何在线用户**均可删除（之前仅限创建者/管理员）
- Password-protected entries can be deleted by the creator, admin, or any user who has **successfully unlocked** the entry in the current session  
  加密条目可由创建者、管理员，或当前会话中已成功解锁该条目的用户删除
- Delete request now carries the password hash when applicable; server validates it server-side  
  删除请求在必要时携带密码哈希，服务端同步校验

**Inline delete confirmation · 内联删除确认**
- Replaced the browser's native `confirm()` dialog with an in-card confirmation row (「确认删除？ [确认] [取消]」)  
  删除确认从浏览器原生弹窗改为条目内嵌确认行，风格统一，体验更流畅
- Cancelling restores the original action buttons with no side effects  
  点击取消后原按钮完整还原

**QR code close animation · 二维码关闭动画**
- Added a `modalOut` (scale + fade) close animation matching the existing open animation  
  补充了与打开动画对称的关闭动画（缩放 + 淡出），保持 UI 一致性

---

### v2.0.0 — 2026-05-13 · Initial release · 首次发布

- Real-time text & file sharing over WebSocket + HTTP  
  WebSocket + HTTP 实时文本与文件共享
- Multi-file upload with auto-zip  
  多文件自动打包为 zip
- Per-entry password protection with SHA-256 hashing and 60 s auto-relock  
  条目级密码保护，SHA-256 哈希，60 秒自动重锁
- QR code access for mobile devices  
  内置二维码供手机扫码访问
- Dark / light theme, Chinese / English UI  
  深色/浅色主题，中英文双语界面
- PWA manifest + icons (iOS / Android home screen)  
  PWA manifest 与多尺寸图标，支持 iOS/Android 添加到主屏幕
- Reliable file drop zone (transparent input overlay, `pointer-events: none` on children)  
  文件拖拽区域点击可靠性修复
- Clickable URLs and email addresses in shared text  
  分享文本中的链接和邮箱地址自动转为可点击超链接
- "Add more files" button in the upload preview  
  上传预览区新增「继续添加」按钮
- Thin custom scrollbar for multi-file list  
  多文件列表自定义细滚动条，避免遮挡文件大小文字
- Upload directory cleaned on server start and shutdown (no orphaned files)  
  服务启动和关闭时自动清理 uploads 目录，不留残余文件
