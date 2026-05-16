#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Item template editor — modifies the live ItemData section in Dolphin RAM.

FE8Data.bin loads at GameCube RAM 0x807CCD60. ItemData section starts at
file offset 0x9CB0 → RAM 0x807D6A10 (count word) / 0x807D6A14 (entry 0).
189 entries × 96 bytes; we expose Mt/Hit/Crit/Wt/Range/Uses/Cost-per-use.

Edits apply globally to all instances of the item type (an Iron Sword's
Mt change affects every Iron Sword on the map immediately). Effect persists
only while the game session runs — re-loading from save reloads original
values from disk.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QLabel, QMessageBox, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout,
)

from parameter import DataSetting, EnumData
from structure import dme_tracking
from widget import BackgroundFrame, MapCombo, NameLabel, ValueSpin


# noinspection PyTypeChecker
class ItemTemplate(BackgroundFrame):
    FIELDS = [
        ('物品_单价', '单价(g/次)'),
        ('物品_耐久', '耐久'),
        ('物品_攻击', '攻击'),
        ('物品_命中', '命中'),
        ('物品_重量', '重量'),
        ('物品_必杀', '必杀'),
        ('物品_最小射程', '最小射程'),
        ('物品_最大射程', '最大射程'),
        ('物品_武器经验', '武器经验'),
    ]
    TRAIT_FIELDS = [(f'物品_特性{i}', f'特性{i}') for i in range(1, 7)]
    EFFECT_FIELDS = [(f'物品_特效{i}', f'特效{i}') for i in range(1, 3)]

    def __init__(self, parent):
        BackgroundFrame.__init__(self, parent)

        # Item selector (QComboBox; populated from EnumData IID_MAPPING)
        self._selector = QComboBox(self)
        self._selector.setIconSize(QSize(24, 24))
        self._selector.setMinimumWidth(360)
        self._populate_selector()
        # noinspection PyUnresolvedReferences
        self._selector.currentIndexChanged.connect(self._on_select)

        # Numeric field editors
        for key, _ in self.FIELDS:
            self[key] = ValueSpin(self, value=DataSetting()[key])
        # Trait dropdowns (6 slots)
        for key, _ in self.TRAIT_FIELDS:
            self[key] = MapCombo(self, EnumData().TRAIT_MAPPING, value=DataSetting()[key])
            self[key].setMinimumWidth(160)
        # Effect dropdowns (2 slots)
        for key, _ in self.EFFECT_FIELDS:
            self[key] = MapCombo(self, EnumData().EFFECT_MAPPING, value=DataSetting()[key])
            self[key].setMinimumWidth(160)

        # Layout
        main_layout = QGridLayout()
        main_layout.addWidget(NameLabel('选择物品'), 0, 0, 1, 1)
        main_layout.addWidget(self._selector, 0, 1, 1, 3)
        # Numeric fields in 2-column grid (rows 1-N)
        for i, (key, label) in enumerate(self.FIELDS):
            row = i // 2 + 1
            col = (i % 2) * 2
            main_layout.addWidget(NameLabel(label), row, col, 1, 1)
            main_layout.addWidget(self[key], row, col + 1, 1, 1)

        numeric_rows = (len(self.FIELDS) + 1) // 2
        # Trait dropdowns: 2-column layout (3 rows × 2 traits)
        trait_start_row = numeric_rows + 1
        for i, (key, label) in enumerate(self.TRAIT_FIELDS):
            row = trait_start_row + i // 2
            col = (i % 2) * 2
            main_layout.addWidget(NameLabel(label), row, col, 1, 1)
            main_layout.addWidget(self[key], row, col + 1, 1, 1)
        # Effect dropdowns: 2-column layout (1 row)
        effect_row = trait_start_row + 3
        for i, (key, label) in enumerate(self.EFFECT_FIELDS):
            col = (i % 2) * 2
            main_layout.addWidget(NameLabel(label), effect_row, col, 1, 1)
            main_layout.addWidget(self[key], effect_row, col + 1, 1, 1)

        # Revert button — restores the current item's fields to the baseline
        # (the RAM values seen the first time the user touched any field this
        # session, i.e. effectively the ROM defaults if nothing else changed).
        self._btn_revert = QPushButton('还原此物品默认', self)
        self._btn_revert.clicked.connect(self._on_revert_item)
        main_layout.addWidget(self._btn_revert, effect_row + 1, 0, 1, 4)

        # Caveat note
        note = QLabel(
            '注意：修改作用于<b>所有</b>该种类物品（例如改"铁剑"攻击会影响地图上所有铁剑）。'
            '改动仅在当前游戏会话生效，读档恢复原值。<br>'
            '特性/特效下拉只列出 ROM 内已存在的选项；将原本为"——"的槽位填入新指针在运行时是<b>安全</b>的'
            '（无 ROM 重定位表限制），但仍建议先手动存档以防引擎对特定槽位有隐藏假设。<br>'
            '<b>还原此物品默认</b>：把当前物品在 RAM 中的所有字段回写到修改器启动时的值；如果已经导出 AR 代码到 Dolphin INI，请另外在 工具 → 清空 Dolphin INI 中本工具的代码块 清掉。'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color:#888; padding:6px;')
        main_layout.addWidget(note, effect_row + 2, 0, 1, 4)

        main_layout.addItem(QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Expanding),
                            effect_row + 3, 0, 1, 4)
        main_layout.setSpacing(3)
        self.setLayout(main_layout)

        # Initial selection: item 0 (Iron Sword)
        self._on_select(0)

    def _populate_selector(self):
        """Fill selector with all IID entries (sorted by their internal index)."""
        mapping = EnumData().IID_MAPPING() or {}
        # mapping is dict {value: (icon_id, name)}; we want them in the same order
        # as items in RAM. mapping value == in-game item id, NOT the RAM index.
        # The RAM ItemData section is indexed 0..188 in declared order; we need
        # to enumerate in that order. The simplest reliable path: use the original
        # order of entries in the IID enumeration as listed in EnumData.
        # mapping.items() order is dict insertion order — relies on enum_data.py.
        self._index_to_iid = []  # list of (iid_value, display_name)
        for value, item in mapping.items():
            if value == 0: continue
            if isinstance(item, tuple):
                icon, name = item
                self._selector.addItem(QIcon(f':/IID/{icon}.gif'), name, value)
                self._index_to_iid.append((value, name))
            else:
                self._selector.addItem(item, value)
                self._index_to_iid.append((value, item))

    def _on_select(self, idx: int):
        """User picked an item — set offset so all field editors read that entry."""
        # idx is the QComboBox row, which matches our enumeration order (item 0 = first entry).
        self.offset = DataSetting.ITEM_STEP * idx
        # Suppress write loops while we read fresh values
        self.refresh()

    def refresh(self):
        """Read current item entry's values into all field editors."""
        for key, _ in self.FIELDS + self.TRAIT_FIELDS + self.EFFECT_FIELDS:
            editor = self[key]
            if editor is not None:
                editor.refresh()

    def _on_revert_item(self):
        """Revert the current item's full entry (0x60 bytes) to its baseline
        in dme_tracking and refresh the editors to show the restored values."""
        idx = self._selector.currentIndex()
        if idx < 0:
            return
        name = (self._index_to_iid[idx][1] if 0 <= idx < len(self._index_to_iid)
                else f'#{idx}')
        start = DataSetting.ITEM_BASE + DataSetting.ITEM_STEP * idx
        end = start + DataSetting.ITEM_STEP
        n = dme_tracking.revert_range(start, end)
        if n == 0:
            QMessageBox.information(
                self, '无需还原',
                f'当前物品 ({name}) 在本会话中没有任何已记录的修改 ——\n'
                'RAM 值已经是修改器看到的初始状态。'
            )
        else:
            QMessageBox.information(
                self, '已还原',
                f'已将 {name} 的 {n} 处字段还原到修改器启动时的原值。\n\n'
                '若已经导出 AR 代码到 Dolphin INI，下次启动游戏时代码仍会重新应用 ——\n'
                '需要配合 工具 → 清空 Dolphin INI 中本工具的代码块 一起使用，\n'
                '才能让 Dolphin 完全恢复 ROM 默认。'
            )
        self.refresh()
