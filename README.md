# FakeLocation

在 MacBook 上用网页改 iPhone 的定位,一键恢复。

> Change your iPhone's location from a web console on your Mac, and restore it with one click.
> USB only (Apple's debug tunnel doesn't work over Bluetooth). Requires iOS Developer Mode.

![status](https://img.shields.io/badge/iOS-17%2B%20%7C%2016---black) ![platform](https://img.shields.io/badge/host-macOS-black) ![license](https://img.shields.io/badge/license-MIT-black)

---

## 它能做什么

- 在地图上点一下,iPhone 的系统定位就变成那个点 —— 地图、天气、大部分 App 都会认。
- 用完点「恢复真实定位」,iPhone 立刻回到真实 GPS。
- **自动处理火星坐标(GCJ-02)**。从高德、腾讯地图复制的坐标直接粘贴就能用,不会偏移 500 米。

## 先说清楚限制

| 事项 | 结论 |
|---|---|
| **连接方式** | **只能 USB**。iOS 的调试通道不走蓝牙,这是 Apple 的限制,没有绕过的办法。 |
| **前提** | iPhone 需开启开发者模式,并与 Mac 配对信任。 |
| **"恢复"的含义** | 是**清除模拟**,让 iPhone 重新用真实 GPS —— 不是写回一个旧坐标。 |
| **拔线之后** | 模拟定位自动失效,iPhone 回到真实定位。这是安全网。 |
| **管理员密码** | iOS 17+ 建立隧道需要 root,启动时输一次。之后的操作都不需要。 |

## 使用

**1. 开启 iPhone 开发者模式**(一次性)

设置 → 隐私与安全性 → 开发者模式 → 打开 → 重启 iPhone。

> 看不到这个选项?先用数据线连一次 Mac 并点「信任」,选项就会出现。

**2. 启动**

```bash
git clone https://github.com/DuckRaiser/FakeLocation.git
cd FakeLocation
./start.sh
```

首次运行会自动装依赖,然后要一次管理员密码(用于建立 iPhone 隧道),浏览器会自动打开控制台。

**3. 用**

在地图上点一个位置 → 「设为 iPhone 定位」→ 打开 iPhone 地图 App 验证 → 用完点顶部橙色条的「恢复真实定位」。

## 坐标系(这是个真坑)

iPhone 只认 **WGS-84**(国际标准 GPS 坐标)。但中国大陆的地图用 **GCJ-02**(火星坐标),两者在境内相差 **300–500 米**。

从高德、腾讯地图复制的坐标,如果不转换直接发给 iPhone,定位会偏到隔壁街区。本工具在粘贴坐标时让你选来源:

- **高德/腾讯** → 按 GCJ-02 处理,自动转成 WGS-84
- **GPS/谷歌** → 按 WGS-84 处理,直接用

在地图上直接点选则无需关心,已自动对齐。境外坐标两个坐标系一致,算法自动跳过。

## 架构

```
iPhone ──USB──► tunneld (root, 独立进程) ──RSD──► FastAPI ──HTTP──► 网页控制台
```

只有 `tunneld` 需要 root,业务代码以普通权限运行。

```
backend/device.py   # 所有 pymobiledevice3 调用都在这里
backend/main.py     # HTTP 接口
web/index.html      # 单页控制台,零构建
start.sh            # 唯一入口
```

底层能力来自 [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)。

## 常见问题

**「未检测到 iPhone」** — 检查:数据线连着吗(充电线可能不支持数据传输)?手机解锁了吗?点过「信任」吗?开发者模式开了吗?

**定位没变** — 部分 App 有自己的反作弊(如 Pokémon GO、部分银行 App),不吃系统级模拟定位。地图、天气这类正常 App 都会生效。

**改完想还原,但网页关了** — 拔掉数据线即可,iPhone 会自动回到真实定位。

## 免责声明

这是一个开发测试工具,基于 Apple 官方的设备调试接口。**仅用于你自己拥有的设备**。请勿用于欺诈、伪造行踪、或违反任何服务条款的场景。使用后果自负。

## License

MIT
