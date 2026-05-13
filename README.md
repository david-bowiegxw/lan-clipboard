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
| Delete an entry · 删除条目 | Click **Delete** (own entries, or any entry if you are admin) |
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
