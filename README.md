# FakeLocation

在 MacBook 上用网页改 iPhone 的定位,一键恢复。

> Change your iPhone's location from a web console on your Mac, and restore it with one click.
> USB only (Apple's debug tunnel doesn't work over Bluetooth). Requires iOS Developer Mode.

![status](https://img.shields.io/badge/iOS-17%2B%20%7C%2016---black) ![platform](https://img.shields.io/badge/host-macOS-black) ![license](https://img.shields.io/badge/license-MIT-black)

---

## 它能做什么

- 在地图上点一下,iPhone 的系统定位就变成那个点 —— 地图、天气、大部分 App 都会认。
- 用完点「恢复真实定位」,iPhone 立刻回到真实 GPS。
- **收藏常用位置**。给家、公司这类固定点起个名存起来,下次点一下就载入。收藏存在本机 `~/.fakelocation/favorites.json`,不进 Git。
- **自动处理火星坐标(GCJ-02)**。从高德、腾讯地图复制的坐标直接粘贴就能用,不会偏移 500 米。
- **两种用法**:终端 `./start.sh`(开浏览器),或打包成 `FakeLocation.app` 双击打开的原生窗口。

## 先说清楚限制

| 事项 | 结论 |
|---|---|
| **连接方式** | **只能 USB**。iOS 的调试通道不走蓝牙,这是 Apple 的限制,没有绕过的办法。 |
| **前提** | iPhone 需开启开发者模式,并与 Mac 配对信任。 |
| **"恢复"的含义** | 是**清除模拟**,让 iPhone 重新用真实 GPS —— 不是写回一个旧坐标。 |
| **模拟要保持生效** | **App(或终端服务)必须开着**。iOS 的模拟定位绑定在调试连接上,关窗口、退服务、拔线,任何一个都会让 iPhone 几秒内回到真实定位。 |
| **拔线之后** | 模拟定位自动失效,iPhone 回到真实定位。这是安全网。 |
| **管理员密码** | iOS 17+ 建立隧道需要 root,启动时输一次。之后的操作都不需要。 |

## 下载安装(Apple 芯片 Mac)

到 [Releases](https://github.com/DuckRaiser/FakeLocation/releases) 下载 `FakeLocation.dmg` → 打开 → 把 `FakeLocation.app` 拖进「应用程序」。

⚠️ **这个包没有 Apple 签名(需要 $99/年 开发者账号),所以首次打开会被 macOS 拦。** 在「终端」里跑一行解除隔离即可(只需一次):

```bash
xattr -dr com.apple.quarantine /Applications/FakeLocation.app
```

之后双击 `FakeLocation.app` 就能正常用。仅支持 Apple 芯片(arm64)Mac。

> 不想用下载的二进制?也可以 `git clone` 后自己 `./make_app.sh` 本地构建 —— 本地生成的 App 不会被 Gatekeeper 拦,无需上面这步。

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

常去的地方在选点后按「收藏当前点」起个名存下来,下次在「收藏」列表里点一下就载入。

## 打包成 macOS App(可选)

想要一个双击就开、关窗即退的原生窗口,而不是终端 + 浏览器:

```bash
./make_app.sh
```

会生成 `FakeLocation.app`。把它拖进「程序坞」或「应用程序」文件夹,以后:

- **双击打开** → 弹出原生窗口。首次会要一次管理员密码(建立 iPhone 隧道),之后每次打开都不用再输。
- **关闭窗口** → App 退出,后端停止。iPhone 若还在模拟定位,先点「恢复真实定位」或直接拔线。

> App 里的启动器指向本仓库的 `.venv` 和 `app.py`,所以别删仓库、别删 `.venv`。换了仓库位置就重新跑一次 `./make_app.sh`。
>
> 为了避免每次打开都输密码,连接 iPhone 的隧道进程(`tunneld`)在关窗后会继续留在后台 —— 它很轻、没插手机时什么都不做,也不会让 iPhone 保持假定位(假定位只由「恢复」按钮或拔线控制)。想彻底停掉它:`sudo pkill -f "pymobiledevice3 remote tunneld"`。

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
