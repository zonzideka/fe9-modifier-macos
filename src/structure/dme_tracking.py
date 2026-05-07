#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrap dolphin_memory_engine.write_bytes so every RAM write the modifier
performs is logged. The cumulative net diff (final value vs. value just before
the first write at each address) can later be exported as Dolphin Action
Replay codes — useful for persisting changes to slots fe9-editor cannot
write to ROM (i.e. pointer fields not registered in FE8Data.bin's reloc table).

The wrapper is the single point through which Value.set() pushes RAM writes,
so import this module's `write_bytes` rather than dolphin_memory_engine's.
"""

import threading

from dolphin_memory_engine import read_bytes, write_bytes as _raw_write_bytes


_lock = threading.Lock()
_writes: dict[int, bytes] = {}        # addr -> latest written bytes
_baseline: dict[int, bytes] = {}      # addr -> RAM value just before the first tracked write


def write_bytes(addr: int, data) -> None:
    """Tracked replacement for dolphin_memory_engine.write_bytes.
    Records the address and final value, snapshotting the prior RAM value
    on first touch so we can compute net change at export time."""
    data = bytes(data)
    with _lock:
        if addr not in _baseline:
            try:
                _baseline[addr] = bytes(read_bytes(addr, len(data)))
            except Exception:
                _baseline[addr] = b'\x00' * len(data)
        _writes[addr] = data
    _raw_write_bytes(addr, data)


def snapshot() -> list:
    """Return current net writes as a list of (addr, value_bytes, baseline_bytes),
    sorted by addr, dropping entries where the user reverted to the baseline value."""
    with _lock:
        out = []
        for addr in sorted(_writes):
            new = _writes[addr]
            base = _baseline.get(addr)
            if base is not None and base == new:
                continue
            out.append((addr, new, base))
        return out


def reset() -> None:
    """Clear the log. Call after the modifier is fully initialized so that any
    initial-state writes (if widgets push values on bind) don't leak into the
    user's session diff."""
    with _lock:
        _writes.clear()
        _baseline.clear()


def count() -> int:
    """Number of net (non-reverted) writes currently in the log."""
    return len(snapshot())
