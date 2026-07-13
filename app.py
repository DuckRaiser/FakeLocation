#!/usr/bin/env python3
"""FakeLocation 原生 App 入口。

由 FakeLocation.app 双击启动。做四件事:
  1. 若隧道未运行,用 macOS 原生密码弹窗以管理员权限拉起(iOS 17+ 建隧道需 root)。
  2. 后台线程启动 FastAPI 后端。
  3. 打开一个原生窗口(WKWebView)显示控制台。
  4. 关窗即退出:停掉后端。隧道保持运行,下次打开无需再输密码。
"""
from __future__ import annotations

import shlex
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent
BACKEND = REPO / 'backend'
TUNNELD_BIN = REPO / '.venv' / 'bin' / 'pymobiledevice3'
TUNNELD_LOG = '/tmp/fakelocation-tunneld.log'

HOST, PORT = '127.0.0.1', 8765
WEB_URL = f'http://{HOST}:{PORT}/'
TUNNELD_URL = 'http://127.0.0.1:49151'


def _http_ok(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def _applescript_str(s: str) -> str:
    """把字符串安全地转成 AppleScript 字面量。"""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def ensure_tunnel() -> None:
    """确保隧道服务在运行;未运行则弹出原生密码框以 root 启动。"""
    if _http_ok(TUNNELD_URL):
        return

    shell_cmd = (
        f'nohup {shlex.quote(str(TUNNELD_BIN))} remote tunneld '
        f'> {shlex.quote(TUNNELD_LOG)} 2>&1 &'
    )
    prompt = 'FakeLocation 需要管理员权限来建立与 iPhone 的连接(只需这一次)。'
    script = (
        f'do shell script {_applescript_str(shell_cmd)} '
        f'with administrator privileges with prompt {_applescript_str(prompt)}'
    )
    try:
        subprocess.run(['osascript', '-e', script], check=True,
                       capture_output=True, timeout=120)
    except subprocess.CalledProcessError:
        # 用户取消了密码框。仍打开窗口,让状态栏引导他重试。
        return
    except Exception:
        return

    for _ in range(30):                 # 最多等 15 秒
        if _http_ok(TUNNELD_URL):
            return
        time.sleep(0.5)


def start_backend() -> 'uvicorn.Server':
    import uvicorn

    sys.path.insert(0, str(BACKEND))
    import main  # noqa: E402  backend 应用

    config = uvicorn.Config(main.app, host=HOST, port=PORT, log_level='warning')
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    for _ in range(40):                 # 最多等 10 秒
        if _http_ok(WEB_URL):
            break
        time.sleep(0.25)
    return server


def _set_dock_icon() -> None:
    """运行时设置程序坞图标与名称(best-effort)。

    从 .app 里 exec 框架版 python 会让 mainBundle 指向 python 而非本 App,
    Info.plist 的图标不生效,所以在运行时直接给 NSApplication 挂上图标。
    """
    icns = REPO / 'FakeLocation.icns'
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSProcessInfo
        app = NSApplication.sharedApplication()
        if icns.exists():
            image = NSImage.alloc().initByReferencingFile_(str(icns))
            if image is not None:
                app.setApplicationIconImage_(image)
        NSProcessInfo.processInfo().setProcessName_('FakeLocation')
    except Exception:
        pass


def main() -> None:
    import webview

    server = None
    if not _http_ok(WEB_URL):            # 已在运行则复用,不再起第二个
        ensure_tunnel()
        server = start_backend()

    _set_dock_icon()
    webview.create_window(
        'FakeLocation', WEB_URL,
        width=1160, height=760, min_size=(920, 620),
    )
    webview.start()                      # 阻塞;所有窗口关闭后返回

    if server is not None:
        server.should_exit = True


if __name__ == '__main__':
    main()
