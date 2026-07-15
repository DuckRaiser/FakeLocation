"""iOS 设备定位模拟的底层封装。

所有 pymobiledevice3 调用只出现在本文件,路由层不直接接触设备 API。
坐标一律为 WGS-84,坐标系转换由前端负责。
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


async def _simulate(action) -> None:
    """在一次隧道会话内执行一个 LocationSimulation 动作。"""
    rsd = await _acquire()
    try:
        async with DvtProvider(rsd) as provider:
            async with LocationSimulation(provider) as location:
                await action(location)
    except DeviceError:
        raise
    except PyMobileDevice3Exception as exc:
        raise DeviceError(
            f'设备通信失败:{exc}',
            '请拔掉数据线重新插上,然后解锁 iPhone 再试一次。',
        )
    finally:
        await _release(rsd)


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
    """把设备定位设为指定 WGS-84 坐标。设置后即使断开本连接也会保持。"""
    await _simulate(lambda loc: loc.set(latitude, longitude))


async def clear_location() -> None:
    """清除模拟定位,设备恢复使用真实 GPS。"""
    await _simulate(lambda loc: loc.clear())
