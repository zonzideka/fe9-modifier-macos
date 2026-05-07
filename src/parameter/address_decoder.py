#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Translate raw RAM addresses written by the modifier into human-readable
labels — used by the Action Replay export to make every code line
self-documenting (e.g. ``# 物品 IID_RAGNELL 特性3``).

We know about two tables:

  - SLOT (live unit state) at DataSetting.SLOT, stride DataSetting.STEP
  - ITEM (global ItemData template) at DataSetting.ITEM_BASE, stride
    DataSetting.ITEM_STEP

For each table we build an offset→fieldname map from DataSetting.setting,
and an entry-index→name list from enum_data.py's *_ENUM dicts (parsed
statically via ast — we don't import EnumData itself because it's a
QObject subclass requiring a Qt application + translator).
"""
import ast
import os

from .data_setting import DataSetting


SLOT_BASE = DataSetting.SLOT
SLOT_STEP = DataSetting.STEP
SLOT_COUNT = DataSetting.COUNT

ITEM_BASE = DataSetting.ITEM_BASE
ITEM_STEP = DataSetting.ITEM_STEP
ITEM_COUNT = DataSetting.ITEM_COUNT


def _extract_enum_keys(file_path: str, dict_attr: str) -> list:
    """Statically pull the dict-literal keys assigned to ``self.<dict_attr>``
    inside any class in *file_path*. Returns [] if anything goes wrong."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Attribute) and tgt.attr == dict_attr and
                        isinstance(node.value, ast.Dict)):
                    out = []
                    for k in node.value.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            out.append(k.value)
                    return out
    return []


_ENUM_FILE = os.path.join(os.path.dirname(__file__), 'enum_data.py')

# These lists assume each *_ENUM dict in enum_data.py is in the same order
# as RAM entry indices. If the assumption fails for some table the decoder
# falls back to the bare entry index.
IID_NAMES = _extract_enum_keys(_ENUM_FILE, 'IID_ENUM')
PID_NAMES = _extract_enum_keys(_ENUM_FILE, 'PID_ENUM')
JID_NAMES = _extract_enum_keys(_ENUM_FILE, 'JID_ENUM')


def _build_field_map(base: int, step: int) -> dict:
    """Map within-entry offset → (name, length) using DataSetting.setting."""
    out = {}
    setting = DataSetting().setting
    end = base + step
    for name, info in setting.items():
        if not isinstance(info, tuple) or len(info) < 2:
            continue
        addr = info[0]
        length = info[1]
        if base <= addr < end:
            off = addr - base
            if off not in out:
                out[off] = (name, length)
    return out


_SLOT_FIELDS = _build_field_map(SLOT_BASE, SLOT_STEP)
_ITEM_FIELDS = _build_field_map(ITEM_BASE, ITEM_STEP)


def decode_address(addr: int) -> str:
    """Human-readable label for a RAM address in one of the known tables.
    Returns '' if the address falls outside both tables."""
    if SLOT_BASE <= addr < SLOT_BASE + SLOT_STEP * SLOT_COUNT:
        idx = (addr - SLOT_BASE) // SLOT_STEP
        off = (addr - SLOT_BASE) % SLOT_STEP
        field_name, _ = _SLOT_FIELDS.get(off, (f'+0x{off:02X}', 0))
        # slot index is a runtime unit-slot (0..158), not a PID — the user
        # picks slots in the modifier UI by character name; the slot # is the
        # closest stable handle we have.
        return f'单位槽 #{idx} {field_name}'
    if ITEM_BASE <= addr < ITEM_BASE + ITEM_STEP * ITEM_COUNT:
        idx = (addr - ITEM_BASE) // ITEM_STEP
        off = (addr - ITEM_BASE) % ITEM_STEP
        field_name, _ = _ITEM_FIELDS.get(off, (f'+0x{off:02X}', 0))
        item = IID_NAMES[idx] if idx < len(IID_NAMES) else f'#{idx}'
        return f'物品 {item} {field_name}'
    return ''


def annotate_writes(writes) -> list:
    """Convenience: take a list of (addr, value_bytes, baseline_bytes) and
    return [(addr, value_bytes, baseline_bytes, label_str), ...]."""
    return [(addr, val, base, decode_address(addr)) for (addr, val, base) in writes]
