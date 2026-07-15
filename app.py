#!/usr/bin/env python3
"""FakeLocation 原生 App 入口。

由 FakeLocation.app 双击启动。做四件事:
  1. 若隧道未运行,用 macOS 原生密码弹窗以管理员权限拉起(iOS 17+ 建隧道需 root)。
  2. 后台线程启动 FastAPI 后端。
  3. 打开一个原生窗口(WKWebView)显示控制台。
  4. 关窗即退出:停掉后端。隧道保持运行,下次打开无需再输密码。
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

# 冻结打包(PyInstaller)后,资源在 _MEIPASS 下;开发模式则在仓库根目录。
FROZEN = bool(getattr(sys, 'frozen', False))
if FROZEN:
    RES = Path(getattr(sys, '_MEIPASS', None) or Path(sys.executable).resolve().parent)
else:
    RES = Path(__file__).resolve().parent

BACKEND = RES / 'backend'
ICNS = RES / 'FakeLocation.icns'
TUNNELD_BIN = RES / '.venv' / 'bin' / 'pymobiledevice3'   # 仅开发模式使用
TUNNELD_LOG = '/tmp/fakelocation-tunneld.log'
APP_LOG = '/tmp/fakelocation-app.log'

HOST, PORT = '127.0.0.1', 8765
WEB_URL = f'http://{HOST}:{PORT}/'
TUNNELD_URL = 'http://127.0.0.1:49151'


def run_tunneld() -> None:
    """以 root 运行 pymobiledevice3 隧道守护进程(USB-only)。

    冻结包里没有独立的 pymobiledevice3 二进制,所以 App 用 --tunneld 自调用、
    由 osascript 以 root 拉起。这里直接调程序化入口 TunneldRunner.create,
    绕开 CLI(它会拖入 inquirer3 等交互式依赖)。
    """
    from pymobiledevice3.remote.common import TunnelProtocol
    from pymobiledevice3.tunneld.api import TUNNELD_DEFAULT_ADDRESS
    from pymobiledevice3.tunneld.server import TunneldRunner

    host, port = TUNNELD_DEFAULT_ADDRESS
    TunneldRunner.create(
        host, port,
        protocol=TunnelProtocol.DEFAULT,
        usb_monitor=True, usbmux_monitor=True,   # USB 通道
        wifi_monitor=False, mobdev2_monitor=False,
    )


def log(msg: str) -> None:
    """写一行诊断日志。Finder 启动时没有终端,靠这个文件排障。"""
    try:
        with open(APP_LOG, 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%H:%M:%S")} {msg}\n')
    except Exception:
        pass


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

    if FROZEN:                           # 自调用 --tunneld(见 run_tunneld)
        launcher = f'{shlex.quote(sys.executable)} --tunneld'
    else:
        launcher = f'{shlex.quote(str(TUNNELD_BIN))} remote tunneld'
    # 不能用 nohup:osascript 提权环境没有控制终端,macOS 的 nohup 会报
    # "can't detach from console" 直接失败。< /dev/null + & 已足够脱离。
    shell_cmd = f'{launcher} < /dev/null > {shlex.quote(TUNNELD_LOG)} 2>&1 &'
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

    os.environ['FAKELOC_WEB'] = str(RES / 'web')   # 让后端找到网页目录
    if BACKEND.is_dir():                            # 开发模式:把 backend 加进路径
        sys.path.insert(0, str(BACKEND))
    import main  # noqa: E402  backend 应用(冻结后由 PyInstaller 收录)

    config = uvicorn.Config(main.app, host=HOST, port=PORT, log_level='warning')
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    for _ in range(40):                 # 最多等 10 秒
        if _http_ok(WEB_URL):
            break
        time.sleep(0.25)
    return server


def _brand_app() -> None:
    """把进程设成前台 GUI App,并挂上程序坞图标(best-effort)。

    从 .app 里 exec 框架版 python,会让 NSBundle.mainBundle 指向 Python.app;
    若激活策略不是 Regular,Finder 启动时窗口会一闪即退。这里强制修正。
    """
    try:
        from AppKit import (NSApplication, NSApplicationActivationPolicyRegular,
                            NSImage)
        from Foundation import NSProcessInfo
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        if ICNS.exists():
            image = NSImage.alloc().initByReferencingFile_(str(ICNS))
            if image is not None:
                app.setApplicationIconImage_(image)
        NSProcessInfo.processInfo().setProcessName_('FakeLocation')
        log('brand: activation policy = Regular, icon set')
    except Exception as exc:
        log(f'brand: 失败 {exc!r}')


def main() -> None:
    log('=== 启动 ===')
    import webview
    log(f'webview imported (ver dir ok)')

    server = None
    if not _http_ok(WEB_URL):            # 已在运行则复用,不再起第二个
        log('WEB 未在运行 -> 建隧道')
        ensure_tunnel()
        log(f'隧道就绪={_http_ok(TUNNELD_URL)} -> 启动后端')
        server = start_backend()
        log(f'后端就绪={_http_ok(WEB_URL)}')
    else:
        log('WEB 已在运行 -> 复用')

    _brand_app()
    webview.create_window(
        'FakeLocation', WEB_URL,
        width=1160, height=760, min_size=(920, 620),
    )
    log('create_window 完成 -> webview.start()')
    t0 = time.time()
    webview.start()                      # 阻塞;所有窗口关闭后返回
    log(f'webview.start() 返回,耗时 {time.time() - t0:.1f}s -> 退出')

    if server is not None:
        server.should_exit = True


if __name__ == '__main__':
    if '--tunneld' in sys.argv:           # 以 root 被 osascript 拉起时走这里
        run_tunneld()
    else:
        try:
            main()
        except Exception:
            log('!!! 未捕获异常:\n' + traceback.format_exc())
            raise
