#!/usr/bin/env bash
#
# FakeLocation 一键启动。
#
#   ./start.sh
#
# 做三件事:装依赖(仅首次)、拉起 iPhone 隧道(需要一次管理员密码)、开网页。
set -uo pipefail
cd "$(dirname "$0")"

VENV=.venv
TUNNELD_URL=http://127.0.0.1:49151
WEB_URL=http://127.0.0.1:8765

tunneld_up() { curl -sf --max-time 1 "$TUNNELD_URL" >/dev/null 2>&1; }

cleanup() {
  echo ""
  echo "正在关闭服务…"
  [ "${TUNNELD_STARTED:-0}" = "1" ] && sudo -n pkill -f 'pymobiledevice3 remote tunneld' 2>/dev/null
  echo "已关闭。iPhone 若仍是模拟定位,拔掉数据线即可恢复。"
}
trap cleanup EXIT INT TERM

echo "──────────────────────────────────────"
echo "  FakeLocation · iPhone 定位控制台"
echo "──────────────────────────────────────"
echo ""

# 1. 依赖(仅首次)
if [ ! -x "$VENV/bin/uvicorn" ]; then
  echo "[1/3] 首次运行,正在安装依赖(约 1 分钟)…"
  python3 -m venv "$VENV" || exit 1
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r requirements.txt || { echo "依赖安装失败,请检查网络。"; exit 1; }
else
  echo "[1/3] 依赖已就绪。"
fi

# 2. 隧道(iOS 17+ 需要 root 建立本地网络接口)
if tunneld_up; then
  echo "[2/3] 隧道服务已在运行,直接复用。"
else
  echo "[2/3] 建立 iPhone 隧道,需要管理员密码(全程只需这一次):"
  sudo -v || { echo "未获得权限,无法继续。"; exit 1; }
  sudo "$VENV/bin/pymobiledevice3" remote tunneld >/tmp/fakelocation-tunneld.log 2>&1 &
  TUNNELD_STARTED=1

  printf "      正在启动"
  for _ in $(seq 1 20); do
    tunneld_up && break
    printf "."
    sleep 0.5
  done
  echo ""

  if ! tunneld_up; then
    echo ""
    echo "隧道启动失败。日志:/tmp/fakelocation-tunneld.log"
    echo "请确认:iPhone 已用数据线连接、已解锁、已在手机上点「信任」。"
    exit 1
  fi
fi

# 3. 后端 + 网页(普通权限,不需要 root)
echo "[3/3] 启动控制台 → $WEB_URL"
echo ""
echo "  提示:iPhone 需开启开发者模式(设置 > 隐私与安全性 > 开发者模式)"
echo "  按 Ctrl+C 退出。"
echo ""

( sleep 1.5 && open "$WEB_URL" ) &
exec "$VENV/bin/uvicorn" main:app --app-dir backend --host 127.0.0.1 --port 8765 --log-level warning
