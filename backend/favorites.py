"""收藏位置的本地存储。

存到 ~/.fakelocation/favorites.json —— 放在仓库外,因为家/公司这类坐标是隐私,
不能进入公开的 Git 仓库。坐标一律为 WGS-84。
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

STORE = Path.home() / '.fakelocation' / 'favorites.json'


def _load() -> list[dict]:
    try:
        with STORE.open(encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, ValueError):
        # ValueError 同时覆盖 JSONDecodeError 和 UnicodeDecodeError ——
        # 中文收藏名被外部改成非 UTF-8 编码时,也当作损坏、回退空表而非崩溃。
        return []


def _save(items: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    # 原子写入:先写临时文件再替换,避免中途崩溃损坏数据。
    tmp = STORE.with_suffix('.json.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORE)


def list_all() -> list[dict]:
    return _load()


def add(name: str, latitude: float, longitude: float) -> list[dict]:
    items = _load()
    items.append({
        'id': uuid.uuid4().hex[:8],
        'name': name.strip() or '未命名',
        'latitude': latitude,
        'longitude': longitude,
    })
    _save(items)
    return items


def remove(fav_id: str) -> list[dict]:
    items = [x for x in _load() if x.get('id') != fav_id]
    _save(items)
    return items
