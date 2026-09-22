from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wow_keybind_sync as sync


def plan(name: str, key: str, macro: str | None = None) -> sync.PlannedBind:
    action = sync.GglEntry("Warrior - Fury", 0, name, "", "", "")
    return sync.PlannedBind(
        action=action,
        key=sync.KeyBind(key),
        ggl_token="sc20_123",
        source="generated",
        macro=macro,
        icon=1,
    )


class DebindParseTests(unittest.TestCase):
    def test_parse_debind_vars_reads_table(self) -> None:
        text = 'DebindVars = {\n    dbver = 5,\n}\n'
        vars_table = sync.parse_debind_vars(text)
        self.assertEqual(vars_table["dbver"], 5)

    def test_parse_debind_vars_rejects_debounce_file(self) -> None:
        text = 'DebounceVars = {\n    dbver = 2,\n}\n'
        with self.assertRaises(sync.LuaParseError) as ctx:
            sync.parse_debind_vars(text)
        self.assertIn("Debind", str(ctx.exception))

    def test_section_to_debind_target_maps_class_and_spec(self) -> None:
        class_file, spec_index = sync.section_to_debind_target("Warrior - Fury")
        self.assertEqual(class_file, "WARRIOR")
        self.assertEqual(spec_index, 2)

    def test_section_to_debind_target_maps_general(self) -> None:
        class_file, spec_index = sync.section_to_debind_target("General")
        self.assertEqual(class_file, "GENERAL")
        self.assertIsNone(spec_index)


class DebindUpdateTests(unittest.TestCase):
    def test_update_debind_writes_shared_general_layer(self) -> None:
        vars_table: dict = {}
        plans = [plan("Charge", "Q", "/cast Charge")]

        added = sync.update_debind(vars_table, "GENERAL", None, plans, replace_managed=True)

        self.assertEqual(added, 1)
        self.assertEqual(vars_table["dbver"], sync.DEBIND_DB_VERSION)
        layer = sync.layer_to_list(vars_table["shared"]["GENERAL"])
        self.assertEqual(len(layer), 1)
        action = layer[0]
        self.assertEqual(action["type"], "macrotext")
        self.assertEqual(action["name"], "Charge")
        self.assertEqual(action["value"], "/cast Charge")
        self.assertEqual(action["key"], "Q")
        self.assertNotIn(sync.DEBIND_MANAGED_MARKER, action)
        self.assertNotIn(sync.DEBIND_MANAGED_MARKER, sync.dump_lua(vars_table))
        self.assertIn("characters", vars_table)
        self.assertIn("migrated", vars_table)
        self.assertIn("options", vars_table)

    def test_update_debind_writes_shared_class_spec_layer(self) -> None:
        vars_table: dict = {}
        plans = [plan("Execute", "E", "/cast Execute")]

        sync.update_debind(vars_table, "WARRIOR", 2, plans, replace_managed=True)

        layer = sync.layer_to_list(vars_table["shared"]["classes"]["WARRIOR"][2])
        self.assertEqual(len(layer), 1)
        self.assertEqual(layer[0]["name"], "Execute")
        self.assertEqual(vars_table["dbver"], sync.DEBIND_DB_VERSION)

    def test_update_debind_keeps_a_newer_profile_version(self) -> None:
        vars_table = {
            "dbver": 6,
            "shared": {"classes": {}},
            "switches": {"$burst": {"mode": "manual", "value": False}},
            "options": {"frameBlacklist": {"blizzard": {"player": False}}},
        }
        plans = [plan("Execute", "E", "/cast Execute")]

        sync.update_debind(vars_table, "WARRIOR", 2, plans, replace_managed=True)

        self.assertEqual(vars_table["dbver"], 6)
        self.assertNotIn("customStates", vars_table)
        self.assertNotIn("blizzframes", vars_table["options"])
        self.assertEqual(
            vars_table["switches"], {"$burst": {"mode": "manual", "value": False}}
        )
        self.assertEqual(
            vars_table["options"]["frameBlacklist"], {"blizzard": {"player": False}}
        )

    def test_update_debind_does_not_add_legacy_keys_beside_modern_ones(self) -> None:
        vars_table = {
            "dbver": 5,
            "shared": {"classes": {}},
            "switches": {},
            "options": {"frameBlacklist": {}},
        }
        plans = [plan("Execute", "E", "/cast Execute")]

        sync.update_debind(vars_table, "WARRIOR", 2, plans, replace_managed=True)

        self.assertNotIn("customStates", vars_table)
        self.assertNotIn("blizzframes", vars_table["options"])

    def test_update_debind_writes_legacy_scaffolding_for_an_old_profile(self) -> None:
        vars_table: dict = {}
        plans = [plan("Execute", "E", "/cast Execute")]

        sync.update_debind(vars_table, "WARRIOR", 2, plans, replace_managed=True)

        self.assertEqual(vars_table["dbver"], sync.DEBIND_DB_VERSION)
        self.assertEqual(vars_table["customStates"], {})
        self.assertEqual(vars_table["options"]["blizzframes"], {})

    def test_update_debind_drops_empty_legacy_tables_left_by_old_versions(self) -> None:
        vars_table = {
            "dbver": 5,
            "shared": {"classes": {}},
            "switches": {"$burst": {"mode": "manual"}},
            "customStates": {},
            "options": {
                "frameBlacklist": {"blizzard": {"player": False}},
                "blizzframes": {},
            },
        }
        plans = [plan("Execute", "E", "/cast Execute")]

        sync.update_debind(vars_table, "WARRIOR", 2, plans, replace_managed=True)

        self.assertNotIn("customStates", vars_table)
        self.assertNotIn("blizzframes", vars_table["options"])
        self.assertEqual(vars_table["switches"], {"$burst": {"mode": "manual"}})

    def test_update_debind_keeps_non_empty_legacy_tables(self) -> None:
        vars_table = {
            "dbver": 5,
            "shared": {"classes": {}},
            "switches": {},
            "customStates": {"$burst": {"mode": 1}},
        }
        plans = [plan("Execute", "E", "/cast Execute")]

        sync.update_debind(vars_table, "WARRIOR", 2, plans, replace_managed=True)

        self.assertEqual(vars_table["customStates"], {"$burst": {"mode": 1}})

    def test_update_debind_replaces_managed_and_keeps_other_actions(self) -> None:
        vars_table = {
            "shared": {
                "GENERAL": {
                    1: {
                        "type": "macrotext",
                        "name": "Old Managed",
                        "value": "/cast Old",
                        "icon": 1,
                        "key": "T",
                        sync.DEBIND_MANAGED_MARKER: True,
                    },
                    2: {
                        "type": "macrotext",
                        "name": "User Action",
                        "value": "/cast User",
                        "icon": 1,
                        "key": "R",
                    },
                }
            }
        }
        plans = [plan("Charge", "Q", "/cast Charge")]

        sync.update_debind(vars_table, "GENERAL", None, plans, replace_managed=True)

        layer = sync.layer_to_list(vars_table["shared"]["GENERAL"])
        names = [action.get("name") for action in layer if isinstance(action, dict)]
        self.assertIn("User Action", names)
        self.assertIn("Charge", names)
        self.assertNotIn("Old Managed", names)
        self.assertTrue(
            all(
                sync.DEBIND_MANAGED_MARKER not in action
                for action in layer
                if isinstance(action, dict)
            )
        )

    def test_update_debind_removes_by_name_and_key_when_replacing(self) -> None:
        vars_table = {
            "shared": {
                "classes": {
                    "WARRIOR": {
                        2: {
                            1: {"type": "macrotext", "name": "Charge", "value": "/cast Charge", "icon": 1, "key": "NUMPAD3"},
                            2: {"type": "macrotext", "name": "Alias", "value": "/cast Alias", "icon": 1, "key": "NUMPAGEDOWN"},
                            3: {"type": "macrotext", "name": "Keep", "value": "/cast Keep", "icon": 1, "key": "G"},
                        }
                    }
                }
            }
        }
        plans = [plan("Charge", "NUMPAD3", "/cast Charge")]

        sync.update_debind(vars_table, "WARRIOR", 2, plans, replace_managed=True)

        layer = sync.layer_to_list(vars_table["shared"]["classes"]["WARRIOR"][2])
        keys = [action.get("key") for action in layer if isinstance(action, dict)]
        names = [action.get("name") for action in layer if isinstance(action, dict)]
        self.assertNotIn("NUMPAGEDOWN", keys)
        self.assertEqual(names.count("Charge"), 1)
        self.assertIn("Keep", names)

    def test_clear_debind_target_only_clears_selected_spec(self) -> None:
        vars_table = {
            "shared": {
                "GENERAL": {1: {"name": "old general"}},
                "classes": {
                    "WARRIOR": {
                        1: {1: {"name": "old arms"}},
                        2: {1: {"name": "old fury"}},
                    }
                },
            }
        }

        removed = sync.clear_debind_target(vars_table, "WARRIOR", 2)

        self.assertEqual(removed, 1)
        self.assertEqual(vars_table["shared"]["classes"]["WARRIOR"][2], {})
        self.assertEqual(vars_table["shared"]["classes"]["WARRIOR"][1][1]["name"], "old arms")
        self.assertEqual(vars_table["shared"]["GENERAL"][1]["name"], "old general")
        self.assertEqual(vars_table["dbver"], sync.DEBIND_DB_VERSION)

    def test_clear_debind_target_clears_general_layer(self) -> None:
        vars_table = {"shared": {"GENERAL": {1: {"name": "old general"}}}}

        removed = sync.clear_debind_target(vars_table, "GENERAL", None)

        self.assertEqual(removed, 1)
        self.assertEqual(vars_table["shared"]["GENERAL"], {})

    def test_clear_debind_target_keeps_a_newer_profile_version(self) -> None:
        vars_table = {
            "dbver": 6,
            "shared": {"GENERAL": {1: {"name": "old general"}}, "classes": {}},
            "switches": {"$burst": {"mode": "manual"}},
            "options": {"frameBlacklist": {"blizzard": {"player": False}}},
        }

        sync.clear_debind_target(vars_table, "GENERAL", None)

        self.assertEqual(vars_table["dbver"], 6)
        self.assertNotIn("customStates", vars_table)
        self.assertNotIn("blizzframes", vars_table["options"])
        self.assertEqual(vars_table["switches"], {"$burst": {"mode": "manual"}})


class DebindLegacyTests(unittest.TestCase):
    def test_legacy_import_not_pending_without_debounce_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "Debounce.lua"
            self.assertFalse(sync.debind_legacy_import_pending(missing, {}))

    def test_legacy_import_pending_when_debounce_file_has_vars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "Debounce.lua"
            legacy.write_text("DebounceVars = {\n    dbver = 2,\n}\n", encoding="utf-8")
            self.assertTrue(sync.debind_legacy_import_pending(legacy, {}))
            self.assertFalse(
                sync.debind_legacy_import_pending(legacy, {"legacyAccountPulled": True})
            )
            self.assertFalse(
                sync.debind_legacy_import_pending(legacy, {"legacyNeeded": False})
            )


if __name__ == "__main__":
    unittest.main()
