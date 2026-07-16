# FakeLocation

通过 USB 连接的 MacBook,在网页上修改 iPhone 的系统定位,并一键恢复真实定位。

## 业务目标

- **解决什么问题**:需要临时把 iPhone 的定位设到指定坐标,用完能立刻还原,全程不碰命令行。
- **嵌入哪个流程**:Mac 上启动服务 → 浏览器打开控制台 → 设定位 → 用完点恢复。

## 技术现实(不要试图绕过)

| 事项 | 结论 |
|---|---|
| 连接方式 | **仅 USB**。蓝牙无法访问 iOS 调试通道,不存在实现路径。 |
| iOS 版本 | iOS 17+ 走 RemoteXPC 隧道(需 sudo);iOS 16- 走 DeveloperDiskImage。 |
| 前提条件 | iPhone 必须开启「开发者模式」并与 Mac 配对信任。 |
| "恢复定位" | = 清除模拟(`clear`),让 iPhone 重新用真实 GPS。**不是**写回旧坐标。 |
| 模拟的存活 | **绑定在 DVT 连接上**:连接断开,iOS 几秒内自动回真实定位。因此 `device.py` 维持持久会话,set 后不许断开;关 App/后端/拔线 = 恢复真实。官方 CLI set 完也是挂起保持连接的。 |
| 断开 USB | 模拟位置会失效,iPhone 自动回到真实定位。这是安全网,不是 bug。 |

## 架构

```
iPhone ──USB──► tunneld (root, 持久) ──RSD──► FastAPI 后端 ──HTTP──► 网页 / 原生窗口
```

- `tunneld` 是唯一需要 root 的进程,单独跑,不与业务代码混在一起。
- 后端以普通权限运行,通过 tunneld 的本地 HTTP 接口拿到设备隧道地址。
- 两种前端外壳,共用同一套后端与网页:
  - `start.sh` → 浏览器(终端启动,sudo 起隧道)
  - `FakeLocation.app` → 原生窗口(双击启动,osascript 原生密码框起隧道)

## 目录结构

```
FakeLocation/
├── CLAUDE.md
├── start.sh              # 终端一键启动(浏览器)
├── make_app.sh           # 本机快速打包 FakeLocation.app(瘦包装,指向 .venv)
├── build_dmg.sh          # 自包含 .dmg 分发(PyInstaller 冻结,用于 Release)
├── app.py                # 原生 App 入口:起隧道 + 后端线程 + pywebview 窗口
├── requirements.txt
├── assets/
│   └── make_icon.py      # 构建期图标生成(Pillow),运行时不依赖
├── backend/
│   ├── main.py           # FastAPI 应用 + 路由
│   ├── device.py         # 设备发现与定位模拟的全部底层逻辑
│   └── favorites.py      # 收藏位置的 JSON 存储(仓库外)
└── web/
    └── index.html        # 单页控制台(地图 + 收藏 + 设置/恢复)
```

- **两种打包**:`make_app.sh` = 本机开发用瘦包装(依赖仓库 .venv,快);`build_dmg.sh` = PyInstaller 冻结出自包含 .dmg(含解释器+依赖,可分发,~63MB)。
- **`assets/` 不能叫 `build/`**:`build/` 是 PyInstaller 的工作目录,会被 `rm -rf` 清空。
- **`app.py` 兼容冻结**:`FROZEN` 分支处理资源路径,冻结包无独立 pymobiledevice3 二进制,用 `--tunneld` 自调用直起 `TunneldRunner`。

## 约定

- **底层设备操作只写在 `device.py`**,路由层不直接调 pymobiledevice3。
- **收藏存到 `~/.fakelocation/favorites.json`(仓库外)**。家/公司坐标是隐私,绝不进 Git。原子写入。
- **不引入前端构建工具**。单个 HTML 文件,浏览器直接打开,零构建。
- **App 是本地构建产物**,不签名不公证(个人自用)。`FakeLocation.app` / `*.icns` 进 .gitignore,由 `make_app.sh` 从源码重建。
- 后端固定 `127.0.0.1:8765`,只监听本地,不暴露到局域网。
- 坐标一律 **WGS-84**;GCJ-02(国内地图)转换只在前端做,后端与存储都是 WGS-84。
- 报错必须给出**下一步动作**,不能只报「失败」(例:「未检测到设备 → 请用数据线连接 iPhone 并在手机上点信任」)。
