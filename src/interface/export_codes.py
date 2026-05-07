#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Convert tracked RAM writes into Dolphin Action Replay codes and persist
them to the GameSettings INI so they re-apply on every game launch (Cheats
must be enabled in Dolphin's General config).

AR opcode quick reference:
    00aaaaaa 000000vv   1-byte write (value at low byte of vv)
    02aaaaaa 0000vvvv   2-byte write
    04aaaaaa vvvvvvvv   4-byte write
where aaaaaa = address & 0xFFFFFF (the leading 0x80/0x81 is implicit).

A single multi-byte write may straddle 4-byte alignment; we emit the largest
power-of-two write per chunk, splitting as needed.
"""
import os
import platform


GAME_ID = 'GFEJ01'  # Fire Emblem: Path of Radiance, JP region (CN translations are JP-region patches).
CHEAT_NAME = 'FE9 Modifier - 自动应用'  # fixed; we overwrite this single block on each export.


def gamesettings_dir() -> str:
    sys = platform.system()
    if sys == 'Darwin':
        return os.path.expanduser('~/Library/Application Support/Dolphin/GameSettings')
    if sys == 'Linux':
        return os.path.expanduser('~/.config/dolphin-emu/GameSettings')
    if sys == 'Windows':
        return os.path.join(os.environ.get('APPDATA', ''), 'Dolphin Emulator', 'GameSettings')
    return os.path.expanduser('~/Library/Application Support/Dolphin/GameSettings')


def writes_to_ar_codes(writes: list) -> list:
    """Convert [(addr, value_bytes, baseline_bytes), ...] into AR code lines.

    Splits multi-byte writes into 4/2/1-byte ops as needed. Per-byte addresses
    are computed from the chunk's offset within the write."""
    lines = []
    for addr, val, _base in writes:
        offset = 0
        n = len(val)
        while offset < n:
            chunk_addr = (addr + offset) & 0xFFFFFF
            remaining = n - offset
            aligned4 = (addr + offset) % 4 == 0
            aligned2 = (addr + offset) % 2 == 0
            if remaining >= 4 and aligned4:
                v = int.from_bytes(val[offset:offset+4], 'big')
                lines.append(f'04{chunk_addr:06X} {v:08X}')
                offset += 4
            elif remaining >= 2 and aligned2:
                v = int.from_bytes(val[offset:offset+2], 'big')
                lines.append(f'02{chunk_addr:06X} 0000{v:04X}')
                offset += 2
            else:
                lines.append(f'00{chunk_addr:06X} 000000{val[offset]:02X}')
                offset += 1
    return lines


def update_ini_text(text: str, cheat_name: str, ar_lines: list) -> str:
    """Pure-text INI update: remove our previous block, append new one to
    [ActionReplay], and ensure the cheat is listed under [ActionReplay_Enabled]."""
    sections = []
    current = ('', [])
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('[') and s.endswith(']'):
            sections.append(current)
            current = (s, [])
        else:
            current[1].append(line)
    sections.append(current)

    def find_or_create(name):
        for i, (n, _) in enumerate(sections):
            if n == name:
                return i
        sections.append((name, []))
        return len(sections) - 1

    target = f'${cheat_name}'

    ar_idx = find_or_create('[ActionReplay]')
    ar_lines_existing = _strip_cheat_block(sections[ar_idx][1], target)
    while ar_lines_existing and ar_lines_existing[-1].strip() == '':
        ar_lines_existing.pop()
    if ar_lines_existing:
        ar_lines_existing.append('')
    ar_lines_existing.append(target)
    ar_lines_existing.extend(ar_lines)
    sections[ar_idx] = (sections[ar_idx][0], ar_lines_existing)

    en_idx = find_or_create('[ActionReplay_Enabled]')
    en_existing = [l for l in sections[en_idx][1] if l.strip() != target]
    while en_existing and en_existing[-1].strip() == '':
        en_existing.pop()
    en_existing.append(target)
    sections[en_idx] = (sections[en_idx][0], en_existing)

    out = []
    for name, lines in sections:
        if name:
            if out and out[-1] != '':
                out.append('')
            out.append(name)
        out.extend(lines)
    while out and out[-1] == '':
        out.pop()
    out.append('')
    return '\n'.join(out)


def _strip_cheat_block(lines: list, target: str) -> list:
    """Drop a `$Name` line and every line until the next `$` or end of section."""
    out = []
    skipping = False
    for line in lines:
        s = line.strip()
        if s == target:
            skipping = True
            continue
        if skipping:
            if s.startswith('$'):
                skipping = False
            else:
                continue
        out.append(line)
    return out


def write_to_dolphin_ini(ar_lines: list, cheat_name: str = CHEAT_NAME, game_id: str = GAME_ID) -> str:
    """Update Dolphin's GameSettings INI for the given game. Returns the path
    written. Creates the directory and file if missing."""
    settings = gamesettings_dir()
    os.makedirs(settings, exist_ok=True)
    path = os.path.join(settings, f'{game_id}.ini')
    text = ''
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    new_text = update_ini_text(text, cheat_name, ar_lines)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    return path
