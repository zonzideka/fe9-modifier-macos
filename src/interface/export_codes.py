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


def writes_to_ar_codes(writes: list, include_comments: bool = False) -> list:
    """Convert tracked writes into AR code lines.

    Each entry is either a 3-tuple (addr, value_bytes, baseline_bytes) or a
    4-tuple (addr, value_bytes, baseline_bytes, label). When include_comments
    is True and a label is present, a ``# label`` line is emitted before that
    entry's code lines (suitable for the on-screen preview).

    Splits multi-byte writes into 4/2/1-byte ops as needed; per-byte addresses
    are computed from each chunk's offset within the write."""
    lines = []
    for entry in writes:
        if len(entry) >= 4:
            addr, val, _base, label = entry[0], entry[1], entry[2], entry[3]
        else:
            addr, val, _base = entry[0], entry[1], entry[2]
            label = ''
        if include_comments and label:
            lines.append(f'# {label}')
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


def description_from_writes(writes: list, max_items: int = 5) -> str:
    """Build a `*description` line summarizing the labelled writes."""
    labels = [e[3] for e in writes if len(e) >= 4 and e[3]]
    if not labels:
        return ''
    head = labels[:max_items]
    tail = f'，… 还有 {len(labels) - max_items} 处' if len(labels) > max_items else ''
    return '、'.join(head) + tail


def update_ini_text(text: str, cheat_name: str, ar_lines: list, description: str = '') -> str:
    """Pure-text INI update: remove our previous block, append new one to
    [ActionReplay], and ensure the cheat is listed under [ActionReplay_Enabled].

    If *description* is non-empty, a ``*description`` line is inserted between
    the cheat name and its code lines (Dolphin treats ``*`` lines as the
    cheat's user-facing description)."""
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
    if description:
        ar_lines_existing.append(f'*{description}')
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


def write_to_dolphin_ini(annotated_writes: list, cheat_name: str = CHEAT_NAME,
                         game_id: str = GAME_ID) -> str:
    """Generate AR codes from annotated writes and write/refresh the cheat
    block in Dolphin's GameSettings INI. Comments are stripped (kept only for
    the on-screen preview); a ``*description`` line summarizes labelled writes.

    Returns the absolute INI path. Creates the directory and file if missing."""
    code_lines = writes_to_ar_codes(annotated_writes, include_comments=False)
    description = description_from_writes(annotated_writes)

    settings = gamesettings_dir()
    os.makedirs(settings, exist_ok=True)
    path = os.path.join(settings, f'{game_id}.ini')
    text = ''
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    new_text = update_ini_text(text, cheat_name, code_lines, description=description)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    return path
