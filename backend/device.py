"""iOS 设备定位模拟的底层封装。

所有 pymobiledevice3 调用只出现在本文件,路由层不直接接触设备 API。
坐标一律为 WGS-84,坐标系转换由前端负责。

关键机制:iOS 的模拟定位只在 DVT 调试连接存活期间有效,连接一断,
系统几秒内自动恢复真实 GPS(官方 CLI 设完坐标也是挂起保持连接的)。
因此本模块维持一个**持久会话**:set 时建立并一直持有,clear/进程退出
时才断开。由此产生的产品语义:App/后端开着=模拟持续;关掉=回真实定位。
"""
from __future__ import annotations

from pymobiledevice3.exceptions import PyMobileDevice3Exception
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.tunneld.api import TunneldConnectionError, get_tunneld_devices


class DeviceError(Exception):
    """设备错误。必须同时给出下一步动作,不能只报失败。"""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


# 持久模拟会话;None = 当前没有在模拟。
# 只会被 uvicorn 的单一事件循环访问,无需加锁。
_session: dict | None = None


async def _acquire() -> RemoteServiceDiscoveryService:
    """取得第一台已建立隧道的设备。"""
    try:
        devices = await get_tunneld_devices()
    except TunneldConnectionError:
        raise DeviceError(
            '隧道服务未运行',
            '请完全退出后重新打开 FakeLocation(会弹出管理员密码框);'
            '若用终端,请以 ./start.sh 启动 —— 它会自动拉起隧道服务。',
        )

    if not devices:
        raise DeviceError(
            '未检测到 iPhone',
            '请用数据线把 iPhone 连到 Mac,在手机上点「信任」,并确认已开启开发者模式'
            '(设置 > 隐私与安全性 > 开发者模式)。',
        )
    return devices[0]


async def _release(rsd: RemoteServiceDiscoveryService) -> None:
    try:
        await rsd.close()
    except Exception:
        pass


async def _open_session() -> dict:
    """建立 rsd → DVT → LocationSimulation 的长连接会话。"""
    rsd = await _acquire()
    provider = None
    location = None
    try:
        provider = DvtProvider(rsd)
        await provider.__aenter__()
        location = LocationSimulation(provider)
        await location.__aenter__()
        return {'rsd': rsd, 'provider': provider, 'location': location}
    except Exception as exc:
        await _close_session({'rsd': rsd, 'provider': provider, 'location': location})
        raise DeviceError(
            f'无法连接设备的调试服务:{exc}',
            '请拔掉数据线重新插上,解锁 iPhone 后再试一次。',
        )


async def _close_session(s: dict | None) -> None:
    """尽力关闭会话的每一层,不让任何一层的失败挡住其他层。"""
    if not s:
        return
    for key in ('location', 'provider'):
        obj = s.get(key)
        if obj is not None:
            try:
                await obj.__aexit__(None, None, None)
            except Exception:
                pass
    if s.get('rsd') is not None:
        await _release(s['rsd'])


async def get_status() -> dict:
    """设备是否就绪。未连接不算异常,如实返回 connected=False。"""
    try:
        rsd = await _acquire()
    except DeviceError as exc:
        return {'connected': False, 'message': exc.message, 'hint': exc.hint}

    try:
        info = rsd.peer_info.get('Properties', {}) if hasattr(rsd, 'peer_info') else {}
        return {
            'connected': True,
            'name': info.get('Name') or '已连接的 iPhone',
            'model': info.get('HardwareModel') or '',
            'ios_version': getattr(rsd, 'product_version', '') or '',
            'udid': getattr(rsd, 'udid', '') or '',
        }
    finally:
        await _release(rsd)


async def set_location(latitude: float, longitude: float) -> None:
    """把设备定位设为指定 WGS-84 坐标,并保持会话让模拟持续生效。"""
    global _session

    fresh = _session is None
    if fresh:
        _session = await _open_session()

    try:
        await _session['location'].set(latitude, longitude)
        return
    except (PyMobileDevice3Exception, OSError, ConnectionError) as exc:
        # 会话失效(多半是拔过线)。新会话直接报错;旧会话重建一次再试。
        await _close_session(_session)
        _session = None
        if fresh:
            raise DeviceError(
                f'设备通信失败:{exc}',
                '请拔掉数据线重新插上,解锁 iPhone 后再试一次。',
            )

    _session = await _open_session()
    try:
        await _session['location'].set(latitude, longitude)
    except Exception as exc:
        await _close_session(_session)
        _session = None
        raise DeviceError(
            f'设备通信失败:{exc}',
            '请拔掉数据线重新插上,解锁 iPhone 后再试一次。',
        )


async def clear_location() -> None:
    """清除模拟定位并断开会话,设备恢复使用真实 GPS。"""
    global _session

    if _session is None:
        # 没有活跃会话(如后端重启过):连接早已断开,iOS 已自动恢复真实
        # 定位。仍开一次临时会话下发 clear,兜底万一系统残留了模拟状态。
        s = await _open_session()
        try:
            await s['location'].clear()
        finally:
            await _close_session(s)
        return

    try:
        await _session['location'].clear()
    except Exception:
        pass          # 会话已死 = 连接已断 = 模拟已被系统清除,目的已达成
    finally:
        await _close_session(_session)
        _session = None
