from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wow_keybind_sync as sync
import wow_keybind_app as app


class CleanupTests(unittest.TestCase):
    def test_loader_numpad_clear_aliases_map_to_numpad5(self) -> None:
        for label in ("NUMPADCLEAR", "NUMPADDCLE", "NUMPADCLE"):
            with self.subTest(label=label):
                self.assertEqual(sync.parse_keybind_label(label).scan_code, sync.SCAN_CODES["NUMPAD5"])

    def test_general_actions_are_dynamic_and_keep_config_names(self) -> None:
        names = {
            "Focus Party1",
            "StopCasting",
            "Trinket 1",
            "Health Stone",
            "SBA",
            "",
        }

        self.assertEqual(
            app.general_action_names(names),
            {"Focus Party1", "StopCasting", "Trinket 1", "Health Stone", "SBA"},
        )

    def test_clear_ggl_entries_preserves_names_and_comments(self) -> None:
        text = """[General]\nTargetEnemy=^sc1E_123 ; keep comment\nStartAttack=\n\n[Warrior - Fury]\nCharge=sc20_123\n"""
        sections, lines = sync.parse_ggl_entries(text)

        cleared, removed = sync.clear_ggl_entries(lines, sections["General"])

        self.assertEqual(removed, 1)
        self.assertEqual(
            "\n".join(cleared),
            "[General]\nTargetEnemy=; keep comment\nStartAttack=\n\n[Warrior - Fury]\nCharge=sc20_123",
        )

    def test_clear_ggl_entries_only_changes_selected_section(self) -> None:
        text = """[General]\nTargetEnemy=^sc1E_123\n\n[Warrior - Fury]\nCharge=sc20_123\n"""
        sections, lines = sync.parse_ggl_entries(text)

        cleared, removed = sync.clear_ggl_entries(lines, sections["Warrior - Fury"])

        self.assertEqual(removed, 1)
        self.assertIn("TargetEnemy=^sc1E_123", cleared)
        self.assertIn("Charge=", cleared)

    def test_clear_debounce_target_only_clears_selected_spec(self) -> None:
        vars_table = {
            "WARRIOR": {
                1: {1: {"name": "old arms"}},
                2: {1: {"name": "old fury"}},
            },
            "GENERAL": {1: {"name": "old general"}},
        }
        class_file, spec_index = sync.section_to_debounce_target("Warrior - Fury")

        removed = sync.clear_debounce_target(vars_table, class_file, spec_index)

        self.assertEqual(removed, 1)
        self.assertEqual(vars_table["WARRIOR"][2], {})
        self.assertEqual(vars_table["WARRIOR"][1][1]["name"], "old arms")
        self.assertEqual(vars_table["GENERAL"][1]["name"], "old general")


if __name__ == "__main__":
    unittest.main()
