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
| 断开 USB | 模拟位置会失效,iPhone 自动回到真实定位。这是安全网,不是 bug。 |

## 架构

```
iPhone ──USB──► tunneld (sudo, 后台) ──RSD──► FastAPI 后端 ──HTTP──► 网页控制台
```

- `tunneld` 是唯一需要 root 的进程,单独跑,不与业务代码混在一起。
- 后端以普通权限运行,通过 tunneld 的本地 HTTP 接口拿到设备隧道地址。

## 目录结构

```
FakeLocation/
├── CLAUDE.md
├── start.sh              # 一键启动(唯一入口)
├── requirements.txt
├── backend/
│   ├── main.py           # FastAPI 应用 + 路由
│   └── device.py         # 设备发现与定位模拟的全部底层逻辑
└── web/
    └── index.html        # 单页控制台(地图 + 设置/恢复按钮)
```

## 约定

- **底层设备操作只写在 `device.py`**,路由层不直接调 pymobiledevice3。
- **不引入前端构建工具**。单个 HTML 文件,浏览器直接打开,零构建。
- 后端固定 `127.0.0.1:8765`,只监听本地,不暴露到局域网。
- 报错必须给出**下一步动作**,不能只报「失败」(例:「未检测到设备 → 请用数据线连接 iPhone 并在手机上点信任」)。
