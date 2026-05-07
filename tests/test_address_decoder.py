#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for parameter.address_decoder — RAM address → human label."""

import os
import sys
import unittest


SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from parameter.address_decoder import (
    IID_NAMES,
    JID_NAMES,
    PID_NAMES,
    annotate_writes,
    decode_address,
    ITEM_BASE,
    ITEM_STEP,
    SLOT_BASE,
    SLOT_STEP,
)


class TestEnumExtraction(unittest.TestCase):
    def test_iid_names_loaded(self):
        # 189 items in FE9 — IID_ENUM should mirror that
        self.assertEqual(len(IID_NAMES), 189)
        self.assertEqual(IID_NAMES[0], 'IID_IRONSWORD')

    def test_pid_jid_names_loaded(self):
        self.assertGreater(len(PID_NAMES), 100)  # ~340 in vanilla
        self.assertGreater(len(JID_NAMES), 100)  # ~115


class TestDecodeAddress(unittest.TestCase):
    def test_unknown_address_returns_empty(self):
        self.assertEqual(decode_address(0x12345678), '')

    def test_item_entry_zero_known_field(self):
        # Item 0, +0x41 = 单价 (cost)
        addr = ITEM_BASE + 0 * ITEM_STEP + 0x41
        label = decode_address(addr)
        self.assertIn('IID_IRONSWORD', label)
        self.assertIn('物品_单价', label)

    def test_item_trait_slot(self):
        # Item 8, +0x20 = 物品_特性3
        addr = ITEM_BASE + 8 * ITEM_STEP + 0x20
        label = decode_address(addr)
        self.assertIn('IID_LONGSWORD', label)  # IID_NAMES[8]
        self.assertIn('物品_特性3', label)

    def test_item_unknown_offset_falls_back(self):
        # Item 0, +0x05 — not in DataSetting, should fall back to '+0x05'
        addr = ITEM_BASE + 0 * ITEM_STEP + 0x05
        label = decode_address(addr)
        self.assertIn('IID_IRONSWORD', label)
        self.assertIn('+0x05', label)

    def test_slot_known_field(self):
        # Slot 0, +0x1A8 = ＨＰ (HP)
        addr = SLOT_BASE + 0 * SLOT_STEP + 0x1A8
        label = decode_address(addr)
        self.assertIn('单位槽 #0', label)
        self.assertIn('ＨＰ', label)

    def test_slot_index_in_label(self):
        addr = SLOT_BASE + 5 * SLOT_STEP + 0x1A8
        label = decode_address(addr)
        self.assertIn('单位槽 #5', label)


class TestAnnotateWrites(unittest.TestCase):
    def test_returns_4_tuples(self):
        writes = [(ITEM_BASE + 0x41, b'\xff', b'\x0A')]
        out = annotate_writes(writes)
        self.assertEqual(len(out), 1)
        self.assertEqual(len(out[0]), 4)
        self.assertIn('IID_IRONSWORD', out[0][3])

    def test_unknown_address_gets_empty_label(self):
        writes = [(0x12345678, b'\x00', b'\x00')]
        out = annotate_writes(writes)
        self.assertEqual(out[0][3], '')


if __name__ == '__main__':
    unittest.main()
