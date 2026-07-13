#!/usr/bin/env bash
#
# 把 FakeLocation 打包成一个可双击的 macOS App。
#
#   ./make_app.sh
#
# 生成 FakeLocation.app —— 双击即打开原生窗口,关窗即退出。
# App 内的启动器指向本仓库的 .venv 与 app.py,所以仓库别删。
set -euo pipefail
cd "$(dirname "$0")"

REPO="$(pwd)"
VENV="$REPO/.venv"
APP="$REPO/FakeLocation.app"
ICNS="$REPO/FakeLocation.icns"

if [ ! -x "$VENV/bin/python" ]; then
  echo "还没装依赖。请先运行一次 ./start.sh。"
  exit 1
fi

echo "[1/3] 生成图标…"
if "$VENV/bin/python" -c "import PIL" 2>/dev/null || "$VENV/bin/pip" install -q pillow; then
  "$VENV/bin/python" build/make_icon.py "$ICNS" || echo "  图标生成失败,使用系统默认图标。"
else
  echo "  Pillow 不可用,使用系统默认图标。"
fi

echo "[2/3] 组装 App…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
[ -f "$ICNS" ] && cp "$ICNS" "$APP/Contents/Resources/FakeLocation.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>FakeLocation</string>
  <key>CFBundleDisplayName</key><string>FakeLocation</string>
  <key>CFBundleIdentifier</key><string>com.ari.fakelocation</string>
  <key>CFBundleExecutable</key><string>FakeLocation</string>
  <key>CFBundleIconFile</key><string>FakeLocation</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# printf %q 把路径烤成 shell 安全字面量,兼容含空格/$/反引号/反斜杠的路径。
# arch -<本机架构> 强制原生架构启动:Finder 双击有时以 x86_64(Rosetta)拉起,
# 导致 arm64 原生扩展(pydantic_core 等)加载失败而闪退。这一步是闪退的根治。
ARCH="$(uname -m)"
{
  printf '#!/bin/bash\n'
  printf '# 由 make_app.sh 生成。启动 FakeLocation 原生窗口。\n'
  printf 'exec arch -%s %q %q\n' "$ARCH" "$VENV/bin/python" "$REPO/app.py"
} > "$APP/Contents/MacOS/FakeLocation"
chmod +x "$APP/Contents/MacOS/FakeLocation"

# 清掉可能的隔离属性,避免 Gatekeeper 拦截(本地生成本就无隔离,双保险)。
xattr -cr "$APP" 2>/dev/null || true

echo "[3/3] 完成 → $APP"
echo ""
echo "  下一步:把 FakeLocation.app 拖进「程序坞」或「应用程序」文件夹,双击即用。"
echo "  首次打开会弹一次管理员密码(建立 iPhone 隧道),之后不再需要。"
open -R "$APP"    # 在访达中高亮
