#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for interface.export_codes — AR code generation, INI roundtrip,
description summarisation."""

import os
import sys
import unittest


SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from interface.export_codes import (
    CHEAT_NAME,
    description_from_writes,
    update_ini_text,
    writes_to_ar_codes,
)


class TestWritesToARCodes(unittest.TestCase):
    def test_4byte_aligned(self):
        writes = [(0x807D6D34, b'\x80\x7E\x8D\x82', b'\x00\x00\x00\x00')]
        self.assertEqual(writes_to_ar_codes(writes), ['047D6D34 807E8D82'])

    def test_2byte_aligned(self):
        writes = [(0x807D6A14, b'\x12\x34', b'\x00\x00')]
        self.assertEqual(writes_to_ar_codes(writes), ['027D6A14 00001234'])

    def test_1byte(self):
        writes = [(0x807D6A55, b'\xFF', b'\x0A')]
        self.assertEqual(writes_to_ar_codes(writes), ['007D6A55 000000FF'])

    def test_3byte_unaligned(self):
        # Starts at +1 from 4-byte boundary; falls into 1-byte + 2-byte.
        writes = [(0x807D6A21, b'\x11\x22\x33', b'\x00\x00\x00')]
        self.assertEqual(
            writes_to_ar_codes(writes),
            ['007D6A21 00000011', '027D6A22 00002233'],
        )

    def test_8byte_aligned_splits_into_two_4byte_writes(self):
        writes = [(0x807D6A00, b'\xAA\xBB\xCC\xDD\xEE\xFF\x00\x11', b'\x00' * 8)]
        self.assertEqual(
            writes_to_ar_codes(writes),
            ['047D6A00 AABBCCDD', '047D6A04 EEFF0011'],
        )

    def test_label_emitted_when_include_comments(self):
        writes = [(0x807D6D34, b'\x80\x7E\x8D\x82', b'\x00\x00\x00\x00', 'item 8 trait3')]
        out = writes_to_ar_codes(writes, include_comments=True)
        self.assertEqual(out, ['# item 8 trait3', '047D6D34 807E8D82'])

    def test_label_skipped_when_include_comments_false(self):
        writes = [(0x807D6D34, b'\x80\x7E\x8D\x82', b'\x00\x00\x00\x00', 'item 8 trait3')]
        out = writes_to_ar_codes(writes, include_comments=False)
        self.assertEqual(out, ['047D6D34 807E8D82'])

    def test_empty_writes(self):
        self.assertEqual(writes_to_ar_codes([]), [])


class TestDescription(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(description_from_writes([]), '')

    def test_no_labels(self):
        writes = [(0, b'\x00', b'\x00')]
        self.assertEqual(description_from_writes(writes), '')

    def test_few_labels(self):
        writes = [
            (0, b'\x00', b'\x00', 'A'),
            (4, b'\x00', b'\x00', 'B'),
            (8, b'\x00', b'\x00', 'C'),
        ]
        self.assertEqual(description_from_writes(writes), 'A、B、C')

    def test_many_labels_truncated(self):
        writes = [(i * 4, b'\x00', b'\x00', f'item{i}') for i in range(10)]
        d = description_from_writes(writes, max_items=3)
        self.assertTrue(d.startswith('item0、item1、item2'))
        self.assertIn('… 还有 7 处', d)


class TestINIRoundtrip(unittest.TestCase):
    def test_empty_input_produces_clean_block(self):
        result = update_ini_text('', CHEAT_NAME, ['047D6D34 807E8D82'])
        self.assertIn(f'${CHEAT_NAME}', result)
        self.assertIn('047D6D34 807E8D82', result)
        self.assertIn('[ActionReplay]', result)
        self.assertIn('[ActionReplay_Enabled]', result)
        # Cheat name appears once in [ActionReplay] and once in [ActionReplay_Enabled]
        self.assertEqual(result.count(f'${CHEAT_NAME}'), 2)

    def test_existing_other_cheat_preserved(self):
        existing = (
            '[ActionReplay]\n'
            '$Other Cheat\n'
            '047C0000 12345678\n'
            '\n'
            '$Yet Another\n'
            '04ABABAB ABCDEF12\n'
        )
        result = update_ini_text(existing, CHEAT_NAME, ['047D6D34 807E8D82'])
        self.assertIn('$Other Cheat', result)
        self.assertIn('047C0000 12345678', result)
        self.assertIn('$Yet Another', result)
        self.assertIn('04ABABAB ABCDEF12', result)
        self.assertIn(f'${CHEAT_NAME}', result)

    def test_previous_block_replaced(self):
        existing = (
            f'[ActionReplay]\n'
            f'${CHEAT_NAME}\n'
            f'04OLDADDR DEADBEEF\n'
            f'04OLDADD2 CAFEBABE\n'
            f'\n'
            f'[ActionReplay_Enabled]\n'
            f'${CHEAT_NAME}\n'
        )
        result = update_ini_text(existing, CHEAT_NAME, ['047D6D34 807E8D82'])
        self.assertNotIn('OLDADDR', result)
        self.assertNotIn('CAFEBABE', result)
        self.assertIn('047D6D34 807E8D82', result)
        # Still one entry under enabled
        self.assertEqual(result.count(f'${CHEAT_NAME}'), 2)

    def test_description_inserted(self):
        result = update_ini_text('', CHEAT_NAME, ['047D6D34 807E8D82'],
                                 description='item 8 trait3')
        self.assertIn('*item 8 trait3', result)

    def test_no_description_no_star_line(self):
        result = update_ini_text('', CHEAT_NAME, ['047D6D34 807E8D82'])
        for line in result.splitlines():
            self.assertFalse(line.startswith('*'),
                             f'Unexpected description line: {line!r}')


if __name__ == '__main__':
    unittest.main()
