from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wow_keybind_sync as sync


class NumpadKeyTests(unittest.TestCase):
    def test_numlock_off_aliases_match_digit_scans(self) -> None:
        aliases = {
            "NUMPADEND": "NUMPAD1",
            "NUMPADCLEAR": "NUMPAD5",
            "NUMPADINSERT": "NUMPAD0",
            "NUMPADDELETE": "NUMPADDECIMAL",
        }
        for alias, canonical in aliases.items():
            with self.subTest(alias=alias):
                self.assertEqual(
                    sync.parse_keybind_label(alias).scan_code,
                    sync.SCAN_CODES[canonical],
                )

    def test_numpad_plus_and_minus_short_labels_parse_with_modifiers(self) -> None:
        self.assertEqual(
            sync.parse_keybind_label("CTRL+NUM+").scan_code,
            sync.SCAN_CODES["NUMPADPLUS"],
        )
        self.assertEqual(
            sync.parse_keybind_label("SHIFT+NUM-").scan_code,
            sync.SCAN_CODES["NUMPADMINUS"],
        )

    def test_numpad_enter_maps_to_extended_scan_code(self) -> None:
        key = sync.parse_keybind_label("NUMPADENTER")
        self.assertEqual(key.scan_code, 0x11C)
        self.assertEqual(key.ggl("123"), "sc11C_123")

    def test_alt_numpad_digits_are_not_generated(self) -> None:
        candidates = sync.key_candidates(
            enabled_scans={sync.SCAN_CODES["NUMPAD1"]},
            enabled_mods={"ALT", "CTRL"},
            allow_unmodified=False,
        )
        self.assertEqual([key.mods for key in candidates], [("CTRL",)])


if __name__ == "__main__":
    unittest.main()
