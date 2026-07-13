"""FakeLocation 后端:网页控制台的 HTTP 接口。

坐标一律为 WGS-84。GCJ-02(国内地图)转换由前端完成。
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import favorites
from device import DeviceError, clear_location, get_status, set_location

# 冻结打包后 web 目录不在源码相对位置,由 app.py 通过 FAKELOC_WEB 指定;
# 开发/直接跑 uvicorn 时回退到源码相对路径。
WEB_DIR = Path(os.environ.get('FAKELOC_WEB') or Path(__file__).resolve().parent.parent / 'web')

app = FastAPI(title='FakeLocation')

# 当前模拟的定位;None 表示未在模拟(或后端重启后状态未知)。
_active: dict | None = None


class Coordinate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Favorite(Coordinate):
    name: str = Field(min_length=1, max_length=40)


def _error(exc: DeviceError) -> JSONResponse:
    return JSONResponse(status_code=503, content={'message': exc.message, 'hint': exc.hint})


@app.get('/')
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / 'index.html')


@app.get('/api/status')
async def status() -> dict:
    return {'device': await get_status(), 'active': _active}


@app.post('/api/location')
async def apply_location(coord: Coordinate):
    global _active
    try:
        await set_location(coord.latitude, coord.longitude)
    except DeviceError as exc:
        return _error(exc)

    _active = {
        'latitude': coord.latitude,
        'longitude': coord.longitude,
        'since': datetime.now().strftime('%H:%M:%S'),
    }
    return {'active': _active}


@app.post('/api/location/clear')
async def restore_location():
    global _active
    try:
        await clear_location()
    except DeviceError as exc:
        return _error(exc)

    _active = None
    return {'active': None}


@app.get('/api/favorites')
async def list_favorites() -> list[dict]:
    return favorites.list_all()


@app.post('/api/favorites')
async def add_favorite(fav: Favorite) -> list[dict]:
    return favorites.add(fav.name, fav.latitude, fav.longitude)


@app.delete('/api/favorites/{fav_id}')
async def delete_favorite(fav_id: str) -> list[dict]:
    return favorites.remove(fav_id)
