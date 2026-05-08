#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for structure.dme_tracking — write logging + multi-profile +
JSON persistence. Mocks dolphin_memory_engine so tests don't touch real RAM."""

import json
import os
import sys
import tempfile
import unittest


SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def _install_mocks(t_module):
    """Replace dme reads/writes with an in-memory fake."""
    fake_ram = {}

    def _read_bytes(addr, n):
        return fake_ram.get(addr, b'\x00' * n)[:n]

    def _write_bytes(addr, data):
        fake_ram[addr] = bytes(data)

    t_module.read_bytes = _read_bytes
    t_module._raw_write_bytes = _write_bytes
    return fake_ram


def _fresh_module():
    """Reload structure.dme_tracking with module-level state reset and
    storage redirected to a fresh temp directory. Returns (module, store_dir)."""
    if 'structure.dme_tracking' in sys.modules:
        del sys.modules['structure.dme_tracking']
    from structure import dme_tracking as t  # type: ignore
    tmp = tempfile.mkdtemp()
    t._config_dir = lambda: tmp
    _install_mocks(t)
    # Reset module-level state to mimic a clean process
    t._loaded = False
    t._profiles = {t.DEFAULT_PROFILE: t._empty_profile()}
    t._current = t.DEFAULT_PROFILE
    return t, tmp


class TestWriteAndSnapshot(unittest.TestCase):
    def test_basic_write_appears_in_snapshot(self):
        t, _ = _fresh_module()
        t.write_bytes(0x1000, b'\xAB\xCD')
        s = t.snapshot(persistable_only=False)
        self.assertEqual(len(s), 1)
        addr, val, base = s[0]
        self.assertEqual(addr, 0x1000)
        self.assertEqual(val, b'\xAB\xCD')
        self.assertEqual(base, b'\x00\x00')  # baseline from mock fake_ram

    def test_revert_to_baseline_drops_from_snapshot(self):
        t, _ = _fresh_module()
        # Write a non-zero value, then "revert" by writing zeros back
        t.write_bytes(0x2000, b'\xFF\xFF')
        t.write_bytes(0x2000, b'\x00\x00')
        self.assertEqual(t.snapshot(persistable_only=False), [])
        self.assertEqual(t.count(persistable_only=False), 0)

    def test_first_baseline_persists_across_overwrites(self):
        t, _ = _fresh_module()
        t.write_bytes(0x3000, b'\x11')
        t.write_bytes(0x3000, b'\x22')
        t.write_bytes(0x3000, b'\x33')
        s = t.snapshot(persistable_only=False)
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0][1], b'\x33')      # latest value
        self.assertEqual(s[0][2], b'\x00')      # original baseline

    def test_reset_clears_current_profile_only(self):
        t, _ = _fresh_module()
        t.write_bytes(0x4000, b'\x01')
        t.new_profile('alt')
        t.write_bytes(0x5000, b'\x02')
        t.set_current_profile(t.DEFAULT_PROFILE)
        t.reset()
        self.assertEqual(t.snapshot(persistable_only=False), [])
        t.set_current_profile('alt')
        self.assertEqual(len(t.snapshot(persistable_only=False)), 1)

    def test_persistable_only_filters_non_item_writes(self):
        from parameter.address_decoder import ITEM_BASE
        t, _ = _fresh_module()
        # ItemData write — should be persistable
        t.write_bytes(ITEM_BASE + 0x41, b'\xff')
        # SLOT write — should NOT be persistable
        t.write_bytes(0x802AF78C, b'\x63')
        # Random address — should NOT be persistable
        t.write_bytes(0x12345, b'\xAA')

        all_writes = t.snapshot(persistable_only=False)
        persistable_writes = t.snapshot(persistable_only=True)
        self.assertEqual(len(all_writes), 3)
        self.assertEqual(len(persistable_writes), 1)
        self.assertEqual(persistable_writes[0][0], ITEM_BASE + 0x41)
        # count() defaults to persistable_only=True
        self.assertEqual(t.count(), 1)
        self.assertEqual(t.count(persistable_only=False), 3)


class TestPersistence(unittest.TestCase):
    def test_writes_persist_across_module_reload(self):
        t, store_dir = _fresh_module()
        t.write_bytes(0x6000, b'\xDE\xAD')
        t.write_bytes(0x7000, b'\xBE\xEF\xCA\xFE')
        path = t.store_path()
        self.assertTrue(os.path.exists(path))

        # Reload module fresh, point storage at the same dir, expect data
        if 'structure.dme_tracking' in sys.modules:
            del sys.modules['structure.dme_tracking']
        from structure import dme_tracking as t2  # type: ignore
        t2._config_dir = lambda: store_dir
        _install_mocks(t2)
        t2._loaded = False
        s = t2.snapshot(persistable_only=False)
        self.assertEqual(len(s), 2)
        self.assertEqual({addr for addr, _, _ in s}, {0x6000, 0x7000})

    def test_corrupt_storage_does_not_crash(self):
        t, store_dir = _fresh_module()
        with open(os.path.join(store_dir, 'profiles.json'), 'w') as f:
            f.write('{not json')
        # Force reload
        t._loaded = False
        # Should not raise; falls back to empty defaults
        self.assertEqual(t.snapshot(persistable_only=False), [])
        self.assertEqual(t.list_profiles(), [t.DEFAULT_PROFILE])


class TestProfiles(unittest.TestCase):
    def test_new_profile_switches_to_it(self):
        t, _ = _fresh_module()
        t.new_profile('hard-mode')
        self.assertEqual(t.current_profile_name(), 'hard-mode')
        self.assertEqual(t.snapshot(), [])  # new profile is empty

    def test_new_profile_no_switch(self):
        t, _ = _fresh_module()
        t.new_profile('alt', switch_to=False)
        self.assertEqual(t.current_profile_name(), t.DEFAULT_PROFILE)
        self.assertIn('alt', t.list_profiles())

    def test_duplicate_profile_name_raises(self):
        t, _ = _fresh_module()
        t.new_profile('x')
        with self.assertRaises(ValueError):
            t.new_profile('x')

    def test_rename_keeps_current_pointer(self):
        t, _ = _fresh_module()
        t.write_bytes(0x8000, b'\x01')
        t.rename_profile(t.DEFAULT_PROFILE, 'production')
        self.assertEqual(t.current_profile_name(), 'production')
        self.assertEqual(len(t.snapshot(persistable_only=False)), 1)

    def test_delete_last_profile_refused(self):
        t, _ = _fresh_module()
        with self.assertRaises(ValueError):
            t.delete_profile(t.DEFAULT_PROFILE)

    def test_delete_current_falls_back(self):
        t, _ = _fresh_module()
        t.new_profile('alt')
        # Now current = alt; delete alt should fall back to default
        t.delete_profile('alt')
        self.assertEqual(t.current_profile_name(), t.DEFAULT_PROFILE)
        self.assertNotIn('alt', t.list_profiles())

    def test_writes_isolated_per_profile(self):
        t, _ = _fresh_module()
        t.write_bytes(0xA000, b'\x01')
        t.new_profile('alt')
        t.write_bytes(0xB000, b'\x02')
        # Default has 0xA000, alt has 0xB000
        self.assertEqual({a for a, _, _ in t.snapshot(persistable_only=False)}, {0xB000})
        t.set_current_profile(t.DEFAULT_PROFILE)
        self.assertEqual({a for a, _, _ in t.snapshot(persistable_only=False)}, {0xA000})


if __name__ == '__main__':
    unittest.main()
