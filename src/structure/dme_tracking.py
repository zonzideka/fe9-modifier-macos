#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrap dolphin_memory_engine.write_bytes so every RAM write the modifier
performs is logged. The cumulative net diff (final value vs. value just before
the first write at each address) can later be exported as Dolphin Action
Replay codes — useful for persisting changes to slots fe9-editor cannot
write to ROM (i.e. pointer fields not registered in FE8Data.bin's reloc table).

The wrapper is the single point through which Value.set() pushes RAM writes,
so import this module's `write_bytes` rather than dolphin_memory_engine's.

State is organised as named *profiles*; each profile owns its own writes and
baseline. The full state is persisted to a JSON file and reloaded on next
launch, so a session can span multiple modifier runs. Switching profiles
swaps which set of writes new edits land in (and which set the export
dialog reads from)."""

import json
import os
import platform
import threading

from dolphin_memory_engine import read_bytes, write_bytes as _raw_write_bytes


# ---------------------------------------------------------------------------
# Storage location
# ---------------------------------------------------------------------------

def _config_dir() -> str:
    """Per-platform config directory for the modifier's session state."""
    sys = platform.system()
    if sys == 'Darwin':
        return os.path.expanduser('~/Library/Application Support/PoR-Modifier')
    if sys == 'Linux':
        return os.path.expanduser('~/.config/por-modifier')
    if sys == 'Windows':
        return os.path.join(os.environ.get('APPDATA', ''), 'PoR-Modifier')
    return os.path.expanduser('~/.por-modifier')


def store_path() -> str:
    return os.path.join(_config_dir(), 'profiles.json')


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

DEFAULT_PROFILE = 'default'


def _empty_profile() -> dict:
    return {'writes': {}, 'baseline': {}}


_lock = threading.RLock()
_profiles: dict = {DEFAULT_PROFILE: _empty_profile()}
_current: str = DEFAULT_PROFILE
_loaded = False


def _ensure_loaded() -> None:
    """Load state from disk on first access. Idempotent."""
    global _loaded, _profiles, _current
    with _lock:
        if _loaded:
            return
        _loaded = True
        path = store_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return  # corrupt / unreadable — start fresh, don't crash startup
        try:
            loaded_profiles = {}
            for name, p in (data.get('profiles') or {}).items():
                writes = {int(k, 16): bytes.fromhex(v) for k, v in (p.get('writes') or {}).items()}
                baseline = {int(k, 16): bytes.fromhex(v) for k, v in (p.get('baseline') or {}).items()}
                loaded_profiles[name] = {'writes': writes, 'baseline': baseline}
            if loaded_profiles:
                _profiles = loaded_profiles
            cur = data.get('current')
            if cur and cur in _profiles:
                _current = cur
            elif _current not in _profiles:
                _current = next(iter(_profiles))
        except Exception:
            # Mixed/garbage data — discard, fall back to fresh defaults.
            _profiles = {DEFAULT_PROFILE: _empty_profile()}
            _current = DEFAULT_PROFILE


def _save() -> None:
    """Best-effort persist current state to disk. Never raises."""
    try:
        path = store_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with _lock:
            data = {
                'current': _current,
                'profiles': {
                    name: {
                        'writes': {f'{a:08X}': v.hex() for a, v in p['writes'].items()},
                        'baseline': {f'{a:08X}': v.hex() for a, v in p['baseline'].items()},
                    }
                    for name, p in _profiles.items()
                },
            }
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def _cur() -> dict:
    return _profiles[_current]


# ---------------------------------------------------------------------------
# Public write/read API (replacement for dolphin_memory_engine.write_bytes)
# ---------------------------------------------------------------------------

def write_bytes(addr: int, data) -> None:
    """Tracked replacement: snapshot baseline (RAM value just before first
    touch) on first write, record latest value, then forward to the real
    write_bytes."""
    _ensure_loaded()
    data = bytes(data)
    with _lock:
        cur = _cur()
        if addr not in cur['baseline']:
            try:
                cur['baseline'][addr] = bytes(read_bytes(addr, len(data)))
            except Exception:
                cur['baseline'][addr] = b'\x00' * len(data)
        cur['writes'][addr] = data
    _raw_write_bytes(addr, data)
    _save()


def snapshot(persistable_only: bool = True) -> list:
    """List of (addr, value_bytes, baseline_bytes) for the current profile,
    sorted by addr, with no-op writes (final value == baseline) filtered out.

    By default also drops writes targeting non-persistable addresses (anything
    outside the ItemData template region). Those are session-specific runtime
    state — gold, current HP, equipment slots, the "已行动" flag — and forcing
    them on every game load via AR codes either no-ops or actively breaks the
    game (e.g. permanent infinite action). Pass persistable_only=False for an
    unfiltered view (debugging, or showing the user how many transient edits
    exist in the current session)."""
    _ensure_loaded()
    if persistable_only:
        from parameter.address_decoder import is_persistable
    with _lock:
        cur = _cur()
        out = []
        for addr in sorted(cur['writes']):
            new = cur['writes'][addr]
            base = cur['baseline'].get(addr)
            if base is not None and base == new:
                continue
            if persistable_only and not is_persistable(addr):
                continue
            out.append((addr, new, base))
        return out


def count(persistable_only: bool = True) -> int:
    """Number of net (non-reverted) writes; by default in the persistable
    region only. Pass persistable_only=False to count everything."""
    return len(snapshot(persistable_only=persistable_only))


def reset() -> None:
    """Clear writes + baseline for the current profile."""
    _ensure_loaded()
    with _lock:
        cur = _cur()
        cur['writes'].clear()
        cur['baseline'].clear()
    _save()


# ---------------------------------------------------------------------------
# Profile management
# ---------------------------------------------------------------------------

def list_profiles() -> list:
    _ensure_loaded()
    with _lock:
        return sorted(_profiles.keys())


def current_profile_name() -> str:
    _ensure_loaded()
    with _lock:
        return _current


def set_current_profile(name: str) -> None:
    global _current
    _ensure_loaded()
    with _lock:
        if name not in _profiles:
            raise KeyError(f'profile {name!r} 不存在')
        _current = name
    _save()


def new_profile(name: str, switch_to: bool = True) -> None:
    """Create an empty profile and (by default) switch to it."""
    global _current
    _ensure_loaded()
    name = name.strip()
    if not name:
        raise ValueError('profile 名不能为空')
    with _lock:
        if name in _profiles:
            raise ValueError(f'profile {name!r} 已存在')
        _profiles[name] = _empty_profile()
        if switch_to:
            _current = name
    _save()


def rename_profile(old: str, new: str) -> None:
    global _current
    _ensure_loaded()
    new = new.strip()
    if not new:
        raise ValueError('profile 名不能为空')
    with _lock:
        if old not in _profiles:
            raise KeyError(f'profile {old!r} 不存在')
        if new in _profiles and new != old:
            raise ValueError(f'profile {new!r} 已存在')
        if old == new:
            return
        _profiles[new] = _profiles.pop(old)
        if _current == old:
            _current = new
    _save()


def delete_profile(name: str) -> None:
    """Remove a profile. Refuses to delete the last remaining profile."""
    global _current
    _ensure_loaded()
    with _lock:
        if name not in _profiles:
            raise KeyError(f'profile {name!r} 不存在')
        if len(_profiles) == 1:
            raise ValueError('不能删除最后一个 profile')
        del _profiles[name]
        if _current == name:
            _current = next(iter(_profiles))
    _save()
