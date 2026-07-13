#!/usr/bin/env bash
#
# 构建自包含的 FakeLocation.app 并打成 .dmg(用于 GitHub Release 分发)。
#
#   ./build_dmg.sh [版本号]
#
# 产物 FakeLocation.dmg 内含 Python 解释器 + 全部依赖,可在任意 Apple 芯片 Mac
# 上「拖进应用程序」即用。注意:未签名,首次打开需右键→打开绕过 Gatekeeper。
set -euo pipefail
cd "$(dirname "$0")"

REPO="$(pwd)"
VENV="$REPO/.venv"
DMG="$REPO/FakeLocation.dmg"
VER="${1:-1.0.0}"

[ -x "$VENV/bin/pyinstaller" ] || { echo "缺 pyinstaller:.venv/bin/pip install pyinstaller"; exit 1; }

echo "[1/4] 生成图标…"
"$VENV/bin/python" -c "import PIL" 2>/dev/null || "$VENV/bin/pip" install -q pillow
"$VENV/bin/python" assets/make_icon.py "$REPO/FakeLocation.icns"

echo "[2/4] PyInstaller 冻结(几分钟)…"
rm -rf build dist "$DMG"
"$VENV/bin/pyinstaller" --noconfirm --clean --windowed \
  --name FakeLocation \
  --icon FakeLocation.icns \
  --osx-bundle-identifier com.ari.fakelocation \
  --paths backend \
  --hidden-import main --hidden-import device --hidden-import favorites \
  --collect-all pymobiledevice3 \
  --collect-all webview \
  --collect-submodules uvicorn \
  --add-data "web/index.html:web" \
  --add-data "FakeLocation.icns:." \
  app.py

# 本地生成本无隔离属性,清一遍双保险
xattr -cr dist/FakeLocation.app 2>/dev/null || true

echo "[3/4] 打 .dmg…"
STAGE="$(mktemp -d)"
cp -R dist/FakeLocation.app "$STAGE/FakeLocation.app"
ln -s /Applications "$STAGE/Applications"      # 拖拽安装的目标
hdiutil create -volname "FakeLocation $VER" -srcfolder "$STAGE" \
  -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

echo "[4/4] 完成:"
du -sh "$DMG"
echo "  $DMG"
