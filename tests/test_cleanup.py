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
                key = sync.parse_keybind_label(label)
                self.assertEqual(key.scan_code, sync.SCAN_CODES["NUMPAD5"])
                self.assertEqual(key.human(), "NUMPAD5")
                self.assertEqual(key.debounce(), "NUMPAD5")

    def test_legacy_numpad_page_aliases_are_removed_during_replacement(self) -> None:
        action = sync.GglEntry("Warrior - Fury", 0, "Charge", "", "", "")
        plans = [
            sync.PlannedBind(
                action=action,
                key=sync.KeyBind("NUMPAD3"),
                ggl_token="sc51_123",
                source="generated",
                macro="/cast Charge",
                icon=1,
            ),
            sync.PlannedBind(
                action=sync.GglEntry("Warrior - Fury", 1, "Interrupt", "", "", ""),
                key=sync.KeyBind("NUMPAD9"),
                ggl_token="sc49_123",
                source="generated",
                macro="/cast Interrupt",
                icon=1,
            ),
        ]
        vars_table = {
            "WARRIOR": {
                2: {
                    1: {"name": "old down", "key": "NUMPAGEDOWN"},
                    2: {"name": "old page up", "key": "NUMPADPAGEUP"},
                    3: {"name": "keep", "key": "Q"},
                }
            }
        }

        sync.update_debounce(
            vars_table,
            "WARRIOR",
            2,
            plans,
            replace_managed=True,
        )

        keys = [
            item.get("key")
            for item in sync.layer_to_list(vars_table["WARRIOR"][2])
            if isinstance(item, dict)
        ]
        self.assertNotIn("NUMPAGEDOWN", keys)
        self.assertNotIn("NUMPADPAGEUP", keys)
        self.assertIn("NUMPAD3", keys)
        self.assertIn("NUMPAD9", keys)
        self.assertIn("Q", keys)

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

    def test_numlock_guidance_warns_only_when_numpad_is_selected_and_off(self) -> None:
        self.assertIsNone(app.num_lock_guidance(False, False))
        self.assertEqual(app.num_lock_guidance(True, True), ("OK", "NumPad keys selected; NumLock is ON."))
        status, detail = app.num_lock_guidance(True, False)
        self.assertEqual(status, "WARN")
        self.assertIn("NumLock is OFF", detail)

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
