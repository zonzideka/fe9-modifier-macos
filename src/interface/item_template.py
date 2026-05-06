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
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QSizePolicy, QSpacerItem, QVBoxLayout

from parameter import DataSetting, EnumData
from widget import BackgroundFrame, NameLabel, ValueSpin


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

    def __init__(self, parent):
        BackgroundFrame.__init__(self, parent)

        # Item selector (QComboBox; populated from EnumData IID_MAPPING)
        self._selector = QComboBox(self)
        self._selector.setIconSize(QSize(24, 24))
        self._selector.setMinimumWidth(360)
        self._populate_selector()
        # noinspection PyUnresolvedReferences
        self._selector.currentIndexChanged.connect(self._on_select)

        # Field editors
        for key, _ in self.FIELDS:
            self[key] = ValueSpin(self, value=DataSetting()[key])

        # Layout
        main_layout = QGridLayout()
        main_layout.addWidget(NameLabel('选择物品'), 0, 0, 1, 1)
        main_layout.addWidget(self._selector, 0, 1, 1, 3)
        for i, (key, label) in enumerate(self.FIELDS):
            row = i // 2 + 1
            col = (i % 2) * 2
            main_layout.addWidget(NameLabel(label), row, col, 1, 1)
            main_layout.addWidget(self[key], row, col + 1, 1, 1)

        # Caveat note
        note = QLabel(
            '注意：修改作用于<b>所有</b>该种类物品（例如改"铁剑"攻击会影响地图上所有铁剑）。'
            '改动仅在当前游戏会话生效，读档恢复原值。'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color:#888; padding:6px;')
        main_layout.addWidget(note, len(self.FIELDS) // 2 + 2, 0, 1, 4)

        main_layout.addItem(QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Expanding),
                            len(self.FIELDS) // 2 + 3, 0, 1, 4)
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
        """Read current item entry's values into all field spinboxes."""
        for key, _ in self.FIELDS:
            editor = self[key]
            if editor is not None:
                editor.refresh()
