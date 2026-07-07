#!/usr/bin/env python3
from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

import wow_keybind_sync as sync


APP_VERSION = "1.2.6-dev.2"


GLOBAL_ACTIONS = [
    "TargetMouseOver",
    "TargetEnemy",
    "TargetLastTarget",
    "StartAttack",
    "Trinket1",
    "Trinket2",
    "HealthStone",
    "HealingPotion",
    "Target Arena1",
    "Target Arena2",
    "Target Arena3",
    "Target Arena4",
    "Target Arena5",
    "Focus Arena1",
    "Focus Arena2",
    "Focus Arena3",
    "Focus Arena4",
    "Focus Arena5",
]

GLOBAL_CUSTOM_TARGETING_ACTIONS = {
    "TargetMouseOver",
    "TargetEnemy",
    "TargetLastTarget",
    "Target Arena1",
    "Target Arena2",
    "Target Arena3",
    "Target Arena4",
    "Target Arena5",
    "Focus Arena1",
    "Focus Arena2",
    "Focus Arena3",
    "Focus Arena4",
    "Focus Arena5",
}

CUSTOM_MACRO_IMPORT_HEADERS = ["section", "loader_action", "macro_name", "macro_text", "enabled"]

CUSTOM_MACRO_TEMPLATE_INSTRUCTIONS = [
    {
        "section": "# AI INSTRUCTIONS",
        "loader_action": "Upload this CSV template with the profile PDF or custom macro notes.",
        "macro_name": "Ask the AI to fill import-ready rows using the header above.",
        "macro_text": "Return CSV only. Do not invent mappings. Only include mappings clearly stated in the source.",
        "enabled": "",
    },
    {
        "section": "# FIELD RULES",
        "loader_action": "loader_action must be the loader/pixel/action being reused and must match Config.ini.",
        "macro_name": "macro_name is the in-game macro name to create.",
        "macro_text": "macro_text is the exact macro body. Use literal \\n for multi-line macros.",
        "enabled": "true",
    },
    {
        "section": "# SECTION RULES",
        "loader_action": "Use the exact class/spec section when known.",
        "macro_name": "Use selected or current if the user will import after choosing the right class/spec.",
        "macro_text": "Use General only for supported global targeting actions.",
        "enabled": "",
    },
]

GLOBAL_BIND_DISPLAY_GROUPS = [
    (
        "Targeting",
        "Mouseover, enemy, last target, target arena 1-5, focus arena 1-5",
    ),
    (
        "Utility",
        "Start attack, trinket 1/2, healthstone, healing potion",
    ),
]


@dataclasses.dataclass(frozen=True)
class PreflightItem:
    label: str
    status: str
    detail: str
    blocking: bool = False


@dataclasses.dataclass(frozen=True)
class BackupInfo:
    backup_path: Path
    target_path: Path
    kind: str
    mtime: float


APPLY_BLOCKING_PROCESSES = {
    "wow.exe": "World of Warcraft",
    "wowt.exe": "World of Warcraft",
    "wowclassic.exe": "World of Warcraft Classic",
    "wowclassict.exe": "World of Warcraft Classic",
    "fpsmonitor.exe": "FPS Monitor / loader",
    "fps monitor.exe": "FPS Monitor / loader",
    "ggl.exe": "GGL loader",
    "ggloader.exe": "GGL loader",
}


LIGHT_THEME = {
    "bg": "#f0f0f0",
    "panel": "#f0f0f0",
    "panel_2": "#f0f0f0",
    "field": "#ffffff",
    "text": "#000000",
    "muted": "#555555",
    "gold": "#000000",
    "gold_dark": "#d9d9d9",
    "blue": "#0078d7",
    "blue_dark": "#f0f0f0",
    "button_text": "#000000",
    "danger": "#8a3b3b",
    "danger_bg": "#f7e6e6",
    "danger_hover": "#edd0d0",
    "ok_bg": "#e7f1fb",
    "chip_bg": "#f4f4f4",
    "scrollbar": "#c9c9c9",
    "scrollbar_hover": "#b5b5b5",
    "secondary_button": "#6b7280",
    "secondary_button_hover": "#4b5563",
    "select_text": "#ffffff",
}

DARK_THEME = {
    "bg": "#15171b",
    "panel": "#15171b",
    "panel_2": "#15171b",
    "field": "#22262d",
    "text": "#f4f6f8",
    "muted": "#a7adb7",
    "gold": "#f4f6f8",
    "gold_dark": "#3a404a",
    "blue": "#4da3ff",
    "blue_dark": "#1d2d3f",
    "button_text": "#ffffff",
    "danger": "#ff9a9a",
    "danger_bg": "#3b2428",
    "danger_hover": "#4a2c32",
    "ok_bg": "#18304a",
    "chip_bg": "#2b3038",
    "scrollbar": "#3f4652",
    "scrollbar_hover": "#555f6e",
    "secondary_button": "#4b5563",
    "secondary_button_hover": "#5b6574",
    "select_text": "#ffffff",
}

THEME = dict(LIGHT_THEME)


def set_app_theme(dark_mode: bool) -> None:
    THEME.clear()
    THEME.update(DARK_THEME if dark_mode else LIGHT_THEME)


def ctk_theme(key: str) -> tuple[str, str]:
    return LIGHT_THEME[key], DARK_THEME[key]


PAGE_SCROLL_MULTIPLIER = 3
INNER_SCROLL_UNITS = 3


class PageScrollableFrame(ctk.CTkScrollableFrame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._nested_scroll_roots: set[tk.Widget] = set()

    def add_nested_scroll_root(self, widget: tk.Widget) -> None:
        for attr in ("_parent_canvas", "_parent_frame", "_scrollbar"):
            nested = getattr(widget, attr, None)
            if nested is not None:
                self._nested_scroll_roots.add(nested)
        self._nested_scroll_roots.add(widget)

    def _is_nested_scroll_widget(self, widget: tk.Widget) -> bool:
        while widget is not None:
            if widget in self._nested_scroll_roots:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _mouse_wheel_all(self, event: tk.Event):
        if self._is_nested_scroll_widget(event.widget):
            return None
        if not self.check_if_master_is_canvas(event.widget):
            return None
        self.scroll_from_wheel_event(event)
        return None

    def _wheel_units(self, event: tk.Event) -> int:
        if sys.platform.startswith("win"):
            return -int(event.delta / 6) * PAGE_SCROLL_MULTIPLIER
        return -event.delta * PAGE_SCROLL_MULTIPLIER

    def scroll_units(self, units: int, horizontal: bool = False) -> bool:
        if not units:
            return False
        if horizontal:
            if self._parent_canvas.xview() != (0.0, 1.0):
                self._parent_canvas.xview("scroll", units, "units")
                return True
            return False
        if self._parent_canvas.yview() != (0.0, 1.0):
            self._parent_canvas.yview("scroll", units, "units")
            return True
        return False

    def scroll_from_wheel_event(self, event: tk.Event) -> bool:
        return self.scroll_units(self._wheel_units(event), horizontal=self._shift_pressed)


CONFIG_EXAMPLE_PATH = r"C:\Program Files (x86)\Your Folder Name\Config.ini"
SEED_CONFIG_EXAMPLE_PATH = r"C:\Program Files (x86)\Your Folder Name\Config BACKUP.ini"
DEBOUNCE_EXAMPLE_PATH = (
    r"C:\World of Warcraft\_retail_\WTF\Account\YOUR ACCOUNT NUMBER\SavedVariables\Debounce.lua"
)
BINDPAD_EXAMPLE_PATH = (
    r"C:\World of Warcraft\_retail_\WTF\Account\YOUR ACCOUNT NUMBER\SavedVariables\BindPad.lua"
)


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def settings_path() -> Path:
    return app_dir() / "wow_keybind_sync_settings.json"


def load_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        backup = path.with_name(path.name + ".bak")
        try:
            return json.loads(backup.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}


def save_settings(data: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2)
    backup = path.with_name(path.name + ".bak")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    temp = path.with_name(f".{path.name}.tmp-{stamp}")
    try:
        temp.write_text(text, encoding="utf-8")
        if path.exists():
            shutil.copy2(path, backup)
        temp.replace(path)
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")


def backup_target_from_path(path: Path) -> Path | None:
    name = path.name
    if ".bak-" in name:
        original_name = name.split(".bak-", 1)[0]
    elif name.endswith(".bak"):
        original_name = name[: -len(".bak")]
    else:
        return None
    if not original_name:
        return None
    return path.with_name(original_name)


def file_size_label(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "unknown size"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def account_debounce_candidate(path: Path) -> Path | None:
    if path.name.lower() != "debounce.lua" or len(path.parents) < 4:
        return None
    candidate = path.parents[3] / "SavedVariables" / "Debounce.lua"
    if not candidate.exists() or candidate == path:
        return None
    try:
        text, _, _ = sync.read_text(candidate)
    except Exception:
        return None
    if re.search(r"\bDebounceVars\s*=", text):
        return candidate
    return None


def normalize_debounce_path(path: Path) -> Path:
    if not path.exists():
        return path
    try:
        text, _, _ = sync.read_text(path)
    except Exception:
        return path
    if re.search(r"\bDebounceVarsPerChar\s*=", text):
        candidate = account_debounce_candidate(path)
        if candidate:
            return candidate
    return path


def load_bindpad_profiles(path: Path) -> list[tuple[str, str]]:
    text, _, _ = sync.read_text(path)
    lower_parts = {part.lower() for part in path.parts}
    if "interface" in lower_parts and "addons" in lower_parts:
        raise RuntimeError(
            "That looks like the BindPad addon folder/source file. Choose the WTF\\Account\\YOUR ACCOUNT NUMBER\\SavedVariables\\BindPad.lua file instead."
        )
    if "BINDPAD_GENERAL_TAB" in text or "BindPad Addon" in text[:500]:
        raise RuntimeError(
            "That looks like BindPad addon code, not saved user data. Choose the WTF\\Account\\YOUR ACCOUNT NUMBER\\SavedVariables\\BindPad.lua file instead."
        )
    vars_table = sync.parse_bindpad_vars(text)
    return [(sync.bindpad_profile_label(key), key) for key in sync.bindpad_profile_keys(vars_table)]


def find_running_processes(processes: dict[str, str]) -> list[str]:
    try:
        output = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []

    found: set[str] = set()
    for row in csv.reader(output.splitlines()):
        if not row:
            continue
        label = processes.get(row[0].strip().lower())
        if label:
            found.add(label)
    return sorted(found)


def load_sections(ggl_config: Path) -> list[str]:
    return load_sections_and_action_names(ggl_config)[0]


def section_order(sections: dict[str, list[sync.GglEntry]]) -> list[str]:
    preferred: list[str] = []
    if "General" in sections:
        preferred.append("General")
    for class_name, specs in sync.SPEC_INDEX.items():
        for spec_name in specs:
            section = f"{class_name} - {spec_name}"
            if section in sections:
                preferred.append(section)
    other = sorted(name for name in sections if name not in preferred)
    return preferred + other


def load_sections_and_action_names(ggl_config: Path) -> tuple[list[str], dict[str, list[str]]]:
    text, _, _ = sync.read_text(ggl_config)
    sections, _ = sync.parse_ggl_entries(text)
    return section_order(sections), {
        section: [entry.name for entry in entries]
        for section, entries in sections.items()
    }


def load_action_names(ggl_config: Path, section: str) -> list[str]:
    text, _, _ = sync.read_text(ggl_config)
    sections, _ = sync.parse_ggl_entries(text)
    return [entry.name for entry in sections.get(section, [])]


def safe_path_key(path: Path) -> str:
    try:
        return str(path.resolve()).casefold()
    except OSError:
        return str(path).casefold()


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def existing_drive_roots() -> list[Path]:
    roots: list[Path] = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = Path(f"{letter}:\\")
        try:
            if root.exists():
                roots.append(root)
        except OSError:
            continue
    return roots


def safe_glob(path: Path, pattern: str) -> list[Path]:
    try:
        return list(path.glob(pattern))
    except OSError:
        return []


def safe_iter_dirs(path: Path) -> list[Path]:
    try:
        return [child for child in path.iterdir() if child.is_dir()]
    except OSError:
        return []


def dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = safe_path_key(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def wow_roots_from_path(path: Path) -> list[Path]:
    roots: list[Path] = []
    for part in [path, *path.parents]:
        name = part.name.lower()
        if name == "_retail_":
            roots.append(part.parent)
        elif name.startswith("world of warcraft"):
            roots.append(part)
    return roots


def likely_wow_roots(hint_path: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    if hint_path:
        roots.extend(wow_roots_from_path(hint_path))

    for drive in existing_drive_roots():
        search_parents = [
            drive,
            drive / "Games",
            drive / "Program Files",
            drive / "Program Files (x86)",
        ]
        for parent in search_parents:
            roots.extend(path for path in safe_glob(parent, "World of Warcraft*") if path.is_dir())

    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        raw = os.environ.get(env_name)
        if raw:
            base = Path(raw)
            roots.extend(path for path in safe_glob(base, "World of Warcraft*") if path.is_dir())

    return dedupe_paths(roots)


def canonical_debounce_candidate(path: Path) -> Path | None:
    if path.name.lower() != "debounce.lua" or not path.exists():
        return None
    lower_parts = {part.lower() for part in path.parts}
    if "interface" in lower_parts and "addons" in lower_parts:
        return None
    normalized = normalize_debounce_path(path)
    if normalized.name.lower() != "debounce.lua" or not normalized.exists():
        return None
    try:
        text, _, _ = sync.read_text(normalized)
        sync.parse_debounce_vars(text)
    except Exception:
        return None
    return normalized


def canonical_bindpad_candidate(path: Path) -> Path | None:
    if path.name.lower() != "bindpad.lua" or not path.exists():
        return None
    lower_parts = {part.lower() for part in path.parts}
    if "interface" in lower_parts and "addons" in lower_parts:
        return None
    try:
        text, _, _ = sync.read_text(path)
        sync.parse_bindpad_vars(text)
    except Exception:
        return None
    return path


def find_addon_saved_variable_candidates(addon: str, hint_path: Path | None = None) -> list[Path]:
    filename = "BindPad.lua" if addon == "BindPad" else "Debounce.lua"
    raw_candidates: list[Path] = []
    if hint_path:
        raw_candidates.append(hint_path)
        if hint_path.is_dir():
            raw_candidates.append(hint_path / filename)
        elif hint_path.parent:
            raw_candidates.append(hint_path.parent / filename)

    for root in likely_wow_roots(hint_path):
        retail = root / "_retail_"
        raw_candidates.extend(safe_glob(retail, f"WTF/Account/*/SavedVariables/{filename}"))
        raw_candidates.extend(safe_glob(root, f"WTF/Account/*/SavedVariables/{filename}"))

    canonical: list[Path] = []
    for candidate in raw_candidates:
        path = (
            canonical_bindpad_candidate(candidate)
            if addon == "BindPad"
            else canonical_debounce_candidate(candidate)
        )
        if path:
            canonical.append(path)

    return sorted(dedupe_paths(canonical), key=safe_mtime, reverse=True)


def canonical_config_candidate(path: Path) -> Path | None:
    if path.name.lower() != "config.ini" or not path.exists():
        return None
    try:
        text, _, _ = sync.read_text(path)
        sections, _ = sync.parse_ggl_entries(text)
    except Exception:
        return None
    if "General" in sections:
        return path
    for class_name, specs in sync.SPEC_INDEX.items():
        for spec_name in specs:
            if f"{class_name} - {spec_name}" in sections:
                return path
    return None


def likely_config_ini_candidates(hint_path: Path | None = None) -> list[Path]:
    raw_candidates: list[Path] = []
    if hint_path:
        raw_candidates.append(hint_path)
        if hint_path.is_dir():
            raw_candidates.append(hint_path / "Config.ini")
        elif hint_path.parent:
            raw_candidates.append(hint_path.parent / "Config.ini")

    raw_candidates.append(app_dir() / "Config.ini")

    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        raw = os.environ.get(env_name)
        if not raw:
            continue
        base = Path(raw)
        raw_candidates.append(base / "Config.ini")
        for child in safe_iter_dirs(base):
            raw_candidates.append(child / "Config.ini")

    for drive in existing_drive_roots():
        for child in safe_iter_dirs(drive):
            name = child.name.lower()
            if any(token in name for token in ("loader", "monitor", "ggl", "pixel", "rotation")):
                raw_candidates.append(child / "Config.ini")

    canonical = [path for path in (canonical_config_candidate(candidate) for candidate in raw_candidates) if path]
    return sorted(dedupe_paths(canonical), key=safe_mtime, reverse=True)


def run_once(
    *,
    section: str,
    action_names: set[str] | None,
    addon_path: Path,
    macro_addon: str,
    bindpad_profile: str | None,
    ggl_config: Path,
    seed_config: Path | None,
    apply: bool,
    overwrite_ggl: bool,
    reports_dir: Path,
    layout: sync.KeyLayout,
    enabled_scans: set[int],
    random_seed: str | None,
    enabled_mods: set[str],
    allow_unmodified: bool,
    blocked_keys: set[sync.KeyBind],
    extra_blocked_keys: set[sync.KeyBind] | None = None,
    macro_overrides: dict[str, sync.MacroOverride] | None = None,
    loader_context_sections: set[str] | None = None,
    cleanup_names: set[str] | None = None,
) -> tuple[str, list[sync.PlannedBind]]:
    ggl_text, ggl_encoding, ggl_newline = sync.read_text(ggl_config)
    sections, ggl_lines = sync.parse_ggl_entries(ggl_text)

    seed_sections = None
    if seed_config and seed_config.exists():
        seed_text, _, _ = sync.read_text(seed_config)
        seed_sections, _ = sync.parse_ggl_entries(seed_text)

    suffix = sync.find_suffix(sections, seed_sections)
    if not suffix:
        raise RuntimeError("Could not find the GGL keyboard suffix.")

    entries = sync.select_entries(sections, section, action_names, None)
    if cleanup_names is None:
        cleanup_names = {entry.name for entry in entries}
    seed_map = sync.map_seed_entries(seed_sections, section)
    plan_seed = f"{random_seed}|{section}" if random_seed else None
    effective_blocked_keys = set(blocked_keys)
    if extra_blocked_keys:
        effective_blocked_keys.update(extra_blocked_keys)
    if loader_context_sections is None:
        loader_context_sections = {section}
        if section != "General":
            loader_context_sections.add("General")
    addon_label = "BindPad" if macro_addon == "BindPad" else "Debounce"
    loader_reserved_keys = sync.collect_ggl_reserved_keys(sections, loader_context_sections, entries)
    effective_blocked_keys.update(loader_reserved_keys)
    class_file: str | None = None
    if macro_addon == "BindPad":
        spec_index = sync.bindpad_spec_index_for_section(section)
    else:
        class_file, spec_index = sync.section_to_debounce_target(section)
    planned_macro_names = {entry.name for entry in entries}
    if macro_overrides:
        planned_macro_names.update(override.name for override in macro_overrides.values() if override.name)
    if macro_addon == "BindPad":
        bindpad_text, _, _ = sync.read_text(addon_path)
        bindpad_vars = sync.parse_bindpad_vars(bindpad_text)
        if section != "General" and not bindpad_profile:
            raise RuntimeError("Choose a BindPad character/profile for class/spec binds.")
        effective_blocked_keys.update(
            sync.bindpad_reserved_keys(
                bindpad_vars,
                bindpad_profile,
                spec_index,
                planned_macro_names,
                layout,
            )
        )
    plans = sync.plan_bindings(
        entries,
        seed_map,
        suffix,
        overwrite_ggl,
        enabled_scans,
        plan_seed,
        enabled_mods,
        allow_unmodified,
        effective_blocked_keys,
        macro_overrides,
        layout=layout,
    )

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = reports_dir / f"wow_keybind_plan_{safe_name(section)}_{stamp}.csv"
    sync.write_report(report_path, plans, layout)

    assigned = sum(1 for plan in plans if plan.key)
    debounce_count = sum(1 for plan in plans if plan.key and plan.macro)
    warnings = [plan for plan in plans if plan.warning]

    lines = [
        f"{section}",
        f"  Loader binds: {assigned}/{len(plans)}",
        f"  {addon_label} macro binds: {debounce_count}",
        f"  Report: {report_path}",
    ]
    lines.append(f"  Keyboard layout: {layout.name}")
    if random_seed:
        lines.append(f"  Random layout seed: {random_seed}")
        if not overwrite_ggl:
            lines.append("  Existing loader hotkeys kept; randomized keys only fill open slots.")
    mods_label = ", ".join(mod.title() for mod in sync.MODIFIER_ORDER if mod in enabled_mods) or "none"
    lines.append(f"  Allowed modifiers: {mods_label}; unmodified keys: {'yes' if allow_unmodified else 'no'}")
    if blocked_keys:
        blocked_label = ", ".join(
            key.human(layout) for key in sorted(blocked_keys, key=lambda item: item.human(layout))
        )
        lines.append(f"  Reserved binds: {blocked_label}")
    if extra_blocked_keys:
        lines.append(f"  Keys reserved from earlier pass: {len(extra_blocked_keys)}")
    if loader_reserved_keys:
        lines.append(f"  Existing loader hotkeys reserved: {len(loader_reserved_keys)}")
    if macro_overrides:
        lines.append(f"  Custom pixels/macros: {len(macro_overrides)}")

    preview = plans[:10]
    for plan in preview:
        key = plan.key.human(layout) if plan.key else "NO KEY"
        destination = addon_label if plan.macro else "loader only"
        label = plan.action.name
        if plan.debounce_name and plan.debounce_name != plan.action.name:
            label = f"{plan.debounce_name} via {plan.action.name}"
        lines.append(f"  - {label}: {key} ({destination})")
    if len(plans) > len(preview):
        lines.append(f"  - ... {len(plans) - len(preview)} more")
    if warnings:
        lines.append(f"  Warnings: {len(warnings)}. See the report.")

    if apply:
        cleanup_keys = {plan.key.debounce(layout) for plan in plans if plan.key}
        addon_text, addon_encoding, _ = sync.read_text(addon_path)
        addon_backup = sync.backup_file(addon_path)
        ggl_backup = sync.backup_file(ggl_config)
        if macro_addon == "BindPad":
            vars_table = sync.parse_bindpad_vars(addon_text)
            sync.update_bindpad(
                vars_table,
                bindpad_profile,
                spec_index,
                plans,
                general=(section == "General"),
                cleanup_names=cleanup_names,
                cleanup_keys=cleanup_keys,
                layout=layout,
            )
            sync.write_text(addon_path, "BindPadVars = " + sync.dump_lua(vars_table) + "\n", addon_encoding)
        else:
            vars_table = sync.parse_debounce_vars(addon_text)
            if class_file is None:
                raise RuntimeError("Could not determine the Debounce class/spec target.")
            sync.update_debounce(
                vars_table,
                class_file,
                spec_index,
                plans,
                replace_managed=True,
                cleanup_names=cleanup_names,
                cleanup_keys=cleanup_keys,
                layout=layout,
            )
            sync.write_text(addon_path, "DebounceVars = " + sync.dump_lua(vars_table) + "\n", addon_encoding)

        cleanup_entries = [
            entry for entry in sections.get(section, []) if entry.name in cleanup_names
        ]
        new_lines = sync.rewrite_ggl_lines(ggl_lines, plans, overwrite_ggl, cleanup_entries)
        sync.write_text(ggl_config, ggl_newline.join(new_lines) + ggl_newline, ggl_encoding)

        lines.append("  Applied.")
        lines.append(f"  {addon_label} backup: {addon_backup}")
        lines.append(f"  Loader backup: {ggl_backup}")
    else:
        lines.append("  Preview only.")

    return "\n".join(lines), plans


class App(ctk.CTk):
    def __init__(self) -> None:
        self.settings = load_settings()
        set_app_theme(bool(self.settings.get("dark_mode", False)))
        ctk.set_appearance_mode("dark" if self.settings.get("dark_mode") else "light")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title("WoW Keybind Sync")
        self.geometry("980x720")
        self.minsize(760, 520)
        self.configure(bg=THEME["bg"])
        self._apply_theme()
        self.page_canvas: tk.Canvas | None = None
        self.page_scroll_exempt_widgets: set[tk.Widget] = set()
        self.action_search_text = ""
        self.action_search_time = 0.0
        self.last_log_text = ""
        self._save_job: str | None = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.dark_mode = tk.BooleanVar(value=bool(self.settings.get("dark_mode", False)))
        self.macro_addon = tk.StringVar(value=str(self.settings.get("macro_addon", "Debounce")))
        self.debounce_path = tk.StringVar(value=str(self.settings.get("debounce_path", "")))
        self.ggl_config = tk.StringVar(value=str(self.settings.get("ggl_config", "")))
        self.seed_config = tk.StringVar(value=str(self.settings.get("seed_config", "")))
        self.bindpad_profile = tk.StringVar(value=str(self.settings.get("bindpad_profile", "")))
        self.bindpad_profile_labels: dict[str, str] = {}
        self.section = tk.StringVar()
        saved_layout = sync.key_layout_from_id(str(self.settings.get("keyboard_layout", sync.DEFAULT_KEY_LAYOUT_ID)))
        self.keyboard_layout_display = tk.StringVar(value=saved_layout.name)
        self.global_binds = tk.BooleanVar(value=bool(self.settings.get("global_binds", True)))
        self.bind_all_sections = tk.BooleanVar(value=bool(self.settings.get("bind_all_sections", False)))
        self.overwrite_ggl = tk.BooleanVar(value=bool(self.settings.get("overwrite_ggl", False)))
        self.randomize = tk.BooleanVar(value=bool(self.settings.get("randomize", False)))
        self.random_seed = tk.StringVar(value=str(self.settings.get("random_seed") or sync.new_random_seed()))
        self.blocked_binds = tk.StringVar(value=str(self.settings.get("blocked_binds", "")))
        saved_mods = self.settings.get("enabled_mods")
        enabled_mods = (
            set(saved_mods)
            if isinstance(saved_mods, list)
            else set(sync.DEFAULT_ALLOWED_MODIFIERS)
        )
        self.mod_vars = {
            mod: tk.BooleanVar(value=(mod in enabled_mods))
            for mod in sync.MODIFIER_ORDER
        }
        self.allow_unmodified = tk.BooleanVar(value=bool(self.settings.get("allow_unmodified", True)))
        saved_key_ids = self.settings.get("enabled_key_ids")
        if isinstance(saved_key_ids, list):
            enabled_scans = sync.scans_from_saved_keys(saved_key_ids, saved_layout)
        elif isinstance(self.settings.get("enabled_keys"), list):
            enabled_scans = sync.scans_from_saved_keys(self.settings.get("enabled_keys"), sync.US_QWERTY_LAYOUT)
        else:
            enabled_scans = set(saved_layout.default_enabled_scans)
        self.key_vars = {
            sync.scan_id(scan): tk.BooleanVar(value=(scan in enabled_scans and saved_layout.supports_scan(scan)))
            for scan in sync.BASE_CANDIDATE_SCANS
        }
        self.key_checkboxes: dict[str, ctk.CTkCheckBox] = {}
        disabled_actions = self.settings.get("disabled_actions_by_section")
        self.disabled_actions_by_section: dict[str, set[str]] = {
            str(section): {str(action) for action in actions if str(action)}
            for section, actions in disabled_actions.items()
            if isinstance(actions, list)
        } if isinstance(disabled_actions, dict) else {}
        saved_custom_pixels = self.settings.get("custom_pixels")
        self.custom_pixels: list[dict[str, object]] = []
        if isinstance(saved_custom_pixels, list):
            for row in saved_custom_pixels:
                if not isinstance(row, dict):
                    continue
                section = str(row.get("section", "")).strip()
                loader_action = str(row.get("loader_action", "")).strip()
                macro_name = str(row.get("macro_name", "")).strip()
                macro_text = str(row.get("macro_text", "")).strip()
                if section and loader_action and macro_name:
                    self.custom_pixels.append(
                        {
                            "section": section,
                            "loader_action": loader_action,
                            "macro_name": macro_name,
                            "macro_text": macro_text,
                            "enabled": bool(row.get("enabled", True)),
                        }
                    )
        self.action_visible_names: list[str] = []
        self.custom_visible_indices: list[int] = []
        self.section_combos: list[tk.Widget] = []
        self.bindpad_profile_combos: list[tk.Widget] = []
        self.available_sections: list[str] = []
        self.action_names_by_section: dict[str, list[str]] = {}
        self.action_names_config_key = ""
        self.advanced_section_visible_sections: list[str] = []
        self.advanced_section_filter = tk.StringVar()
        self.advanced_section_display = tk.StringVar(value="No class/spec selected")
        self.express_sections: list[str] = []
        self.express_section_visible_sections: list[str] = []
        self.express_section_filter = tk.StringVar()
        self.express_section_display = tk.StringVar(value="No class/spec selected")
        self.express_seed: str | None = None
        self.custom_loader_action = tk.StringVar()
        self.custom_macro_name = tk.StringVar()
        self.custom_enabled = tk.BooleanVar(value=True)
        self.express_addon_status = tk.StringVar(value="Missing")
        self.express_config_status = tk.StringVar(value="Missing")
        self.express_profile_status = tk.StringVar(value="")
        self.express_section_status = tk.StringVar(value="Choose class/spec")
        self.express_ready_status = tk.StringVar(value="Choose files to begin.")
        self.express_global_status = tk.StringVar(value="Load Config.ini to check global binds.")
        self.express_global_missing = tk.StringVar(value="")
        self.express_custom_status = tk.StringVar(value="No custom macros imported.")
        self.advanced_section_filter.trace_add("write", lambda *_args: self.refresh_advanced_section_picker())
        self.express_section_filter.trace_add("write", lambda *_args: self.refresh_express_section_picker())

        self._build(lazy=True)
        for var in (
            self.macro_addon,
            self.debounce_path,
            self.ggl_config,
            self.bindpad_profile,
            self.section,
        ):
            var.trace_add("write", lambda *_args: self.refresh_express_status())
        self.reload_sections()
        self.after(500, self._prewarm_tabs)
        self.after(250, self.prompt_for_missing_paths)

    def _apply_theme(self) -> None:
        style = ttk.Style(self)
        for theme in ("vista", "xpnative", "default"):
            try:
                style.theme_use(theme)
                break
            except tk.TclError:
                continue

        style.configure(".", font=("Segoe UI", 10))
        style.configure("Root.TFrame", background=THEME["bg"])
        style.configure("TFrame", background=THEME["panel"])
        style.configure("Panel.TFrame", background=THEME["panel"])
        style.configure("Panel.TLabelframe", background=THEME["panel"])
        style.configure(
            "Panel.TLabelframe.Label",
            background=THEME["panel"],
            foreground=THEME["text"],
            font=("Segoe UI Semibold", 10),
        )
        style.configure("TLabel", background=THEME["panel"], foreground=THEME["text"])
        style.configure("Muted.TLabel", background=THEME["panel"], foreground=THEME["muted"])
        style.configure("Title.TLabel", background=THEME["panel_2"], foreground=THEME["text"], font=("Georgia", 19, "bold"))
        style.configure("Subtitle.TLabel", background=THEME["panel_2"], foreground=THEME["muted"], font=("Segoe UI", 10))
        style.configure("Accent.TButton", padding=(14, 7))
        style.configure("ExpressTitle.TLabel", background=THEME["panel"], foreground=THEME["text"], font=("Segoe UI Semibold", 14))
        style.configure("ExpressStep.TLabel", background=THEME["panel"], foreground=THEME["text"], font=("Segoe UI Semibold", 10))
        style.configure("ExpressStatus.TLabel", background=THEME["panel"], foreground=THEME["blue"], font=("Segoe UI Semibold", 10))
        style.configure("ExpressDanger.TLabel", background=THEME["panel"], foreground=THEME["danger"], font=("Segoe UI Semibold", 10))
        style.configure(
            "TCombobox",
            fieldbackground=THEME["field"],
            background=THEME["field"],
            foreground=THEME["text"],
            arrowcolor=THEME["text"],
            insertcolor=THEME["text"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", THEME["field"])],
            foreground=[("readonly", THEME["text"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=THEME["scrollbar"],
            troughcolor=THEME["bg"],
            arrowcolor=THEME["text"],
            bordercolor=THEME["gold_dark"],
        )
        self.option_add("*TCombobox*Listbox.background", THEME["field"])
        self.option_add("*TCombobox*Listbox.foreground", THEME["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", THEME["blue"])
        self.option_add("*TCombobox*Listbox.selectForeground", THEME["select_text"])

    def _build(self, active_tab: str | None = None, lazy: bool = True) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.clear_built_widget_refs()
        self.page_scroll_exempt_widgets = set()
        self.section_combos = []
        self.bindpad_profile_combos = []
        self.built_tabs: set[str] = set()

        shell = ctk.CTkFrame(self, fg_color=ctk_theme("bg"), corner_radius=0)
        self.shell = shell
        shell.pack(fill="both", expand=True)

        outer = PageScrollableFrame(
            shell,
            fg_color=ctk_theme("bg"),
            corner_radius=0,
            scrollbar_button_color=ctk_theme("scrollbar"),
            scrollbar_button_hover_color=ctk_theme("scrollbar_hover"),
        )
        self.page_scroll_frame = outer
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        header = ctk.CTkFrame(
            outer,
            fg_color=ctk_theme("field"),
            border_color=ctk_theme("gold_dark"),
            border_width=1,
            corner_radius=8,
        )
        header.pack(fill="x", pady=(0, 12))
        header_row = ctk.CTkFrame(header, fg_color="transparent")
        header_row.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(
            header_row,
            text="WoW Keybind Sync",
            text_color=ctk_theme("text"),
            font=("Georgia", 20, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True, anchor="w")
        ctk.CTkSwitch(
            header_row,
            text="Dark mode",
            variable=self.dark_mode,
            text_color=ctk_theme("text"),
            command=self.toggle_dark_mode,
        ).pack(side="right", padx=(12, 0))
        ctk.CTkLabel(
            header,
            text=f"Debounce + GGL Loader  |  v{APP_VERSION}",
            text_color=ctk_theme("muted"),
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", padx=17, pady=(0, 12), anchor="w")

        notebook = ctk.CTkTabview(
            outer,
            fg_color=ctk_theme("bg"),
            corner_radius=8,
            command=self.on_tab_changed,
        )
        self.notebook = notebook
        notebook.pack(fill="both", expand=True)
        self.express_tab = notebook.add("Express")
        self.advanced_tab = notebook.add("Advanced")
        target_tab = active_tab if active_tab in {"Express", "Advanced"} else "Express"
        self.select_tab(target_tab)
        if not lazy:
            for tab_name in ("Express", "Advanced"):
                self.build_tab_if_needed(tab_name)

    def clear_built_widget_refs(self) -> None:
        for name in (
            "macro_addon_combo",
            "bindpad_profile_combo",
            "advanced_section_search",
            "advanced_section_list_frame",
            "advanced_section_list",
            "action_list",
            "custom_loader_combo",
            "custom_macro_text",
            "custom_list",
            "log",
            "express_ready_label",
            "express_macro_addon_combo",
            "express_bindpad_profile_combo",
            "express_section_search",
            "express_section_list_frame",
            "express_section_list",
            "express_log",
        ):
            if hasattr(self, name):
                delattr(self, name)

    def on_tab_changed(self) -> None:
        if not hasattr(self, "notebook"):
            return
        self.build_tab_if_needed(self.notebook.get())

    def select_tab(self, tab_name: str) -> None:
        if not hasattr(self, "notebook"):
            return
        self.notebook.set(tab_name)
        self.build_tab_if_needed(tab_name)

    def build_tab_if_needed(self, tab_name: str) -> None:
        if tab_name in getattr(self, "built_tabs", set()):
            return
        if tab_name == "Express":
            self._build_express_tab(self.express_tab)
            self.refresh_express_section_picker()
            self.refresh_express_status()
        elif tab_name == "Advanced":
            self._build_advanced_tab(self.advanced_tab)
            self.apply_bindpad_profile_combo_cache()
            self.refresh_advanced_section_picker()
            self.refresh_action_list()
            self.refresh_custom_controls()
        else:
            return
        self.built_tabs.add(tab_name)

    def _prewarm_tabs(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.build_tab_if_needed("Advanced")

    def _widget_exists(self, name: str) -> tk.Widget | None:
        widget = getattr(self, name, None)
        if widget is None:
            return None
        try:
            if not widget.winfo_exists():
                return None
        except tk.TclError:
            return None
        return widget

    def _configure_classic_textlike(self, widget: tk.Widget | None) -> None:
        if widget is None:
            return
        options = {
            "bg": THEME["field"],
            "fg": THEME["text"],
            "insertbackground": THEME["text"],
            "selectbackground": THEME["blue"],
            "selectforeground": THEME["select_text"],
            "highlightbackground": THEME["gold_dark"],
            "highlightcolor": THEME["gold"],
        }
        for option, value in options.items():
            try:
                widget.configure(**{option: value})
            except tk.TclError:
                continue

    def _set_listbox_row_foregrounds(
        self,
        widget: tk.Widget | None,
        muted_indices: set[int] | None = None,
    ) -> None:
        if widget is None:
            return
        muted_indices = muted_indices or set()
        try:
            size = int(widget.size())
            state = str(widget.cget("state"))
        except tk.TclError:
            return
        try:
            if state == "disabled":
                widget.configure(state="normal")
            for index in range(size):
                foreground = THEME["muted"] if index in muted_indices else THEME["text"]
                widget.itemconfig(index, foreground=foreground)
        except tk.TclError:
            return
        finally:
            if state == "disabled":
                try:
                    widget.configure(state="disabled")
                except tk.TclError:
                    pass

    def _recolor_listbox_rows(self) -> None:
        advanced_muted = {0} if not self.advanced_section_visible_sections else set()
        self._set_listbox_row_foregrounds(self._widget_exists("advanced_section_list"), advanced_muted)

        express_muted = {0} if not self.express_section_visible_sections else set()
        self._set_listbox_row_foregrounds(self._widget_exists("express_section_list"), express_muted)

        section = self.section.get().strip()
        disabled = self.disabled_actions_by_section.get(section, set())
        action_muted = {
            index
            for index, name in enumerate(self.action_visible_names)
            if name in disabled
        }
        if not self.action_visible_names:
            action_muted.add(0)
        self._set_listbox_row_foregrounds(self._widget_exists("action_list"), action_muted)

        custom_muted = set()
        if not self.custom_visible_indices:
            custom_muted.add(0)
        else:
            for visible_index, row_index in enumerate(self.custom_visible_indices):
                try:
                    row = self.custom_pixels[row_index]
                except IndexError:
                    continue
                if not row.get("enabled", True):
                    custom_muted.add(visible_index)
        self._set_listbox_row_foregrounds(self._widget_exists("custom_list"), custom_muted)

    def apply_classic_widget_theme(self) -> None:
        for name in (
            "advanced_section_list",
            "action_list",
            "custom_list",
            "express_section_list",
        ):
            self._configure_classic_textlike(self._widget_exists(name))

        for name in ("custom_macro_text", "log"):
            self._configure_classic_textlike(self._widget_exists(name))

        self._recolor_listbox_rows()

    def toggle_dark_mode(self) -> None:
        dark_mode = self.dark_mode.get()
        set_app_theme(dark_mode)
        ctk.set_appearance_mode("dark" if dark_mode else "light")
        self._finish_theme_swap()

    def _finish_theme_swap(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.configure(bg=THEME["bg"])
        self._apply_theme()
        self.apply_classic_widget_theme()
        self.schedule_save_current_settings()

    def _build_advanced_tab(self, parent: tk.Widget) -> None:
        parent.configure(fg_color=ctk_theme("bg"))

        top_grid = ctk.CTkFrame(parent, fg_color="transparent")
        top_grid.pack(fill="x", padx=4, pady=(8, 10))
        top_grid.grid_columnconfigure(0, weight=1, uniform="advanced_top")
        top_grid.grid_columnconfigure(1, weight=1, uniform="advanced_top")

        files_card = self._ctk_grid_card(top_grid, "Files", 0, 0)
        target_card = self._ctk_grid_card(top_grid, "Bind Target", 0, 1)
        self._build_advanced_files_card(files_card)
        self._build_advanced_target_card(target_card)

        self._build_advanced_actions_card(self._ctk_card(parent, "Spell / Loader Actions"))
        self._build_advanced_custom_card(self._ctk_card(parent, "Custom Pixels / Macro Overrides"))
        self._build_advanced_key_rules_card(self._ctk_card(parent, "Key Rules"))
        self._build_advanced_run_card(self._ctk_card(parent, "Run"))
        self._build_advanced_result_card(self._ctk_card(parent, "Result"))

    def _ctk_grid_card(
        self,
        parent: tk.Widget,
        title: str,
        row: int,
        column: int,
        columnspan: int = 1,
    ) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent,
            fg_color=ctk_theme("field"),
            border_color=ctk_theme("gold_dark"),
            border_width=1,
            corner_radius=8,
        )
        frame.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=4, pady=0)
        ctk.CTkLabel(
            frame,
            text=title,
            text_color=ctk_theme("text"),
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=14, pady=(12, 10))
        return frame

    def _ctk_hint(
        self,
        parent: tk.Widget,
        text: str,
        row: int,
        column: int = 0,
        columnspan: int = 4,
        wraplength: int = 740,
    ) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=ctk_theme("muted"),
            anchor="w",
            justify="left",
            wraplength=wraplength,
        ).grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=14, pady=(8, 14))

    def _advanced_path_row(
        self,
        parent: tk.Widget,
        label: str,
        var: tk.StringVar,
        row: int,
    ) -> None:
        ctk.CTkLabel(parent, text=label, text_color=ctk_theme("text"), anchor="w").grid(
            row=row,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=4,
        )
        ctk.CTkEntry(parent, textvariable=var, height=32).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(0, 10),
            pady=4,
        )
        ctk.CTkButton(
            parent,
            text="Browse",
            width=86,
            height=32,
            corner_radius=8,
            command=lambda: self.browse(var),
        ).grid(row=row, column=2, sticky="e", padx=(0, 14), pady=4)
        parent.columnconfigure(1, weight=1)

    def _build_advanced_files_card(self, card: ctk.CTkFrame) -> None:
        ctk.CTkLabel(card, text="Bind addon", text_color=ctk_theme("text"), anchor="w").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=4,
        )
        self.macro_addon_combo = ctk.CTkComboBox(
            card,
            variable=self.macro_addon,
            values=["Debounce", "BindPad"],
            width=180,
            state="readonly",
            command=lambda _value: self.on_macro_addon_changed(),
        )
        self.macro_addon_combo.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=4)
        self._advanced_path_row(card, "Addon file", self.debounce_path, 2)
        self._advanced_path_row(card, "Config.ini", self.ggl_config, 3)
        self._advanced_path_row(card, "Seed config", self.seed_config, 4)

        ctk.CTkLabel(card, text="BindPad profile", text_color=ctk_theme("text"), anchor="w").grid(
            row=5,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=4,
        )
        self.bindpad_profile_combo = ctk.CTkComboBox(
            card,
            variable=self.bindpad_profile,
            values=[],
            width=320,
            state="readonly",
            command=lambda _value: self.save_current_settings(),
        )
        self.bindpad_profile_combo.grid(row=5, column=1, sticky="ew", padx=(0, 10), pady=4)
        self.bindpad_profile_combos.append(self.bindpad_profile_combo)
        self._ctk_hint(
            card,
            "Choose the WTF SavedVariables file. Seed config is optional and usually only useful when not randomizing.",
            6,
            wraplength=360,
        )

    def _build_advanced_target_card(self, card: ctk.CTkFrame) -> None:
        ctk.CTkLabel(card, text="Selected", text_color=ctk_theme("text"), anchor="w").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=4,
        )
        ctk.CTkLabel(
            card,
            textvariable=self.advanced_section_display,
            text_color=ctk_theme("text"),
            fg_color=ctk_theme("chip_bg"),
            corner_radius=8,
            padx=10,
            pady=5,
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=4)
        ctk.CTkButton(card, text="Reload", width=86, height=32, corner_radius=8, command=self.reload_sections).grid(
            row=1,
            column=2,
            sticky="e",
            padx=(0, 14),
            pady=4,
        )
        card.columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Search", text_color=ctk_theme("text"), anchor="w").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=4,
        )
        self.advanced_section_search = ctk.CTkEntry(
            card,
            textvariable=self.advanced_section_filter,
            placeholder_text="Type class or spec",
            height=32,
        )
        self.advanced_section_search.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=4)

        self.advanced_section_list_frame = ctk.CTkFrame(
            card,
            fg_color=ctk_theme("field"),
            border_color=ctk_theme("gold_dark"),
            border_width=1,
            corner_radius=8,
        )
        self.advanced_section_list_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=14, pady=(4, 8))
        self.advanced_section_list = tk.Listbox(
            self.advanced_section_list_frame,
            height=6,
            activestyle="none",
            bg=THEME["field"],
            fg=THEME["text"],
            selectbackground=THEME["blue"],
            selectforeground=THEME["select_text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False,
            font=("Segoe UI", 10),
        )
        advanced_section_scrollbar = ttk.Scrollbar(
            self.advanced_section_list_frame,
            command=self.advanced_section_list.yview,
            style="Vertical.TScrollbar",
        )
        self.advanced_section_list.configure(yscrollcommand=advanced_section_scrollbar.set)
        self.advanced_section_list.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        advanced_section_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 8), pady=8)
        self.advanced_section_list_frame.columnconfigure(0, weight=1)
        self.advanced_section_list_frame.rowconfigure(0, weight=1)
        self.advanced_section_list.bind("<<ListboxSelect>>", self.on_advanced_section_list_select)
        self.advanced_section_list.bind("<Double-Button-1>", self.on_advanced_section_list_activate)
        self.advanced_section_list.bind("<Return>", self.on_advanced_section_list_activate)
        self.advanced_section_list.bind("<MouseWheel>", self._on_inner_mousewheel)
        self.advanced_section_list.bind("<Button-4>", self._on_inner_scroll_button)
        self.advanced_section_list.bind("<Button-5>", self._on_inner_scroll_button)
        self.page_scroll_exempt_widgets.update({self.advanced_section_list, advanced_section_scrollbar})
        self.page_scroll_frame.add_nested_scroll_root(self.advanced_section_list)
        self.page_scroll_frame.add_nested_scroll_root(advanced_section_scrollbar)
        card.rowconfigure(3, weight=1)

        self._ctk_hint(
            card,
            "Type to filter. Advanced includes every Config.ini section.",
            4,
            columnspan=3,
            wraplength=360,
        )

        option_row = ctk.CTkFrame(card, fg_color="transparent")
        option_row.grid(row=5, column=0, columnspan=3, sticky="ew", padx=14, pady=(2, 0))
        ctk.CTkCheckBox(
            option_row,
            text="Bind all class/spec sections",
            variable=self.bind_all_sections,
            text_color=ctk_theme("text"),
            command=self.save_current_settings,
        ).pack(anchor="w", pady=(0, 6))
        ctk.CTkCheckBox(
            option_row,
            text="Global targeting / trinkets / potions",
            variable=self.global_binds,
            text_color=ctk_theme("text"),
            command=self.save_current_settings,
        ).pack(anchor="w", pady=(0, 6))
        ctk.CTkCheckBox(
            option_row,
            text="Replace loader hotkeys",
            variable=self.overwrite_ggl,
            text_color=ctk_theme("text"),
            command=self.save_current_settings,
        ).pack(anchor="w", pady=(0, 6))
        ctk.CTkCheckBox(
            option_row,
            text="Randomized layout",
            variable=self.randomize,
            text_color=ctk_theme("text"),
            command=self.save_current_settings,
        ).pack(anchor="w")

        seed_row = ctk.CTkFrame(card, fg_color="transparent")
        seed_row.grid(row=6, column=0, columnspan=3, sticky="ew", padx=14, pady=(12, 0))
        ctk.CTkLabel(seed_row, text="Seed", text_color=ctk_theme("text")).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(seed_row, textvariable=self.random_seed, width=150, height=32).pack(side="left")
        ctk.CTkButton(seed_row, text="New Seed", width=94, height=32, corner_radius=8, command=self.new_random_seed).pack(
            side="left",
            padx=(8, 0),
        )
        self._ctk_hint(
            card,
            "Use Replace when changing randomization, modifiers, keys, or reserved binds.",
            7,
            columnspan=3,
            wraplength=360,
        )

    def _build_advanced_actions_card(self, card: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            card,
            text="Turn off actions you do not want this spec to bind. Double-click an action, select several, or use Disable All to start from a blank slate.",
            text_color=ctk_theme("muted"),
            anchor="w",
            wraplength=780,
        ).grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 8))

        body = ctk.CTkFrame(card, fg_color=ctk_theme("field"), border_color=ctk_theme("gold_dark"), border_width=1, corner_radius=8)
        body.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=14, pady=(0, 10))
        self.action_list = tk.Listbox(
            body,
            height=10,
            selectmode="extended",
            activestyle="none",
            bg=THEME["field"],
            fg=THEME["text"],
            selectbackground=THEME["blue"],
            selectforeground=THEME["select_text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        action_scrollbar = ttk.Scrollbar(body, command=self.action_list.yview, style="Vertical.TScrollbar")
        self.action_list.configure(yscrollcommand=action_scrollbar.set)
        self.action_list.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        action_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 8), pady=8)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.page_scroll_exempt_widgets.update({self.action_list, action_scrollbar})
        self.page_scroll_frame.add_nested_scroll_root(self.action_list)
        self.action_list.bind("<MouseWheel>", self._on_inner_mousewheel)
        self.action_list.bind("<Button-4>", self._on_inner_scroll_button)
        self.action_list.bind("<Button-5>", self._on_inner_scroll_button)
        self.action_list.bind("<KeyPress>", self._on_action_list_keypress)
        self.action_list.bind("<Double-Button-1>", lambda _event: self.toggle_selected_actions())

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.grid(row=3, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 14))
        ctk.CTkButton(button_row, text="Toggle Selected", width=120, height=32, corner_radius=8, command=self.toggle_selected_actions).pack(side="left")
        ctk.CTkButton(
            button_row,
            text="Enable Selected",
            width=122,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.enable_selected_actions,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Disable Selected",
            width=124,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.disable_selected_actions,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Enable All",
            width=96,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.enable_all_actions,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Disable All",
            width=96,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.disable_all_actions,
        ).pack(side="left", padx=(8, 0))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)

    def _build_advanced_custom_card(self, card: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            card,
            text="Use this when a profile dev reuses a loader pixel for another spell or custom macro.",
            text_color=ctk_theme("muted"),
            anchor="w",
            wraplength=780,
        ).grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 8))

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 8))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        ctk.CTkLabel(form, text="Loader action", text_color=ctk_theme("text")).grid(row=0, column=0, sticky="w", pady=4)
        self.custom_loader_combo = ttk.Combobox(form, textvariable=self.custom_loader_action, width=34)
        self.custom_loader_combo.grid(row=0, column=1, sticky="ew", padx=(8, 14), pady=4)
        self.custom_loader_combo.bind("<KeyRelease>", self._on_custom_loader_keyrelease)
        ctk.CTkLabel(form, text="Macro name", text_color=ctk_theme("text")).grid(row=0, column=2, sticky="w", pady=4)
        ctk.CTkEntry(form, textvariable=self.custom_macro_name, height=32).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(8, 0),
            pady=4,
        )
        ctk.CTkCheckBox(
            form,
            text="Enabled",
            variable=self.custom_enabled,
            text_color=ctk_theme("text"),
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ctk.CTkLabel(form, text="Macro text", text_color=ctk_theme("text")).grid(row=2, column=0, sticky="nw", pady=(8, 0))
        self.custom_macro_text = tk.Text(
            form,
            height=4,
            wrap="word",
            bg=THEME["field"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            selectbackground=THEME["blue"],
            selectforeground=THEME["select_text"],
            relief="solid",
            bd=1,
            font=("Consolas", 10),
            padx=6,
            pady=5,
        )
        self.custom_macro_text.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        self.page_scroll_exempt_widgets.add(self.custom_macro_text)

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.grid(row=3, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 8))
        ctk.CTkButton(button_row, text="Add / Update", height=32, corner_radius=8, command=self.add_or_update_custom_pixel).pack(side="left")
        ctk.CTkButton(
            button_row,
            text="Remove Selected",
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.remove_selected_custom_pixel,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Clear Fields",
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.clear_custom_pixel_fields,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Import CSV",
            height=32,
            corner_radius=8,
            command=self.import_custom_macro_csv,
        ).pack(side="right")
        ctk.CTkButton(
            button_row,
            text="Save Template",
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.save_custom_macro_template,
        ).pack(side="right", padx=(0, 8))

        list_frame = ctk.CTkFrame(card, fg_color=ctk_theme("field"), border_color=ctk_theme("gold_dark"), border_width=1, corner_radius=8)
        list_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", padx=14, pady=(0, 14))
        self.custom_list = tk.Listbox(
            list_frame,
            height=4,
            activestyle="none",
            bg=THEME["field"],
            fg=THEME["text"],
            selectbackground=THEME["blue"],
            selectforeground=THEME["select_text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        custom_scrollbar = ttk.Scrollbar(list_frame, command=self.custom_list.yview, style="Vertical.TScrollbar")
        self.custom_list.configure(yscrollcommand=custom_scrollbar.set)
        self.custom_list.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        custom_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 8), pady=8)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.page_scroll_exempt_widgets.update({self.custom_list, custom_scrollbar})
        self.page_scroll_frame.add_nested_scroll_root(self.custom_list)
        self.custom_list.bind("<MouseWheel>", self._on_inner_mousewheel)
        self.custom_list.bind("<Button-4>", self._on_inner_scroll_button)
        self.custom_list.bind("<Button-5>", self._on_inner_scroll_button)
        self.custom_list.bind("<<ListboxSelect>>", lambda _event: self.load_selected_custom_pixel())
        card.columnconfigure(0, weight=1)

    def layout_display_names(self) -> list[str]:
        return [sync.KEY_LAYOUTS[layout_id].name for layout_id in sync.KEY_LAYOUT_ORDER]

    def keyboard_layout_id(self) -> str:
        selected = self.keyboard_layout_display.get().strip()
        for layout_id in sync.KEY_LAYOUT_ORDER:
            if sync.KEY_LAYOUTS[layout_id].name == selected:
                return layout_id
        return sync.DEFAULT_KEY_LAYOUT_ID

    def current_layout(self) -> sync.KeyLayout:
        return sync.key_layout_from_id(self.keyboard_layout_id())

    def on_keyboard_layout_changed(self, _value: str | None = None) -> None:
        layout = self.current_layout()
        unavailable: list[str] = []
        for scan_id, var in self.key_vars.items():
            scan = sync.scan_from_id(scan_id)
            if scan is None:
                continue
            if var.get() and not layout.supports_scan(scan):
                unavailable.append(sync.US_QWERTY_LAYOUT.label(scan))
                var.set(False)
        self.refresh_key_rule_labels()
        self.save_current_settings()
        if unavailable:
            self.write_log(
                "Keyboard layout changed. Disabled unavailable keys: "
                + ", ".join(sorted(unavailable))
            )

    def key_display_label(self, scan_code: int) -> str:
        layout = self.current_layout()
        base = layout.label(scan_code)
        numpad_labels = {
            "NUMPAD0": "Num 0",
            "NUMPAD1": "Num 1",
            "NUMPAD2": "Num 2",
            "NUMPAD3": "Num 3",
            "NUMPAD4": "Num 4",
            "NUMPAD5": "Num 5",
            "NUMPAD6": "Num 6",
            "NUMPAD7": "Num 7",
            "NUMPAD8": "Num 8",
            "NUMPAD9": "Num 9",
            "NUMPADPLUS": "Num +",
            "NUMPADMINUS": "Num -",
            "NUMPADMULTIPLY": "Num *",
            "NUMPADDIVIDE": "Num /",
            "NUMPADDECIMAL": "Num .",
        }
        return numpad_labels.get(base, base)

    def refresh_key_rule_labels(self) -> None:
        if not hasattr(self, "key_checkboxes"):
            return
        layout = self.current_layout()
        for scan_id, checkbox in self.key_checkboxes.items():
            scan = sync.scan_from_id(scan_id)
            if scan is None:
                continue
            enabled = layout.supports_scan(scan)
            if not enabled:
                self.key_vars[scan_id].set(False)
            checkbox.configure(
                text=self.key_display_label(scan),
                state="normal" if enabled else "disabled",
                text_color=ctk_theme("text") if enabled else ctk_theme("muted"),
            )

    def _build_advanced_key_rules_card(self, card: ctk.CTkFrame) -> None:
        rules = ctk.CTkFrame(card, fg_color="transparent")
        rules.grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 14))
        rules.grid_columnconfigure(0, weight=1)
        rules.grid_columnconfigure(1, weight=2)

        modifier_frame = ctk.CTkFrame(rules, fg_color="transparent")
        modifier_frame.grid(row=0, column=0, sticky="new", padx=(0, 16))
        ctk.CTkLabel(
            modifier_frame,
            text="Keyboard layout",
            text_color=ctk_theme("text"),
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).pack(fill="x")
        ctk.CTkOptionMenu(
            modifier_frame,
            variable=self.keyboard_layout_display,
            values=self.layout_display_names(),
            command=self.on_keyboard_layout_changed,
            width=220,
            height=32,
        ).pack(fill="x", pady=(8, 12))
        ctk.CTkLabel(
            modifier_frame,
            text="Modifiers",
            text_color=ctk_theme("text"),
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).pack(fill="x")
        mod_row = ctk.CTkFrame(modifier_frame, fg_color="transparent")
        mod_row.pack(fill="x", pady=(8, 0))
        for index, mod in enumerate(sync.MODIFIER_ORDER):
            ctk.CTkCheckBox(
                mod_row,
                text=mod.title(),
                variable=self.mod_vars[mod],
                text_color=ctk_theme("text"),
                command=self.save_current_settings,
                width=70,
            ).grid(row=0, column=index, sticky="w", padx=(0, 8), pady=(0, 6))
        ctk.CTkCheckBox(
            mod_row,
            text="No modifier",
            variable=self.allow_unmodified,
            text_color=ctk_theme("text"),
            command=self.save_current_settings,
            width=110,
        ).grid(row=1, column=0, columnspan=3, sticky="w")
        ctk.CTkLabel(modifier_frame, text="Reserved binds", text_color=ctk_theme("text"), anchor="w").pack(fill="x", pady=(12, 4))
        reserved_row = ctk.CTkFrame(modifier_frame, fg_color="transparent")
        reserved_row.pack(fill="x")
        ctk.CTkEntry(reserved_row, textvariable=self.blocked_binds, height=32).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(reserved_row, text="Save", width=70, height=32, corner_radius=8, command=self.save_current_settings).pack(
            side="left",
            padx=(8, 0),
        )
        ctk.CTkLabel(
            modifier_frame,
            text="Use reserved binds for overlays, recording tools, or awkward keys.",
            text_color=ctk_theme("muted"),
            anchor="w",
            justify="left",
            wraplength=360,
        ).pack(fill="x", pady=(8, 0))

        key_frame = ctk.CTkFrame(rules, fg_color="transparent")
        key_frame.grid(row=0, column=1, sticky="new")
        key_columns = 5
        ctk.CTkLabel(
            key_frame,
            text="Allowed Keyboard Keys",
            text_color=ctk_theme("text"),
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).grid(row=0, column=0, columnspan=key_columns, sticky="ew", pady=(0, 8))
        self.key_checkboxes = {}
        layout = self.current_layout()
        for index, scan in enumerate(sync.BASE_CANDIDATE_SCANS):
            row = 1 + index // key_columns
            col = index % key_columns
            scan_id = sync.scan_id(scan)
            state = "normal" if layout.supports_scan(scan) else "disabled"
            checkbox = ctk.CTkCheckBox(
                key_frame,
                text=self.key_display_label(scan),
                variable=self.key_vars[scan_id],
                state=state,
                text_color=ctk_theme("muted") if state == "disabled" else ctk_theme("text"),
                command=self.save_current_settings,
                width=76,
            )
            checkbox.grid(row=row, column=col, sticky="w", padx=(0, 8), pady=3)
            self.key_checkboxes[scan_id] = checkbox
        key_button_row = 1 + ((len(sync.BASE_CANDIDATE_SCANS) + key_columns - 1) // key_columns)
        button_row = ctk.CTkFrame(key_frame, fg_color="transparent")
        button_row.grid(row=key_button_row, column=0, columnspan=key_columns, sticky="ew", pady=(8, 0))
        ctk.CTkButton(button_row, text="Safe Defaults", width=110, height=32, corner_radius=8, command=self.select_default_keys).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(0, 6),
        )
        ctk.CTkButton(
            button_row,
            text="All Safe",
            width=86,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.select_all_safe_keys,
        ).grid(row=0, column=1, sticky="w", padx=(0, 8), pady=(0, 6))
        ctk.CTkButton(
            button_row,
            text="Disable F Keys",
            width=118,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.disable_function_keys,
        ).grid(row=0, column=2, sticky="w", pady=(0, 6))
        ctk.CTkButton(
            button_row,
            text="Enable F Keys",
            width=112,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.enable_function_keys,
        ).grid(row=1, column=0, sticky="w", padx=(0, 8))
        ctk.CTkButton(
            button_row,
            text="Clear",
            width=70,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.clear_keys,
        ).grid(row=1, column=1, sticky="w")
        numpad_row = ctk.CTkFrame(key_frame, fg_color="transparent")
        numpad_row.grid(row=key_button_row + 1, column=0, columnspan=key_columns, sticky="ew", pady=(8, 0))
        ctk.CTkButton(numpad_row, text="Enable Numpad", width=124, height=32, corner_radius=8, command=self.enable_numpad_keys).pack(side="left")
        ctk.CTkButton(
            numpad_row,
            text="Disable Numpad",
            width=128,
            height=32,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.disable_numpad_keys,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(
            key_frame,
            text="Numpad is optional because Num Lock and compact keyboards can behave differently.",
            text_color=ctk_theme("muted"),
            anchor="w",
            justify="left",
            wraplength=520,
        ).grid(row=key_button_row + 2, column=0, columnspan=key_columns, sticky="ew", pady=(8, 0))

    def _build_advanced_run_card(self, card: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            card,
            text="Preview creates a report only. Apply writes backups first. Close WoW and the loader before Apply.",
            text_color=ctk_theme("muted"),
            anchor="w",
            wraplength=760,
        ).grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 10))
        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 8))
        ctk.CTkButton(
            button_row,
            text="Check Setup",
            width=110,
            height=34,
            corner_radius=8,
            command=self.run_preflight_check,
        ).pack(side="left")
        ctk.CTkButton(button_row, text="Preview", width=92, height=34, corner_radius=8, command=lambda: self.run(False)).pack(side="left", padx=(8, 0))
        ctk.CTkButton(button_row, text="Apply", width=86, height=34, corner_radius=8, command=lambda: self.run(True)).pack(
            side="left",
            padx=(8, 0),
        )
        ctk.CTkButton(
            button_row,
            text="Remove Old Debounce Binds",
            width=190,
            height=34,
            corner_radius=8,
            fg_color=ctk_theme("danger_bg"),
            hover_color=ctk_theme("danger_hover"),
            text_color=ctk_theme("danger"),
            command=self.remove_old_debounce_binds,
        ).pack(side="left", padx=(8, 0))
        support_row = ctk.CTkFrame(card, fg_color="transparent")
        support_row.grid(row=3, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 14))
        ctk.CTkButton(
            support_row,
            text="Backup Manager",
            width=132,
            height=34,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.open_backup_manager,
        ).pack(side="left")
        ctk.CTkButton(
            support_row,
            text="Export Bug Report",
            width=142,
            height=34,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.export_bug_report,
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            support_row,
            text="Open Reports Folder",
            width=148,
            height=34,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
            command=self.open_reports,
        ).pack(side="right")

    def _build_advanced_result_card(self, card: ctk.CTkFrame) -> None:
        self.log = tk.Text(
            card,
            wrap="word",
            height=14,
            bg=THEME["field"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            selectbackground=THEME["blue"],
            selectforeground=THEME["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=THEME["gold_dark"],
            highlightcolor=THEME["gold"],
            font=("Consolas", 10),
            padx=10,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(card, command=self.log.yview, style="Vertical.TScrollbar")
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.grid(row=1, column=0, sticky="nsew", padx=(14, 0), pady=(0, 14))
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(2, 14), pady=(0, 14))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)
        self.page_scroll_exempt_widgets.update({self.log, scrollbar})

    def _build_express_tab(self, parent: tk.Widget) -> None:
        parent.configure(fg_color=ctk_theme("bg"))

        intro = ctk.CTkFrame(parent, fg_color=ctk_theme("field"), border_color=ctk_theme("gold_dark"), border_width=1, corner_radius=8)
        intro.pack(fill="x", padx=4, pady=(8, 10))
        title_row = ctk.CTkFrame(intro, fg_color="transparent")
        title_row.pack(fill="x", padx=14, pady=(14, 0))
        ctk.CTkLabel(
            title_row,
            text="Express setup",
            text_color=ctk_theme("text"),
            font=("Segoe UI Semibold", 18),
            anchor="w",
        ).pack(side="left")
        self.express_ready_label = ctk.CTkLabel(
            title_row,
            textvariable=self.express_ready_status,
            text_color=ctk_theme("danger"),
            fg_color=ctk_theme("danger_bg"),
            corner_radius=8,
            padx=10,
            pady=4,
        )
        self.express_ready_label.pack(side="right")
        ctk.CTkLabel(
            intro,
            text="Auto-detect files, choose a class/spec, preview, then apply.",
            text_color=ctk_theme("muted"),
            anchor="w",
            wraplength=760,
        ).pack(fill="x", padx=14, pady=(4, 0))
        defaults = ctk.CTkFrame(intro, fg_color="transparent")
        defaults.pack(fill="x", padx=14, pady=(10, 14))
        for text in ("Safe defaults", "Randomized keys", "Backups before writes"):
            ctk.CTkLabel(
                defaults,
                text=text,
                text_color=ctk_theme("muted"),
                fg_color=ctk_theme("chip_bg"),
                corner_radius=8,
                padx=10,
                pady=4,
            ).pack(side="left", padx=(0, 8))

        files = self._ctk_card(parent, "1. Files")
        detect_row = ctk.CTkFrame(files, fg_color="transparent")
        detect_row.grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 10))
        ctk.CTkButton(
            detect_row,
            text="Auto Detect Files",
            command=self.auto_detect_express_paths,
            height=36,
            corner_radius=8,
        ).pack(side="left")
        ctk.CTkLabel(
            detect_row,
            text="Best first step for most users.",
            text_color=ctk_theme("muted"),
        ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(files, text="Bind addon", text_color=ctk_theme("text")).grid(row=2, column=0, sticky="w", padx=(14, 8), pady=4)
        self.express_macro_addon_combo = ctk.CTkComboBox(
            files,
            variable=self.macro_addon,
            values=["Debounce", "BindPad"],
            width=180,
            state="readonly",
            command=lambda _value: self.on_macro_addon_changed(),
        )
        self.express_macro_addon_combo.grid(row=2, column=1, sticky="w", padx=(0, 10), pady=4)
        self._express_path_row(files, "Addon file", self.debounce_path, 3, self.express_addon_status)
        self._express_path_row(files, "Config.ini", self.ggl_config, 4, self.express_config_status)
        ctk.CTkLabel(files, text="BindPad profile", text_color=ctk_theme("text")).grid(row=5, column=0, sticky="w", padx=(14, 8), pady=4)
        self.express_bindpad_profile_combo = ctk.CTkComboBox(
            files,
            variable=self.bindpad_profile,
            values=[],
            width=320,
            state="disabled",
            command=lambda _value: self.save_current_settings(),
        )
        self.express_bindpad_profile_combo.grid(row=5, column=1, sticky="ew", padx=(0, 10), pady=4)
        self.bindpad_profile_combos.append(self.express_bindpad_profile_combo)
        ctk.CTkLabel(files, textvariable=self.express_profile_status, text_color=ctk_theme("muted"), width=140, anchor="w").grid(
            row=5,
            column=3,
            sticky="w",
            padx=(0, 14),
            pady=4,
        )
        ctk.CTkLabel(files, text="Keyboard layout", text_color=ctk_theme("text")).grid(
            row=6,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=4,
        )
        ctk.CTkOptionMenu(
            files,
            variable=self.keyboard_layout_display,
            values=self.layout_display_names(),
            command=self.on_keyboard_layout_changed,
            width=220,
            height=32,
        ).grid(row=6, column=1, sticky="w", padx=(0, 10), pady=4)
        ctk.CTkLabel(
            files,
            text="Use International Safe if your keyboard layout is not listed.",
            text_color=ctk_theme("muted"),
            anchor="w",
        ).grid(row=6, column=2, columnspan=2, sticky="w", padx=(0, 14), pady=4)
        ctk.CTkLabel(
            files,
            text="Examples are shown in Browse. Choose the WTF SavedVariables file, not the AddOns folder.",
            text_color=ctk_theme("muted"),
            anchor="w",
            wraplength=760,
        ).grid(row=7, column=0, columnspan=4, sticky="ew", padx=14, pady=(8, 14))
        files.columnconfigure(1, weight=1)

        target = self._ctk_card(parent, "2. Character")
        ctk.CTkLabel(target, text="Selected", text_color=ctk_theme("text")).grid(
            row=1,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=(0, 8),
        )
        ctk.CTkLabel(
            target,
            textvariable=self.express_section_display,
            text_color=ctk_theme("text"),
            fg_color=ctk_theme("chip_bg"),
            corner_radius=8,
            padx=10,
            pady=5,
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))
        ctk.CTkButton(target, text="Reload", width=90, command=self.reload_sections, corner_radius=8).grid(
            row=1,
            column=2,
            sticky="e",
            padx=(0, 10),
            pady=(0, 8),
        )
        ctk.CTkLabel(target, textvariable=self.express_section_status, text_color=ctk_theme("muted"), width=130, anchor="w").grid(
            row=1,
            column=3,
            sticky="w",
            padx=(0, 14),
            pady=(0, 8),
        )
        ctk.CTkLabel(target, text="Search", text_color=ctk_theme("text")).grid(
            row=2,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=(0, 8),
        )
        self.express_section_search = ctk.CTkEntry(
            target,
            textvariable=self.express_section_filter,
            placeholder_text="Type class or spec",
            height=32,
        )
        self.express_section_search.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(0, 14), pady=(0, 8))
        self.express_section_list_frame = ctk.CTkFrame(
            target,
            fg_color=ctk_theme("field"),
            border_color=ctk_theme("gold_dark"),
            border_width=1,
            corner_radius=8,
        )
        self.express_section_list_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=14, pady=(0, 14))
        self.express_section_list = tk.Listbox(
            self.express_section_list_frame,
            height=8,
            activestyle="none",
            bg=THEME["field"],
            fg=THEME["text"],
            selectbackground=THEME["blue"],
            selectforeground=THEME["select_text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False,
            font=("Segoe UI", 10),
        )
        section_scrollbar = ttk.Scrollbar(
            self.express_section_list_frame,
            command=self.express_section_list.yview,
            style="Vertical.TScrollbar",
        )
        self.express_section_list.configure(yscrollcommand=section_scrollbar.set)
        self.express_section_list.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        section_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 8), pady=8)
        self.express_section_list_frame.columnconfigure(0, weight=1)
        self.express_section_list_frame.rowconfigure(0, weight=1)
        self.express_section_list.bind("<<ListboxSelect>>", self.on_express_section_list_select)
        self.express_section_list.bind("<Double-Button-1>", self.on_express_section_list_activate)
        self.express_section_list.bind("<Return>", self.on_express_section_list_activate)
        self.express_section_list.bind("<MouseWheel>", self._on_inner_mousewheel)
        self.express_section_list.bind("<Button-4>", self._on_inner_scroll_button)
        self.express_section_list.bind("<Button-5>", self._on_inner_scroll_button)
        self.page_scroll_exempt_widgets.update({self.express_section_list, section_scrollbar})
        self.page_scroll_frame.add_nested_scroll_root(self.express_section_list)
        self.page_scroll_frame.add_nested_scroll_root(section_scrollbar)
        target.rowconfigure(3, weight=1)
        target.columnconfigure(1, weight=1)
        ctk.CTkLabel(
            target,
            text="Use search if the list is long.",
            text_color=ctk_theme("muted"),
            anchor="w",
        ).grid(
            row=4,
            column=0,
            columnspan=4,
            sticky="ew",
            padx=14,
            pady=(0, 14),
        )

        custom_frame = self._ctk_card(parent, "3. Custom Macros")
        custom_row = ctk.CTkFrame(custom_frame, fg_color="transparent")
        custom_row.grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 10))
        ctk.CTkButton(
            custom_row,
            text="Import Macro CSV",
            command=self.import_custom_macro_csv,
            height=36,
            corner_radius=8,
        ).pack(side="left")
        ctk.CTkButton(
            custom_row,
            text="Save Template",
            command=self.save_custom_macro_template,
            height=36,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
        ).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(
            custom_row,
            textvariable=self.express_custom_status,
            text_color=ctk_theme("muted"),
            anchor="w",
        ).pack(side="left", padx=(12, 0))
        ctk.CTkLabel(
            custom_frame,
            text="Optional. Use this when a profile dev provides custom macro mappings.",
            text_color=ctk_theme("muted"),
            anchor="w",
            wraplength=760,
        ).grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 14))

        run_frame = self._ctk_card(parent, "4. Run")
        button_row = ctk.CTkFrame(run_frame, fg_color="transparent")
        button_row.grid(row=1, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 8))
        ctk.CTkButton(
            button_row,
            text="Check Setup",
            command=self.run_express_preflight_check,
            height=36,
            corner_radius=8,
        ).pack(side="left")
        ctk.CTkButton(button_row, text="Preview EZ Setup", command=lambda: self.run_express(False), height=36, corner_radius=8).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Apply EZ Setup",
            command=lambda: self.run_express(True),
            height=36,
            corner_radius=8,
        ).pack(side="left", padx=(8, 0))
        support_row = ctk.CTkFrame(run_frame, fg_color="transparent")
        support_row.grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 8))
        ctk.CTkButton(
            support_row,
            text="Backup Manager",
            command=self.open_backup_manager,
            height=36,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
        ).pack(side="left")
        ctk.CTkButton(
            support_row,
            text="Export Bug Report",
            command=self.export_bug_report,
            height=36,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            support_row,
            text="Open Reports Folder",
            command=self.open_reports,
            height=36,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
        ).pack(side="right")
        ctk.CTkLabel(
            run_frame,
            text="Preview first. Close WoW and the loader before Apply.",
            text_color=ctk_theme("muted"),
            anchor="w",
        ).grid(row=3, column=0, columnspan=4, sticky="ew", padx=14, pady=(0, 14))

        log_frame = self._ctk_card(parent, "Result")
        self.express_log = ctk.CTkTextbox(
            log_frame,
            height=150,
            wrap="word",
            fg_color=ctk_theme("field"),
            text_color=ctk_theme("text"),
            border_color=ctk_theme("gold_dark"),
            border_width=1,
            corner_radius=8,
            font=("Consolas", 10),
        )
        self.express_log.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.express_log.configure(state="disabled")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        self.page_scroll_exempt_widgets.add(self.express_log)
        self.refresh_express_status()

    def _ctk_card(self, parent: tk.Widget, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent,
            fg_color=ctk_theme("field"),
            border_color=ctk_theme("gold_dark"),
            border_width=1,
            corner_radius=8,
        )
        frame.pack(fill="x", padx=4, pady=(0, 10))
        ctk.CTkLabel(
            frame,
            text=title,
            text_color=ctk_theme("text"),
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=14, pady=(12, 10))
        return frame

    def express_playable_sections(self, sections: list[str]) -> list[str]:
        return [section for section in sections if section and section != "General"]

    def set_advanced_sections(self, sections: list[str]) -> None:
        self.available_sections = list(sections)
        self.refresh_advanced_section_picker()

    def set_express_sections(self, sections: list[str]) -> None:
        self.available_sections = list(sections)
        self.express_sections = self.express_playable_sections(sections)
        self.refresh_express_section_picker()

    def choose_advanced_section(self, section: str) -> None:
        if section not in self.available_sections:
            return
        self.section.set(section)
        self.on_section_changed()
        self.save_current_settings()

    def on_advanced_section_list_select(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "advanced_section_list"):
            return
        selection = self.advanced_section_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self.advanced_section_visible_sections):
            return
        self.choose_advanced_section(self.advanced_section_visible_sections[index])

    def on_advanced_section_list_activate(self, _event: tk.Event | None = None) -> str:
        self.on_advanced_section_list_select()
        return "break"

    def refresh_advanced_section_picker(self) -> None:
        if not hasattr(self, "advanced_section_list"):
            return

        query = self.advanced_section_filter.get().strip().lower()
        sections = [
            section
            for section in self.available_sections
            if not query or query in section.lower()
        ]
        self.advanced_section_visible_sections = sections
        current = self.section.get().strip()
        if current in self.available_sections:
            self.advanced_section_display.set(current)
        else:
            self.advanced_section_display.set("No class/spec selected")

        self.advanced_section_list.configure(state="normal")
        self.advanced_section_list.delete(0, "end")
        if not sections:
            message = "No matches. Try the class or spec name." if self.available_sections else "Load Config.ini to show class/specs."
            self.advanced_section_list.insert("end", message)
            self.advanced_section_list.itemconfig(0, foreground=THEME["muted"])
            self.advanced_section_list.configure(state="disabled")
            return

        for section in sections:
            self.advanced_section_list.insert("end", section)
        if current in sections:
            index = sections.index(current)
            self.advanced_section_list.selection_set(index)
            self.advanced_section_list.activate(index)
            self.advanced_section_list.see(index)

    def choose_express_section(self, section: str) -> None:
        if section not in self.express_sections:
            return
        self.section.set(section)
        self.on_section_changed()
        self.save_current_settings()

    def on_express_section_list_select(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "express_section_list"):
            return
        selection = self.express_section_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self.express_section_visible_sections):
            return
        self.choose_express_section(self.express_section_visible_sections[index])

    def on_express_section_list_activate(self, _event: tk.Event | None = None) -> str:
        self.on_express_section_list_select()
        return "break"

    def refresh_express_section_picker(self) -> None:
        if not hasattr(self, "express_section_list"):
            return

        query = self.express_section_filter.get().strip().lower()
        sections = [
            section
            for section in self.express_sections
            if not query or query in section.lower()
        ]
        self.express_section_visible_sections = sections
        current = self.section.get().strip()
        if current in self.express_sections:
            self.express_section_display.set(current)
        else:
            self.express_section_display.set("No class/spec selected")

        self.express_section_list.configure(state="normal")
        self.express_section_list.delete(0, "end")
        if not sections:
            message = "No matches. Try the class or spec name." if self.express_sections else "Load Config.ini to show class/specs."
            self.express_section_list.insert("end", message)
            self.express_section_list.itemconfig(0, foreground=THEME["muted"])
            self.express_section_list.configure(state="disabled")
            return

        for section in sections:
            self.express_section_list.insert("end", section)
        if current in sections:
            index = sections.index(current)
            self.express_section_list.selection_set(index)
            self.express_section_list.activate(index)
            self.express_section_list.see(index)

    def _on_inner_mousewheel(self, event: tk.Event) -> str:
        steps = int(-1 * (event.delta / 120)) * INNER_SCROLL_UNITS
        if steps and self._inner_widget_can_scroll(event.widget, steps):
            event.widget.yview_scroll(steps, "units")
        elif hasattr(self, "page_scroll_frame"):
            self.page_scroll_frame.scroll_from_wheel_event(event)
        return "break"

    def _on_inner_scroll_button(self, event: tk.Event) -> str:
        direction = -INNER_SCROLL_UNITS if getattr(event, "num", 0) == 4 else INNER_SCROLL_UNITS
        if self._inner_widget_can_scroll(event.widget, direction):
            event.widget.yview_scroll(direction, "units")
        elif hasattr(self, "page_scroll_frame"):
            self.page_scroll_frame.scroll_units(direction * 20 * PAGE_SCROLL_MULTIPLIER)
        return "break"

    def _inner_widget_can_scroll(self, widget: tk.Widget, steps: int) -> bool:
        if not steps:
            return False
        try:
            first, last = widget.yview()
        except tk.TclError:
            return False
        if first <= 0.0 and last >= 1.0:
            return False
        if steps < 0:
            return first > 0.001
        return last < 0.999

    def _is_page_scroll_exempt(self, widget: tk.Widget) -> bool:
        try:
            if widget.winfo_toplevel() is not self:
                return True
        except tk.TclError:
            return True

        while widget is not None:
            if widget in self.page_scroll_exempt_widgets:
                return True
            try:
                widget_class = widget.winfo_class()
            except tk.TclError:
                return True
            if widget_class in {"TCombobox", "Listbox", "ComboboxPopdownFrame"}:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _on_page_mousewheel(self, event: tk.Event) -> str | None:
        if not self.page_canvas:
            return
        if self._is_page_scroll_exempt(event.widget):
            return None
        steps = int(-1 * (event.delta / 120))
        if steps:
            self.page_canvas.yview_scroll(steps, "units")
        return None

    def _action_match_index(self, query: str, names: list[str] | tuple[str, ...] | None = None) -> int | None:
        needle = query.strip().lower()
        if not needle:
            return None
        candidates = list(names if names is not None else self.action_visible_names)
        for index, name in enumerate(candidates):
            if str(name).lower().startswith(needle):
                return index
        for index, name in enumerate(candidates):
            if needle in str(name).lower():
                return index
        return None

    def _select_action_index(self, index: int) -> None:
        self.action_list.selection_clear(0, "end")
        self.action_list.selection_set(index)
        self.action_list.activate(index)
        self.action_list.see(index)

    def _on_action_list_keypress(self, event: tk.Event) -> str | None:
        keysym = getattr(event, "keysym", "")
        if keysym in {"Escape", "Return", "Tab", "Up", "Down", "Prior", "Next", "Home", "End"}:
            if keysym == "Escape":
                self.action_search_text = ""
                self.action_search_time = 0.0
                return "break"
            return None
        if keysym == "BackSpace":
            self.action_search_text = self.action_search_text[:-1]
        else:
            char = getattr(event, "char", "")
            if not char or not char.isprintable():
                return None
            now = time.monotonic()
            if now - self.action_search_time > 1.25:
                self.action_search_text = ""
            self.action_search_text += char
            self.action_search_time = now

        index = self._action_match_index(self.action_search_text)
        if index is not None:
            self._select_action_index(index)
        return "break"

    def _on_custom_loader_keyrelease(self, event: tk.Event) -> None:
        keysym = getattr(event, "keysym", "")
        if keysym in {"Escape", "Return", "Tab", "Up", "Down", "Left", "Right", "Home", "End"}:
            return
        typed = self.custom_loader_action.get()
        if not typed.strip():
            return
        values = tuple(str(value) for value in self.custom_loader_combo.cget("values"))
        index = self._action_match_index(typed, values)
        if index is None:
            return
        match = values[index]
        if match == typed:
            return

        lower_match = match.lower()
        lower_typed = typed.lower()
        start = lower_match.find(lower_typed)
        cursor = (start + len(typed)) if start >= 0 else len(typed)
        self.custom_loader_action.set(match)
        try:
            self.custom_loader_combo.icursor(cursor)
            self.custom_loader_combo.selection_range(cursor, "end")
        except tk.TclError:
            pass

    def _path_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=(10, 10), pady=3)
        ttk.Button(parent, text="Browse", command=lambda: self.browse(var)).grid(row=row, column=2, pady=3)
        parent.columnconfigure(1, weight=1)

    def _express_path_row(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.StringVar,
        row: int,
        status_var: tk.StringVar,
    ) -> None:
        ctk.CTkLabel(parent, text=label, text_color=ctk_theme("text")).grid(
            row=row,
            column=0,
            sticky="w",
            padx=(14, 8),
            pady=4,
        )
        ctk.CTkEntry(parent, textvariable=var, height=32).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(0, 10),
            pady=4,
        )
        ctk.CTkButton(parent, text="Browse", width=90, height=32, command=lambda: self.browse(var), corner_radius=8).grid(
            row=row,
            column=2,
            pady=4,
            padx=(0, 10),
        )
        ctk.CTkLabel(parent, textvariable=status_var, text_color=ctk_theme("muted"), width=140, anchor="w").grid(
            row=row,
            column=3,
            sticky="w",
            padx=(0, 14),
            pady=4,
        )
        parent.columnconfigure(1, weight=1)

    def _set_status_label(self, label: tk.Widget, ok: bool) -> None:
        if isinstance(label, ctk.CTkLabel):
            label.configure(
                text_color=ctk_theme("blue") if ok else ctk_theme("danger"),
                fg_color=ctk_theme("ok_bg") if ok else ctk_theme("danger_bg"),
            )
        else:
            label.configure(style="ExpressStatus.TLabel" if ok else "ExpressDanger.TLabel")

    def refresh_express_status(self) -> None:
        if not hasattr(self, "express_ready_label"):
            return

        addon_name = "BindPad" if self.macro_addon.get() == "BindPad" else "Debounce"
        addon_raw = self.debounce_path.get().strip().strip('"')
        config_raw = self.ggl_config.get().strip().strip('"')
        section = self.section.get().strip()
        profile = self.bindpad_profile.get().strip()

        addon_ok = bool(addon_raw) and Path(addon_raw).exists()
        config_ok = bool(config_raw) and Path(config_raw).exists()
        section_ok = bool(section and section != "General")
        profile_ok = addon_name != "BindPad" or bool(profile)

        self.express_addon_status.set("File found" if addon_ok else f"{addon_name} file missing")
        self.express_config_status.set("File found" if config_ok else "Config missing")
        self.express_section_status.set("Selected" if section_ok else "Choose class/spec")
        if hasattr(self, "express_section_display"):
            self.express_section_display.set(section if section_ok else "No class/spec selected")
        self.express_profile_status.set(
            "Selected" if addon_name == "BindPad" and profile_ok else ("Choose profile" if addon_name == "BindPad" else "Not needed")
        )

        missing: list[str] = []
        if not addon_ok:
            missing.append(f"{addon_name} file")
        if not config_ok:
            missing.append("Config.ini")
        if not section_ok:
            missing.append("class/spec")
        if not profile_ok:
            missing.append("BindPad profile")

        if missing:
            self.express_ready_status.set("Needs: " + ", ".join(missing))
            self._set_status_label(self.express_ready_label, False)
        else:
            self.express_ready_status.set("Ready for Preview")
            self._set_status_label(self.express_ready_label, True)
        self.refresh_express_custom_status()
        self.refresh_express_global_status(config_ok)

    def refresh_express_global_status(self, config_ok: bool | None = None) -> None:
        if not hasattr(self, "express_global_status_label"):
            return
        config_raw = self.ggl_config.get().strip().strip('"')
        if config_ok is None:
            config_ok = bool(config_raw) and Path(config_raw).exists()
        if not config_ok:
            self.express_global_status.set("Load Config.ini to check global binds.")
            self.express_global_missing.set("")
            self._set_status_label(self.express_global_status_label, False)
            return
        try:
            general_names = set(load_action_names(Path(config_raw), "General"))
        except Exception:
            self.express_global_status.set("Could not read General global binds.")
            self.express_global_missing.set("")
            self._set_status_label(self.express_global_status_label, False)
            return

        present = [name for name in GLOBAL_ACTIONS if name in general_names]
        missing = [name for name in GLOBAL_ACTIONS if name not in general_names]
        self.express_global_status.set(f"Found in Config.ini: {len(present)}/{len(GLOBAL_ACTIONS)}")
        if missing:
            self._set_status_label(self.express_global_status_label, False)
            self.express_global_missing.set("Missing from General: " + ", ".join(missing))
        else:
            self._set_status_label(self.express_global_status_label, True)
            self.express_global_missing.set("All Express global binds are available.")

    def _grid_hint(
        self,
        parent: ttk.Frame,
        text: str,
        row: int,
        column: int = 0,
        columnspan: int = 3,
    ) -> None:
        ttk.Label(parent, text=text, style="Muted.TLabel", wraplength=700).grid(
            row=row,
            column=column,
            columnspan=columnspan,
            sticky="w",
            pady=(4, 0),
        )

    def _pack_hint(self, parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text, style="Muted.TLabel", wraplength=700).pack(
            fill="x",
            pady=(8, 0),
        )

    def _path_dialog_details(self, var: tk.StringVar) -> tuple[str, list[str], list[tuple[str, str]]]:
        if var is self.ggl_config:
            return (
                "Path to Config.ini",
                [CONFIG_EXAMPLE_PATH],
                [("Config.ini", "Config.ini"), ("INI files", "*.ini"), ("All files", "*.*")],
            )
        if var is self.seed_config:
            return (
                "Path to seed Config.ini",
                [SEED_CONFIG_EXAMPLE_PATH],
                [("INI files", "*.ini"), ("All files", "*.*")],
            )
        examples = [DEBOUNCE_EXAMPLE_PATH, BINDPAD_EXAMPLE_PATH]
        if self.macro_addon.get() == "BindPad":
            examples = [BINDPAD_EXAMPLE_PATH, DEBOUNCE_EXAMPLE_PATH]
        return (
            "Path to addon SavedVariables file",
            examples,
            [("Lua files", "*.lua"), ("All files", "*.*")],
        )

    def _center_child_window(self, child: tk.Toplevel) -> None:
        child.update_idletasks()
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_w = self.winfo_width()
        parent_h = self.winfo_height()
        child_w = child.winfo_width()
        child_h = child.winfo_height()
        x = parent_x + max((parent_w - child_w) // 2, 0)
        y = parent_y + max((parent_h - child_h) // 3, 0)
        child.geometry(f"+{x}+{y}")

    def choose_path(self, var: tk.StringVar) -> str:
        title, examples, filetypes = self._path_dialog_details(var)
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        selected = {"path": ""}
        path_value = tk.StringVar(value=var.get().strip())

        body = ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(body, text="Example path:", style="Muted.TLabel").pack(anchor="w", pady=(10, 2))
        for example in examples:
            example_entry = ttk.Entry(body, width=82)
            example_entry.insert(0, example)
            example_entry.configure(state="readonly")
            example_entry.pack(fill="x", pady=(0, 4))
        ttk.Label(body, text="Selected path:", style="Muted.TLabel").pack(anchor="w", pady=(8, 2))
        path_entry = ttk.Entry(body, textvariable=path_value, width=82)
        path_entry.pack(fill="x")

        def browse_files() -> None:
            current = Path(path_value.get().strip()) if path_value.get().strip() else None
            options: dict[str, object] = {
                "parent": dialog,
                "title": title,
                "filetypes": filetypes,
            }
            if current:
                if current.parent.exists():
                    options["initialdir"] = str(current.parent)
                if current.name:
                    options["initialfile"] = current.name
            path = filedialog.askopenfilename(**options)
            if path:
                selected["path"] = path
                dialog.destroy()

        def use_typed_path() -> None:
            path = path_value.get().strip().strip('"')
            if path:
                selected["path"] = path
            dialog.destroy()

        def cancel() -> None:
            selected["path"] = ""
            dialog.destroy()

        button_row = ttk.Frame(body)
        button_row.pack(fill="x", pady=(12, 0))
        ttk.Button(button_row, text="Browse Files", command=browse_files).pack(side="left")
        ttk.Button(button_row, text="Use This Path", command=use_typed_path).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="Cancel", command=cancel).pack(side="right")

        dialog.bind("<Return>", lambda _event: use_typed_path())
        dialog.bind("<Escape>", lambda _event: cancel())
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self._center_child_window(dialog)
        path_entry.focus_set()
        self.wait_window(dialog)
        return selected["path"]

    def browse(self, var: tk.StringVar) -> None:
        selected = self.choose_path(var)
        if selected:
            var.set(selected)
            if var is self.debounce_path:
                self.refresh_bindpad_profiles()
            if var is self.ggl_config:
                seed = sync.default_seed_path(Path(selected))
                if seed and not self.seed_config.get().strip():
                    self.seed_config.set(str(seed))
                self.save_current_settings()
                self.reload_sections()
                self.refresh_express_status()
                return
            self.save_current_settings()
            self.refresh_express_status()

    def auto_detect_express_paths(self) -> None:
        def var_path(var: tk.StringVar) -> Path | None:
            raw = var.get().strip().strip('"')
            return Path(raw) if raw else None

        addon = "BindPad" if self.macro_addon.get() == "BindPad" else "Debounce"
        addon_candidates = find_addon_saved_variable_candidates(addon, var_path(self.debounce_path))
        config_candidates = likely_config_ini_candidates(var_path(self.ggl_config))
        lines = ["Auto detect complete.", ""]
        missing: list[str] = []

        if addon_candidates:
            selected_addon = addon_candidates[0]
            self.debounce_path.set(str(selected_addon))
            lines.append(f"{addon} SavedVariables: {selected_addon}")
            if len(addon_candidates) > 1:
                lines.append(f"  Found {len(addon_candidates)} valid {addon} files; using the newest one.")
        else:
            missing.append(f"{addon} SavedVariables")
            lines.append(f"{addon} SavedVariables: not found")

        if config_candidates:
            selected_config = config_candidates[0]
            self.ggl_config.set(str(selected_config))
            seed = sync.default_seed_path(selected_config)
            if seed and (not self.seed_config.get().strip() or not Path(self.seed_config.get()).exists()):
                self.seed_config.set(str(seed))
            lines.append(f"Config.ini: {selected_config}")
            if len(config_candidates) > 1:
                lines.append(f"  Found {len(config_candidates)} valid Config.ini files; using the newest one.")
        else:
            missing.append("Config.ini")
            lines.append("Config.ini: not found")

        self.refresh_bindpad_profiles()
        if config_candidates:
            self.reload_sections()
        self.save_current_settings()
        lines.append("")
        if missing:
            lines.append("Anything not found can still be selected manually with Browse.")
            self.write_log("\n".join(lines))
            messagebox.showwarning(
                "Auto Detect Files",
                "I found what I could, but still need: " + ", ".join(missing) + ".",
            )
        else:
            self.write_log("\n".join(lines))
            messagebox.showinfo("Auto Detect Files", "Found and filled the files for Express setup.")

    def reports_dir(self) -> Path:
        path = app_dir() / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def open_reports(self) -> None:
        import os

        os.startfile(self.reports_dir())

    def add_preflight_item(
        self,
        items: list[PreflightItem],
        label: str,
        status: str,
        detail: str,
        blocking: bool = False,
    ) -> None:
        items.append(PreflightItem(label, status, detail, blocking and status == "FAIL"))

    def active_preflight_actions(
        self,
        sections: dict[str, list[sync.GglEntry]],
        section: str,
    ) -> dict[str, set[str]]:
        actions: dict[str, set[str]] = {}
        if section and section != "General":
            names = {entry.name for entry in sections.get(section, [])}
            actions[section] = names - self.disabled_actions_by_section.get(section, set())
        if self.global_binds.get():
            names = {entry.name for entry in sections.get("General", [])}
            actions["General"] = (names & set(GLOBAL_ACTIONS)) - self.disabled_actions_by_section.get("General", set())
        elif section == "General":
            names = {entry.name for entry in sections.get("General", [])}
            actions["General"] = names - self.disabled_actions_by_section.get("General", set())
        return {name: values for name, values in actions.items() if values}

    def duplicate_loader_hotkeys(
        self,
        sections: dict[str, list[sync.GglEntry]],
        active_actions: dict[str, set[str]],
        layout: sync.KeyLayout,
    ) -> list[str]:
        seen: dict[sync.KeyBind, list[str]] = {}
        for section, action_names in active_actions.items():
            for entry in sections.get(section, []):
                if entry.name not in action_names or not entry.value:
                    continue
                key, _suffix = sync.ggl_token_to_key(entry.value)
                if key:
                    seen.setdefault(key, []).append(f"{section}: {entry.name}")
        duplicates = []
        for key, owners in seen.items():
            if len(owners) > 1:
                joined = ", ".join(owners[:3])
                if len(owners) > 3:
                    joined += f", +{len(owners) - 3} more"
                duplicates.append(f"{key.human(layout)} -> {joined}")
        return duplicates

    def duplicate_addon_macro_names(self, active_actions: dict[str, set[str]]) -> list[str]:
        seen: dict[str, list[str]] = {}
        for section, action_names in active_actions.items():
            overrides = self.custom_overrides_for_section(section)
            for action_name in sorted(action_names):
                override = overrides.get(action_name)
                macro_name = override.name.strip() if override and override.name.strip() else action_name
                seen.setdefault(macro_name.lower(), []).append(f"{section}: {action_name}")
        duplicates: list[str] = []
        for owners in seen.values():
            if len(owners) <= 1:
                continue
            label = owners[0].split(": ", 1)[-1]
            joined = ", ".join(owners[:3])
            if len(owners) > 3:
                joined += f", +{len(owners) - 3} more"
            duplicates.append(f"{label} -> {joined}")
        return duplicates

    def custom_macro_preflight_errors(
        self,
        sections: dict[str, list[sync.GglEntry]],
        section: str,
    ) -> tuple[int, list[str]]:
        if not section:
            return 0, []
        action_lookup = {
            name: {entry.name for entry in entries}
            for name, entries in sections.items()
        }
        active_count = 0
        errors: list[str] = []
        for row in self.custom_pixels:
            if not row.get("enabled", True):
                continue
            if not self.custom_row_visible_for_section(row, section):
                continue
            active_count += 1
            row_section = str(row.get("section", "")).strip()
            loader_action = str(row.get("loader_action", "")).strip()
            macro_name = str(row.get("macro_name", "")).strip()
            if not macro_name:
                errors.append(f"{loader_action or '(blank action)'} has no macro name")
            if row_section not in sections:
                errors.append(f"{loader_action or '(blank action)'} uses missing section {row_section or '(blank)'}")
                continue
            if loader_action not in action_lookup.get(row_section, set()):
                errors.append(f"{row_section}: {loader_action or '(blank action)'} not found in Config.ini")
        return active_count, errors

    def collect_preflight_items(self, apply: bool) -> list[PreflightItem]:
        items: list[PreflightItem] = []
        section = self.section.get().strip()
        macro_addon = "BindPad" if self.macro_addon.get() == "BindPad" else "Debounce"
        addon_path = Path(self.debounce_path.get().strip())
        ggl_config = Path(self.ggl_config.get().strip())
        seed_config = Path(self.seed_config.get().strip()) if self.seed_config.get().strip() else None
        layout = self.current_layout()
        bind_all = self.bind_all_sections.get()

        if bind_all:
            self.add_preflight_item(items, "Class/spec", "OK", "All playable class/spec sections.")
            if macro_addon == "BindPad":
                self.add_preflight_item(items, "Bind all sections", "FAIL", "All-class binding is Debounce-only for now.", True)
        elif section:
            self.add_preflight_item(items, "Class/spec", "OK", section)
            if macro_addon == "Debounce":
                try:
                    sync.section_to_debounce_target(section)
                except (RuntimeError, ValueError, SystemExit) as exc:
                    self.add_preflight_item(items, "Class/spec target", "FAIL", str(exc), True)
            else:
                spec_index = sync.bindpad_spec_index_for_section(section)
                if spec_index is None:
                    self.add_preflight_item(items, "BindPad target", "OK", "General BindPad binds.")
                else:
                    self.add_preflight_item(items, "BindPad target", "OK", f"Character-specific BindPad tab {spec_index}.")
        else:
            self.add_preflight_item(items, "Class/spec", "FAIL", "Choose a class/spec first.", True)

        addon_ok = False
        if not addon_path.exists():
            self.add_preflight_item(items, "Addon file", "FAIL", "Choose a valid Debounce.lua or BindPad.lua path.", True)
        else:
            try:
                if macro_addon == "Debounce":
                    normalized_addon_path = normalize_debounce_path(addon_path)
                    if normalized_addon_path != addon_path:
                        self.add_preflight_item(
                            items,
                            "Addon file",
                            "WARN",
                            "Selected Debounce file looks character-specific; account-wide file was found and will be used.",
                        )
                        addon_path = normalized_addon_path
                    text, _encoding, _newline = sync.read_text(addon_path)
                    sync.parse_debounce_vars(text)
                    addon_ok = True
                    self.add_preflight_item(items, "Addon file", "OK", f"Debounce file found ({file_size_label(addon_path)}).")
                else:
                    text, _encoding, _newline = sync.read_text(addon_path)
                    vars_table = sync.parse_bindpad_vars(text)
                    addon_ok = True
                    profile_count = len(sync.bindpad_profile_keys(vars_table))
                    self.add_preflight_item(items, "Addon file", "OK", f"BindPad file found with {profile_count} profile(s).")
                    bindpad_profile = self.active_bindpad_profile_key()
                    if (bind_all or section != "General") and not bindpad_profile:
                        self.add_preflight_item(items, "BindPad profile", "FAIL", "Choose a BindPad character/profile.", True)
                    elif bind_all or section != "General":
                        self.add_preflight_item(items, "BindPad profile", "OK", self.bindpad_profile.get().strip() or bindpad_profile or "Selected")
            except Exception as exc:
                self.add_preflight_item(items, "Addon file", "FAIL", str(exc), True)

        sections: dict[str, list[sync.GglEntry]] = {}
        config_ok = False
        if not ggl_config.exists():
            self.add_preflight_item(items, "Config.ini", "FAIL", "Choose a valid Config.ini path.", True)
        else:
            try:
                ggl_text, _encoding, _newline = sync.read_text(ggl_config)
                sections, _ggl_lines = sync.parse_ggl_entries(ggl_text)
                if not sections:
                    raise RuntimeError("Config.ini did not contain any sections.")
                config_ok = True
                self.add_preflight_item(items, "Config.ini", "OK", f"{len(sections)} section(s) found.")
                if bind_all:
                    playable = [
                        candidate for candidate in self.express_playable_sections(section_order(sections))
                    ]
                    if macro_addon == "Debounce":
                        playable = [
                            candidate
                            for candidate in playable
                            if sync.retail_debounce_target_from_section(candidate)
                        ]
                    if playable:
                        self.add_preflight_item(items, "Selected sections", "OK", f"{len(playable)} class/spec section(s) will be processed.")
                    else:
                        self.add_preflight_item(items, "Selected sections", "FAIL", "No supported class/spec sections found in Config.ini.", True)
                elif section and section not in sections:
                    self.add_preflight_item(items, "Selected section", "FAIL", f"{section} is not in Config.ini.", True)
                elif section:
                    self.add_preflight_item(items, "Selected section", "OK", "Found in Config.ini.")

                seed_sections = None
                if seed_config:
                    if seed_config.exists():
                        seed_text, _seed_encoding, _seed_newline = sync.read_text(seed_config)
                        seed_sections, _seed_lines = sync.parse_ggl_entries(seed_text)
                        self.add_preflight_item(items, "Seed config", "OK", "Seed file found.")
                    else:
                        self.add_preflight_item(items, "Seed config", "WARN", "Seed path is set but the file was not found.")
                suffix = sync.find_suffix(sections, seed_sections)
                if suffix:
                    self.add_preflight_item(items, "Loader suffix", "OK", "Keyboard suffix found.")
                else:
                    self.add_preflight_item(items, "Loader suffix", "FAIL", "Could not find keyboard suffix in Config.ini.", True)
            except Exception as exc:
                self.add_preflight_item(items, "Config.ini", "FAIL", str(exc), True)

        try:
            enabled_scans = self.selected_keys()
            enabled_mods = self.selected_mods()
            allow_unmodified = self.allow_unmodified.get()
            blocked_keys = sync.parse_keybind_set(self.blocked_binds.get(), layout)
            candidates = sync.key_candidates(
                enabled_scans,
                None,
                enabled_mods,
                allow_unmodified,
                blocked_keys,
                layout,
            )
            if not enabled_scans:
                self.add_preflight_item(items, "Key pool", "FAIL", "Choose at least one allowed keyboard key.", True)
            elif not enabled_mods and not allow_unmodified:
                self.add_preflight_item(items, "Key pool", "FAIL", "Choose at least one modifier, or allow no-modifier binds.", True)
            else:
                self.add_preflight_item(items, "Key pool", "OK", f"{len(candidates)} usable key combination(s).")
        except ValueError as exc:
            candidates = []
            self.add_preflight_item(items, "Reserved binds", "FAIL", str(exc), True)

        if config_ok and (section or bind_all):
            if bind_all:
                active_actions: dict[str, set[str]] = {}
                for run_section in self.playable_sections_for_current_config(macro_addon):
                    names = {entry.name for entry in sections.get(run_section, [])}
                    selected = names - self.disabled_actions_by_section.get(run_section, set())
                    if selected:
                        active_actions[run_section] = selected
                if self.global_binds.get():
                    names = {entry.name for entry in sections.get("General", [])}
                    selected = (names & set(GLOBAL_ACTIONS)) - self.disabled_actions_by_section.get("General", set())
                    if selected:
                        active_actions["General"] = selected
            else:
                active_actions = self.active_preflight_actions(sections, section)
            required = sum(len(names) for names in active_actions.values())
            largest_section_required = max((len(names) for names in active_actions.values()), default=0)
            if required == 0:
                self.add_preflight_item(items, "Actions to bind", "WARN", "No active actions selected for this run.")
            elif candidates and len(candidates) < largest_section_required:
                self.add_preflight_item(
                    items,
                    "Actions to bind",
                    "FAIL",
                    f"Largest section needs {largest_section_required} bind(s), but only {len(candidates)} usable key combination(s) are available.",
                    True,
                )
            elif bind_all:
                self.add_preflight_item(
                    items,
                    "Actions to bind",
                    "OK",
                    f"{required} active action(s) across {len(active_actions)} section(s); largest section has {largest_section_required}.",
                )
            else:
                self.add_preflight_item(items, "Actions to bind", "OK", f"{required} active action(s).")

            if bind_all:
                duplicates = []
                for active_section, action_names in active_actions.items():
                    duplicates.extend(
                        self.duplicate_loader_hotkeys(sections, {active_section: action_names}, layout)
                    )
            else:
                duplicates = self.duplicate_loader_hotkeys(sections, active_actions, layout)
            if duplicates:
                detail = "; ".join(duplicates[:3])
                if len(duplicates) > 3:
                    detail += f"; +{len(duplicates) - 3} more"
                self.add_preflight_item(items, "Duplicate loader hotkeys", "WARN", detail)
            else:
                self.add_preflight_item(items, "Duplicate loader hotkeys", "OK", "No duplicate hotkeys in the active selection.")

            duplicate_macro_names = [] if bind_all else self.duplicate_addon_macro_names(active_actions)
            if bind_all:
                self.add_preflight_item(items, "Duplicate addon macro names", "OK", "Skipped across multiple sections; addon tabs are isolated by section.")
            elif duplicate_macro_names:
                detail = "; ".join(duplicate_macro_names[:3])
                if len(duplicate_macro_names) > 3:
                    detail += f"; +{len(duplicate_macro_names) - 3} more"
                self.add_preflight_item(items, "Duplicate addon macro names", "WARN", detail)
            else:
                self.add_preflight_item(items, "Duplicate addon macro names", "OK", "No duplicate macro names in the active selection.")

            if bind_all:
                custom_count = 0
                custom_errors = []
                seen_custom_errors: set[str] = set()
                for run_section in self.playable_sections_for_current_config(macro_addon):
                    count, errors = self.custom_macro_preflight_errors(sections, run_section)
                    custom_count += count
                    for error in errors:
                        if error not in seen_custom_errors:
                            custom_errors.append(error)
                            seen_custom_errors.add(error)
            else:
                custom_count, custom_errors = self.custom_macro_preflight_errors(sections, section)
            if custom_errors:
                detail = "; ".join(custom_errors[:4])
                if len(custom_errors) > 4:
                    detail += f"; +{len(custom_errors) - 4} more"
                self.add_preflight_item(items, "Custom macros", "FAIL", detail, True)
            elif custom_count:
                self.add_preflight_item(items, "Custom macros", "OK", f"{custom_count} active custom macro override(s).")
            else:
                self.add_preflight_item(items, "Custom macros", "OK", "No active custom macro overrides.")

        running = find_running_processes(APPLY_BLOCKING_PROCESSES)
        if running:
            status = "FAIL" if apply else "WARN"
            detail = "Close before Apply: " + ", ".join(running)
            self.add_preflight_item(items, "WoW / loader closed", status, detail, apply)
        else:
            self.add_preflight_item(items, "WoW / loader closed", "OK", "No blocking processes detected.")

        if addon_ok and config_ok:
            self.add_preflight_item(items, "File writes", "OK", "Backups will be created before Apply writes changes.")
        return items

    def preflight_has_blockers(self, items: list[PreflightItem]) -> bool:
        return any(item.blocking for item in items)

    def format_preflight(self, items: list[PreflightItem], apply: bool) -> str:
        label = "Apply" if apply else "Preview"
        blockers = sum(1 for item in items if item.blocking)
        warnings = sum(1 for item in items if item.status == "WARN")
        lines = [
            f"Preflight check for {label}",
            f"  Blocking issues: {blockers}",
            f"  Warnings: {warnings}",
            "",
        ]
        for item in items:
            lines.append(f"[{item.status}] {item.label}: {item.detail}")
        return "\n".join(lines)

    def run_preflight_check(self) -> None:
        try:
            items = self.collect_preflight_items(apply=True)
            text = self.format_preflight(items, apply=True)
            self.write_log(text)
            if self.preflight_has_blockers(items):
                messagebox.showwarning("Check Setup", "Preflight found issues. See Result for details.")
            else:
                messagebox.showinfo("Check Setup", "Preflight passed. See Result for details.")
        except Exception as exc:
            details = traceback.format_exc()
            self.write_log(f"{exc}\n\n{details}")
            messagebox.showerror("Check Setup", str(exc))

    def backup_targets(self) -> list[Path]:
        raw_targets = [
            self.debounce_path.get().strip(),
            self.ggl_config.get().strip(),
            self.seed_config.get().strip(),
            str(settings_path()),
        ]
        targets: list[Path] = []
        seen: set[str] = set()
        for raw in raw_targets:
            if not raw:
                continue
            target = Path(raw)
            key = safe_path_key(target)
            if key in seen:
                continue
            seen.add(key)
            targets.append(target)
        return targets

    def backup_kind(self, target: Path) -> str:
        name = target.name.lower()
        if name == "config.ini":
            return "Config.ini"
        if name == "debounce.lua":
            return "Debounce"
        if name == "bindpad.lua":
            return "BindPad"
        if name == settings_path().name.lower():
            return "App settings"
        return target.name

    def discover_backups(self) -> list[BackupInfo]:
        backups: list[BackupInfo] = []
        seen: set[str] = set()
        for target in self.backup_targets():
            parent = target.parent
            if not parent.exists():
                continue
            for candidate in parent.glob(target.name + ".bak*"):
                if not candidate.is_file():
                    continue
                restored_target = backup_target_from_path(candidate)
                if not restored_target or safe_path_key(restored_target) != safe_path_key(target):
                    continue
                key = safe_path_key(candidate)
                if key in seen:
                    continue
                seen.add(key)
                backups.append(
                    BackupInfo(
                        backup_path=candidate,
                        target_path=target,
                        kind=self.backup_kind(target),
                        mtime=safe_mtime(candidate),
                    )
                )
        return sorted(backups, key=lambda item: item.mtime, reverse=True)

    def backup_row_text(self, backup: BackupInfo) -> str:
        when = dt.datetime.fromtimestamp(backup.mtime).strftime("%Y-%m-%d %H:%M:%S") if backup.mtime else "unknown time"
        return (
            f"{when}  |  {backup.kind}  |  {file_size_label(backup.backup_path)}  |  "
            f"{backup.backup_path.name}"
        )

    def open_backup_manager(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Backup Manager")
        dialog.geometry("900x460")
        dialog.minsize(720, 360)
        dialog.configure(fg_color=ctk_theme("bg"))
        dialog.transient(self)

        ctk.CTkLabel(
            dialog,
            text="Backup Manager",
            text_color=ctk_theme("text"),
            font=("Segoe UI Semibold", 18),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            dialog,
            text="Backups are created before Apply or cleanup writes. Restore creates one more backup of the current file first.",
            text_color=ctk_theme("muted"),
            anchor="w",
            wraplength=840,
        ).pack(fill="x", padx=16, pady=(0, 12))

        body = ctk.CTkFrame(dialog, fg_color=ctk_theme("field"), border_color=ctk_theme("gold_dark"), border_width=1, corner_radius=8)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        listbox = tk.Listbox(
            body,
            selectmode="extended",
            activestyle="none",
            bg=THEME["field"],
            fg=THEME["text"],
            selectbackground=THEME["blue"],
            selectforeground=THEME["select_text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 10),
        )
        scrollbar = ttk.Scrollbar(body, command=listbox.yview, style="Vertical.TScrollbar")
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 10), pady=10)

        backups: list[BackupInfo] = []

        def selected_backups() -> list[BackupInfo]:
            return [backups[index] for index in listbox.curselection() if index < len(backups)]

        def refresh() -> None:
            nonlocal backups
            backups = self.discover_backups()
            listbox.delete(0, "end")
            if not backups:
                listbox.insert("end", "No app-created backups found for the current files.")
                listbox.itemconfig(0, foreground=THEME["muted"])
                return
            for backup in backups:
                listbox.insert("end", self.backup_row_text(backup))

        def restore_selected() -> None:
            selected = selected_backups()
            if len(selected) != 1:
                messagebox.showwarning("Restore Backup", "Select exactly one backup to restore.")
                return
            backup = selected[0]
            confirmed = messagebox.askyesno(
                "Restore Backup",
                "Restore this backup over the current file?\n\n"
                f"Backup: {backup.backup_path}\n\n"
                f"Target: {backup.target_path}\n\n"
                "The current target file will be backed up first.",
            )
            if not confirmed:
                return
            try:
                backup.target_path.parent.mkdir(parents=True, exist_ok=True)
                current_backup = sync.backup_file(backup.target_path) if backup.target_path.exists() else None
                shutil.copy2(backup.backup_path, backup.target_path)
                self.write_log(
                    "Restored backup.\n\n"
                    f"Backup restored: {backup.backup_path}\n"
                    f"Target file: {backup.target_path}\n"
                    + (f"Current file backup: {current_backup}\n" if current_backup else "")
                )
                if backup.target_path == Path(self.ggl_config.get().strip()):
                    self.reload_sections()
                if backup.target_path == Path(self.debounce_path.get().strip()):
                    self.refresh_bindpad_profiles()
                refresh()
                messagebox.showinfo("Restore Backup", "Backup restored.")
            except Exception as exc:
                messagebox.showerror("Restore Backup", str(exc))

        def delete_selected() -> None:
            selected = selected_backups()
            if not selected:
                messagebox.showwarning("Delete Backups", "Select one or more backups to delete.")
                return
            confirmed = messagebox.askyesno(
                "Delete Backups",
                f"Delete {len(selected)} selected backup file(s)?\n\nThis cannot be undone.",
            )
            if not confirmed:
                return
            deleted = 0
            errors: list[str] = []
            for backup in selected:
                try:
                    backup.backup_path.unlink()
                    deleted += 1
                except OSError as exc:
                    errors.append(f"{backup.backup_path}: {exc}")
            refresh()
            if errors:
                self.write_log("Deleted backups with errors:\n" + "\n".join(errors))
                messagebox.showwarning("Delete Backups", f"Deleted {deleted}; {len(errors)} failed.")
            else:
                self.write_log(f"Deleted {deleted} backup file(s).")

        def keep_newest() -> None:
            grouped: dict[str, list[BackupInfo]] = {}
            for backup in backups:
                grouped.setdefault(safe_path_key(backup.target_path), []).append(backup)
            to_delete: list[BackupInfo] = []
            for group in grouped.values():
                group.sort(key=lambda item: item.mtime, reverse=True)
                to_delete.extend(group[10:])
            if not to_delete:
                messagebox.showinfo("Keep Newest 10", "Nothing to delete. Each file already has 10 or fewer backups.")
                return
            confirmed = messagebox.askyesno(
                "Keep Newest 10",
                f"Delete {len(to_delete)} older backup file(s), keeping the newest 10 per target file?",
            )
            if not confirmed:
                return
            deleted = 0
            for backup in to_delete:
                try:
                    backup.backup_path.unlink()
                    deleted += 1
                except OSError:
                    pass
            refresh()
            self.write_log(f"Deleted {deleted} older backup file(s).")

        def open_selected_folder() -> None:
            selected = selected_backups()
            target = selected[0].backup_path.parent if selected else self.reports_dir()
            os.startfile(target)

        button_row = ctk.CTkFrame(dialog, fg_color="transparent")
        button_row.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(button_row, text="Refresh", width=90, command=refresh, corner_radius=8).pack(side="left")
        ctk.CTkButton(button_row, text="Restore Selected", width=134, command=restore_selected, corner_radius=8).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Delete Selected",
            width=126,
            command=delete_selected,
            corner_radius=8,
            fg_color=ctk_theme("danger_bg"),
            hover_color=ctk_theme("danger_hover"),
            text_color=ctk_theme("danger"),
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Keep Newest 10",
            width=126,
            command=keep_newest,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            button_row,
            text="Open Folder",
            width=108,
            command=open_selected_folder,
            corner_radius=8,
            fg_color=ctk_theme("secondary_button"),
            hover_color=ctk_theme("secondary_button_hover"),
        ).pack(side="right")
        refresh()

    def latest_report_csv(self) -> Path | None:
        reports = list(self.reports_dir().glob("wow_keybind_plan_*.csv"))
        if not reports:
            return None
        return max(reports, key=safe_mtime)

    def redaction_map(self) -> dict[str, str]:
        replacements: dict[str, str] = {}

        def add(raw: str | Path | None, label: str) -> None:
            if raw is None:
                return
            text = str(raw).strip()
            if not text:
                return
            candidates = {text}
            try:
                path = Path(text)
                candidates.add(str(path))
                candidates.add(path.as_posix())
                try:
                    candidates.add(str(path.resolve()))
                    candidates.add(path.resolve().as_posix())
                except OSError:
                    pass
            except Exception:
                pass
            for candidate in candidates:
                if len(candidate) >= 4:
                    replacements[candidate] = label

        add(Path.home(), "<USER_HOME>")
        add(app_dir(), "<APP_FOLDER>")
        add(self.reports_dir(), "<REPORTS_FOLDER>")
        add(self.debounce_path.get(), "<ADDON_FILE>")
        add(self.ggl_config.get(), "<CONFIG_INI>")
        add(self.seed_config.get(), "<SEED_CONFIG>")
        for raw, label in (
            (self.debounce_path.get(), "<ADDON_FOLDER>"),
            (self.ggl_config.get(), "<CONFIG_FOLDER>"),
            (self.seed_config.get(), "<SEED_FOLDER>"),
        ):
            if str(raw).strip():
                add(Path(str(raw)).parent, label)
        return replacements

    def redact_text(self, text: str, replacements: dict[str, str] | None = None) -> str:
        out = text
        replacement_map = replacements or self.redaction_map()
        for needle, label in sorted(replacement_map.items(), key=lambda item: len(item[0]), reverse=True):
            out = out.replace(needle, label)
            out = out.replace(needle.replace("/", "\\"), label)
            out = out.replace(needle.replace("\\", "/"), label)
        out = re.sub(r"C:\\Users\\[^\\\r\n]+", r"C:\\Users\\USER", out, flags=re.IGNORECASE)
        out = re.sub(r"(/Users/)[^/\r\n]+", r"\1USER", out)
        out = re.sub(r"(WTF\\Account\\)[^\\\r\n]+", r"\1YOUR ACCOUNT NUMBER", out, flags=re.IGNORECASE)
        out = re.sub(r"(WTF/Account/)[^/\r\n]+", r"\1YOUR ACCOUNT NUMBER", out, flags=re.IGNORECASE)
        return out

    def redact_data(self, value: object, replacements: dict[str, str]) -> object:
        if isinstance(value, dict):
            return {str(key): self.redact_data(item, replacements) for key, item in value.items()}
        if isinstance(value, list):
            return [self.redact_data(item, replacements) for item in value]
        if isinstance(value, tuple):
            return [self.redact_data(item, replacements) for item in value]
        if isinstance(value, str):
            return self.redact_text(value, replacements)
        return value

    def support_summary_text(self, preflight_text: str, latest_report: Path | None) -> str:
        addon_path = Path(self.debounce_path.get().strip()) if self.debounce_path.get().strip() else None
        config_path = Path(self.ggl_config.get().strip()) if self.ggl_config.get().strip() else None
        lines = [
            "WoW Keybind Sync support bundle",
            f"Created: {dt.datetime.now().isoformat(timespec='seconds')}",
            f"App version: {APP_VERSION}",
            f"Addon target: {self.macro_addon.get()}",
            f"Class/spec: {self.section.get().strip() or '(none selected)'}",
            f"Bind all class/spec sections: {'on' if self.bind_all_sections.get() else 'off'}",
            f"Keyboard layout: {self.current_layout().name}",
            f"Global binds: {'on' if self.global_binds.get() else 'off'}",
            f"Replace loader hotkeys: {'on' if self.overwrite_ggl.get() else 'off'}",
            f"Randomized layout: {'on' if self.randomize.get() else 'off'}",
            f"Addon file exists: {'yes' if addon_path and addon_path.exists() else 'no'}",
            f"Config.ini exists: {'yes' if config_path and config_path.exists() else 'no'}",
            f"Latest report included: {latest_report.name if latest_report else 'none'}",
            "",
            "Preflight summary:",
            preflight_text,
        ]
        return "\n".join(lines)

    def export_bug_report(self) -> None:
        try:
            replacements = self.redaction_map()
            try:
                preflight_items = self.collect_preflight_items(apply=True)
                preflight_text = self.format_preflight(preflight_items, apply=True)
            except Exception as exc:
                preflight_text = f"Preflight could not complete: {exc}\n\n{traceback.format_exc()}"
            latest_report = self.latest_report_csv()
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            path = self.reports_dir() / f"wow_keybind_support_bundle_{stamp}.zip"

            summary = self.redact_text(self.support_summary_text(preflight_text, latest_report), replacements)
            log_text = self.redact_text(self.last_log_text or "No log text captured yet.", replacements)
            settings_text = json.dumps(
                self.redact_data(self.settings_snapshot(), replacements),
                indent=2,
                ensure_ascii=False,
            )

            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("summary.txt", summary)
                archive.writestr("preflight.txt", self.redact_text(preflight_text, replacements))
                archive.writestr("last_result_log.txt", log_text)
                archive.writestr("settings_redacted.json", settings_text)
                if latest_report:
                    report_text = latest_report.read_text(encoding="utf-8", errors="replace")
                    archive.writestr("latest_preview_report.csv", self.redact_text(report_text, replacements))

            self.write_log(
                "Exported anonymized support bundle.\n\n"
                f"File: {path}\n\n"
                "Included: summary, preflight, last Result log, redacted settings"
                + (", latest preview CSV." if latest_report else ".")
            )
            messagebox.showinfo("Export Bug Report", f"Created support bundle:\n{path}")
            os.startfile(path.parent)
        except Exception as exc:
            details = traceback.format_exc()
            self.write_log(f"{exc}\n\n{details}")
            messagebox.showerror("Export Bug Report", str(exc))

    def remove_old_debounce_binds(self) -> None:
        try:
            section = self.section.get().strip()
            if not section:
                raise RuntimeError("Choose a class/spec or General first.")
            if self.macro_addon.get() == "BindPad":
                raise RuntimeError("This cleanup button is only for Debounce. Choose Debounce first.")
            addon_path = Path(self.debounce_path.get())
            if not addon_path.exists():
                raise RuntimeError("Choose a valid Debounce.lua path.")
            addon_path = normalize_debounce_path(addon_path)
            self.debounce_path.set(str(addon_path))
            running = find_running_processes(APPLY_BLOCKING_PROCESSES)
            if running:
                raise RuntimeError(
                    "Close these before cleaning Debounce: "
                    + ", ".join(running)
                    + ". Then run cleanup again."
                )

            target = "General" if section == "General" else section
            confirmed = messagebox.askyesno(
                "Remove Old Debounce Binds",
                "This will remove ALL Debounce entries in the selected target:\n\n"
                f"{target}\n\n"
                "A backup will be created first. Config.ini will not be changed.\n\n"
                "After this, press Apply to rebuild the current binds.\n\n"
                "Continue?",
            )
            if not confirmed:
                return

            text, encoding, _newline = sync.read_text(addon_path)
            vars_table = sync.parse_debounce_vars(text)
            class_file, spec_index = sync.section_to_debounce_target(section)
            removed = sync.clear_debounce_target(vars_table, class_file, spec_index)
            backup = sync.backup_file(addon_path)
            sync.write_text(addon_path, "DebounceVars = " + sync.dump_lua(vars_table) + "\n", encoding)
            self.write_log(
                f"Removed {removed} Debounce entries from {target}.\n"
                f"Backup: {backup}\n\n"
                "Press Apply to rebuild the current binds."
            )
            messagebox.showinfo(
                "Remove Old Debounce Binds",
                f"Removed {removed} Debounce entries from {target}. Press Apply to rebuild current binds.",
            )
        except Exception as exc:
            details = traceback.format_exc()
            self.write_log(f"{exc}\n\n{details}")
            messagebox.showerror("Remove Old Debounce Binds", str(exc))

    def _write_text_widget(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.configure(state="disabled")

    def write_log(self, text: str) -> None:
        self.last_log_text = text
        if hasattr(self, "log"):
            self._write_text_widget(self.log, text)
        if hasattr(self, "express_log"):
            self._write_text_widget(self.express_log, text)

    def on_macro_addon_changed(self) -> None:
        self.refresh_bindpad_profiles()
        self.save_current_settings()
        self.refresh_express_status()

    def active_bindpad_profile_key(self) -> str | None:
        selected = self.bindpad_profile.get().strip()
        if not selected:
            return None
        return self.bindpad_profile_labels.get(selected, selected if selected.startswith("PROFILE_") else None)

    def apply_bindpad_profile_combo_cache(self) -> None:
        if not getattr(self, "bindpad_profile_combos", None):
            return
        if self.macro_addon.get() != "BindPad":
            for combo in self.bindpad_profile_combos:
                combo.configure(values=[], state="disabled")
            return
        labels = list(self.bindpad_profile_labels)
        for combo in self.bindpad_profile_combos:
            combo.configure(values=labels, state="readonly")

    def refresh_bindpad_profiles(self) -> None:
        if not getattr(self, "bindpad_profile_combos", None):
            return
        if self.macro_addon.get() != "BindPad":
            for combo in self.bindpad_profile_combos:
                combo.configure(values=[], state="disabled")
            self.refresh_express_status()
            return
        for combo in self.bindpad_profile_combos:
            combo.configure(state="readonly")
        path = Path(self.debounce_path.get())
        if not path.exists():
            for combo in self.bindpad_profile_combos:
                combo.configure(values=[])
            self.refresh_express_status()
            return
        try:
            profiles = load_bindpad_profiles(path)
        except Exception as exc:
            for combo in self.bindpad_profile_combos:
                combo.configure(values=[])
            if hasattr(self, "log"):
                self.write_log(str(exc))
            self.refresh_express_status()
            return
        self.bindpad_profile_labels = {label: key for label, key in profiles}
        labels = [label for label, _key in profiles]
        for combo in self.bindpad_profile_combos:
            combo.configure(values=labels)
        current_key = self.active_bindpad_profile_key()
        if current_key:
            for label, key in profiles:
                if key == current_key:
                    self.bindpad_profile.set(label)
                    break
        elif labels:
            self.bindpad_profile.set(labels[0])
        self.save_current_settings()
        self.refresh_express_status()

    def on_section_changed(self) -> None:
        self.express_seed = None
        self.refresh_advanced_section_picker()
        self.refresh_express_section_picker()
        self.refresh_express_status()
        self.refresh_action_list()
        self.refresh_custom_controls()

    def current_action_names(self) -> list[str]:
        section = self.section.get().strip()
        ggl_config = self.ggl_config.get().strip()
        if not section or not ggl_config or not Path(ggl_config).exists():
            return []
        if self.action_names_config_key == safe_path_key(Path(ggl_config)):
            return list(self.action_names_by_section.get(section, []))
        try:
            return load_action_names(Path(ggl_config), section)
        except Exception:
            return []

    def current_general_custom_action_names(self) -> list[str]:
        ggl_config = self.ggl_config.get().strip()
        if not ggl_config or not Path(ggl_config).exists():
            return []
        if self.action_names_config_key == safe_path_key(Path(ggl_config)):
            names = list(self.action_names_by_section.get("General", []))
            return [name for name in names if name in GLOBAL_CUSTOM_TARGETING_ACTIONS]
        try:
            names = load_action_names(Path(ggl_config), "General")
        except Exception:
            return []
        return [name for name in names if name in GLOBAL_CUSTOM_TARGETING_ACTIONS]

    def current_custom_action_sources(self) -> dict[str, str]:
        section = self.section.get().strip()
        sources: dict[str, str] = {}
        for name in self.current_action_names():
            sources[name] = section
        if section != "General":
            for name in self.current_general_custom_action_names():
                sources.setdefault(name, "General")
        return sources

    def current_custom_action_names(self) -> list[str]:
        return list(self.current_custom_action_sources())

    def custom_row_visible_for_section(self, row: dict[str, object], section: str) -> bool:
        row_section = str(row.get("section", ""))
        if row_section == section:
            return True
        if section != "General" and row_section == "General":
            loader_action = str(row.get("loader_action", "")).strip()
            return loader_action in GLOBAL_CUSTOM_TARGETING_ACTIONS
        return False

    def refresh_action_list(self, preserve_view: bool = False) -> None:
        if not hasattr(self, "action_list"):
            return
        view_start = self.action_list.yview()[0] if preserve_view else 0.0
        selected_indices = set(self.action_list.curselection()) if preserve_view else set()
        section = self.section.get().strip()
        names = self.current_action_names()
        disabled = self.disabled_actions_by_section.get(section, set())
        self.action_visible_names = names
        self.action_list.delete(0, "end")
        if not names:
            self.action_list.insert("end", "Choose a Config.ini and class/spec to load actions.")
            return
        for index, name in enumerate(names):
            marker = " " if name in disabled else "x"
            self.action_list.insert("end", f"[{marker}] {name}")
            if name in disabled:
                self.action_list.itemconfig(index, foreground=THEME["muted"])
        if preserve_view:
            for index in selected_indices:
                if index < len(names):
                    self.action_list.selection_set(index)
            self.action_list.yview_moveto(view_start)

    def toggle_selected_actions(self) -> None:
        section = self.section.get().strip()
        if not section or not self.action_visible_names:
            return
        disabled = set(self.disabled_actions_by_section.get(section, set()))
        for index in self.action_list.curselection():
            if index >= len(self.action_visible_names):
                continue
            name = self.action_visible_names[index]
            if name in disabled:
                disabled.remove(name)
            else:
                disabled.add(name)
        self.disabled_actions_by_section[section] = disabled
        self.save_current_settings()
        self.refresh_action_list(preserve_view=True)

    def enable_selected_actions(self) -> None:
        section = self.section.get().strip()
        if not section or not self.action_visible_names:
            return
        disabled = set(self.disabled_actions_by_section.get(section, set()))
        for index in self.action_list.curselection():
            if index < len(self.action_visible_names):
                disabled.discard(self.action_visible_names[index])
        self.disabled_actions_by_section[section] = disabled
        self.save_current_settings()
        self.refresh_action_list(preserve_view=True)

    def disable_selected_actions(self) -> None:
        section = self.section.get().strip()
        if not section or not self.action_visible_names:
            return
        disabled = set(self.disabled_actions_by_section.get(section, set()))
        for index in self.action_list.curselection():
            if index < len(self.action_visible_names):
                disabled.add(self.action_visible_names[index])
        self.disabled_actions_by_section[section] = disabled
        self.save_current_settings()
        self.refresh_action_list(preserve_view=True)

    def enable_all_actions(self) -> None:
        section = self.section.get().strip()
        if not section:
            return
        self.disabled_actions_by_section[section] = set()
        self.save_current_settings()
        self.refresh_action_list(preserve_view=True)

    def disable_all_actions(self) -> None:
        section = self.section.get().strip()
        if not section or not self.action_visible_names:
            return
        self.disabled_actions_by_section[section] = set(self.action_visible_names)
        self.save_current_settings()
        self.refresh_action_list(preserve_view=True)

    def selected_action_names_for_section(self, section: str, allowed_names: set[str] | None = None) -> set[str]:
        ggl_config = Path(self.ggl_config.get())
        if self.action_names_config_key == safe_path_key(ggl_config):
            names = set(self.action_names_by_section.get(section, []))
        else:
            names = set(load_action_names(ggl_config, section))
        if allowed_names is not None:
            names &= allowed_names
        return names - self.disabled_actions_by_section.get(section, set())

    def playable_sections_for_current_config(self, macro_addon: str | None = None) -> list[str]:
        addon = macro_addon or ("BindPad" if self.macro_addon.get() == "BindPad" else "Debounce")
        sections = self.express_playable_sections(self.available_sections)
        if not sections:
            config_raw = self.ggl_config.get().strip()
            if not config_raw:
                return []
            sections = self.express_playable_sections(load_sections(Path(config_raw)))
        if addon == "Debounce":
            supported = []
            for section in sections:
                try:
                    sync.section_to_debounce_target(section)
                except (RuntimeError, ValueError, SystemExit):
                    continue
                supported.append(section)
            return supported
        return sections

    def refresh_custom_controls(self) -> None:
        if not hasattr(self, "custom_loader_combo"):
            return
        names = self.current_custom_action_names()
        self.custom_loader_combo.configure(values=names)
        self.refresh_custom_list()

    def custom_macro_counts_for_section(self, section: str) -> tuple[int, int]:
        if not section:
            return 0, 0
        total = 0
        enabled = 0
        for row in self.custom_pixels:
            if not self.custom_row_visible_for_section(row, section):
                continue
            total += 1
            if row.get("enabled", True):
                enabled += 1
        return enabled, total

    def refresh_express_custom_status(self) -> None:
        if not hasattr(self, "express_custom_status"):
            return
        section = self.section.get().strip()
        if not section or section == "General":
            self.express_custom_status.set("Choose a class/spec first.")
            return
        enabled, total = self.custom_macro_counts_for_section(section)
        if not total:
            self.express_custom_status.set("No custom macros imported.")
        elif enabled == total:
            self.express_custom_status.set(f"{total} custom macro{'s' if total != 1 else ''} loaded.")
        else:
            self.express_custom_status.set(f"{enabled}/{total} custom macros enabled.")

    def refresh_custom_list(self) -> None:
        if not hasattr(self, "custom_list"):
            return
        section = self.section.get().strip()
        self.custom_visible_indices = []
        self.custom_list.delete(0, "end")
        for index, row in enumerate(self.custom_pixels):
            if not self.custom_row_visible_for_section(row, section):
                continue
            self.custom_visible_indices.append(index)
            enabled = "x" if row.get("enabled", True) else " "
            loader_action = str(row.get("loader_action", ""))
            macro_name = str(row.get("macro_name", ""))
            macro_text = str(row.get("macro_text", "")).strip().splitlines()
            suffix = f" | {macro_text[0]}" if macro_text else ""
            scope = "General | " if row.get("section") == "General" and section != "General" else ""
            self.custom_list.insert("end", f"[{enabled}] {scope}{loader_action} -> {macro_name}{suffix}")
            if not row.get("enabled", True):
                self.custom_list.itemconfig(len(self.custom_visible_indices) - 1, foreground=THEME["muted"])
        if not self.custom_visible_indices:
            self.custom_list.insert("end", "No custom pixels for this class/spec or General targeting yet.")
            self.custom_list.itemconfig(0, foreground=THEME["muted"])
        self.refresh_express_custom_status()

    def clear_custom_pixel_fields(self) -> None:
        self.custom_loader_action.set("")
        self.custom_macro_name.set("")
        self.custom_enabled.set(True)
        self.custom_macro_text.delete("1.0", "end")

    def load_selected_custom_pixel(self) -> None:
        if not self.custom_visible_indices:
            return
        selection = self.custom_list.curselection()
        if not selection:
            return
        visible_index = selection[0]
        if visible_index >= len(self.custom_visible_indices):
            return
        row = self.custom_pixels[self.custom_visible_indices[visible_index]]
        self.custom_loader_action.set(str(row.get("loader_action", "")))
        self.custom_macro_name.set(str(row.get("macro_name", "")))
        self.custom_enabled.set(bool(row.get("enabled", True)))
        self.custom_macro_text.delete("1.0", "end")
        self.custom_macro_text.insert("end", str(row.get("macro_text", "")))

    def upsert_custom_pixel(
        self,
        target_section: str,
        loader_action: str,
        macro_name: str,
        macro_text: str,
        enabled: bool,
    ) -> str:
        replacement = {
            "section": target_section,
            "loader_action": loader_action,
            "macro_name": macro_name,
            "macro_text": macro_text,
            "enabled": enabled,
        }
        loader_key = loader_action.lower()
        for index, row in enumerate(self.custom_pixels):
            if row.get("section") == target_section and str(row.get("loader_action", "")).lower() == loader_key:
                self.custom_pixels[index] = replacement
                return "updated"
        self.custom_pixels.append(replacement)
        return "added"

    def parse_custom_macro_enabled(self, value: str) -> bool:
        text = value.strip().lower()
        if not text:
            return True
        if text in {"1", "true", "yes", "y", "on", "enabled", "x"}:
            return True
        if text in {"0", "false", "no", "n", "off", "disabled"}:
            return False
        raise ValueError("enabled must be true/false")

    def load_action_name_lookup(self, ggl_config: Path, section: str) -> dict[str, str]:
        if self.action_names_config_key == safe_path_key(ggl_config):
            names = self.action_names_by_section.get(section, [])
        else:
            names = load_action_names(ggl_config, section)
        return {name.lower(): name for name in names}

    def import_custom_macro_file(self, path: Path) -> tuple[int, int, list[str]]:
        ggl_config = Path(self.ggl_config.get().strip())
        if not ggl_config.exists():
            raise RuntimeError("Choose Config.ini before importing custom macros.")
        if self.action_names_config_key == safe_path_key(ggl_config) and self.available_sections:
            sections = list(self.available_sections)
        else:
            sections, action_names = load_sections_and_action_names(ggl_config)
            self.action_names_by_section = action_names
            self.action_names_config_key = safe_path_key(ggl_config)
        if not sections:
            raise RuntimeError("Config.ini did not contain any sections.")
        section_lookup = {section.lower(): section for section in sections}
        selected_section = self.section.get().strip()

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            field_lookup = {name.strip().lower(): name for name in fieldnames}
            required = ["section", "loader_action", "macro_name"]
            missing = [name for name in required if name not in field_lookup]
            if missing:
                raise RuntimeError("Missing required CSV columns: " + ", ".join(missing))

            imported = 0
            updated = 0
            skipped: list[str] = []
            action_cache: dict[str, dict[str, str]] = {}

            def value(row: dict[str, str], column: str) -> str:
                source = field_lookup.get(column)
                if not source:
                    return ""
                return str(row.get(source, "") or "").strip()

            def actions_for(section: str) -> dict[str, str]:
                if section not in action_cache:
                    action_cache[section] = self.load_action_name_lookup(ggl_config, section)
                return action_cache[section]

            for row_number, row in enumerate(reader, start=2):
                section_raw = value(row, "section")
                loader_action_raw = value(row, "loader_action")
                macro_name = value(row, "macro_name")
                macro_text = value(row, "macro_text").replace("\\n", "\n")
                enabled_raw = value(row, "enabled")

                try:
                    if section_raw.startswith("#"):
                        continue
                    if not section_raw:
                        raise ValueError("section is required")
                    if section_raw.lower() in {"selected", "current"}:
                        if not selected_section or selected_section == "General":
                            raise ValueError("section is selected/current but no class/spec is selected")
                        target_section = selected_section
                    else:
                        target_section = section_lookup.get(section_raw.lower(), "")
                        if not target_section:
                            raise ValueError(f"section is not in Config.ini: {section_raw}")
                    if not loader_action_raw:
                        raise ValueError("loader_action is required")
                    if not macro_name:
                        raise ValueError("macro_name is required")
                    enabled = self.parse_custom_macro_enabled(enabled_raw)

                    target_actions = actions_for(target_section)
                    loader_action = target_actions.get(loader_action_raw.lower())
                    storage_section = target_section
                    if not loader_action and target_section != "General":
                        general_actions = actions_for("General") if "General" in section_lookup.values() else {}
                        general_action = general_actions.get(loader_action_raw.lower())
                        if general_action and general_action in GLOBAL_CUSTOM_TARGETING_ACTIONS:
                            loader_action = general_action
                            storage_section = "General"
                    if not loader_action:
                        raise ValueError(f"loader_action is not available for {target_section}: {loader_action_raw}")

                    result = self.upsert_custom_pixel(
                        storage_section,
                        loader_action,
                        macro_name,
                        macro_text,
                        enabled,
                    )
                    imported += 1
                    if result == "updated":
                        updated += 1
                except ValueError as exc:
                    skipped.append(f"Row {row_number}: {exc}")

        self.save_current_settings()
        self.refresh_custom_controls()
        self.refresh_express_custom_status()
        return imported, updated, skipped

    def import_custom_macro_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Import Custom Macro CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            imported, updated, skipped = self.import_custom_macro_file(Path(path))
            added = imported - updated
            summary = [
                f"Imported custom macro CSV: {path}",
                f"Added: {added}",
                f"Updated: {updated}",
                f"Skipped: {len(skipped)}",
            ]
            if skipped:
                summary.append("")
                summary.extend(skipped[:25])
                if len(skipped) > 25:
                    summary.append(f"... {len(skipped) - 25} more skipped rows")
            self.write_log("\n".join(summary))
            if skipped:
                messagebox.showwarning(
                    "Import Custom Macro CSV",
                    f"Imported {imported} rows, skipped {len(skipped)}. See Result for details.",
                )
            else:
                messagebox.showinfo("Import Custom Macro CSV", f"Imported {imported} custom macro rows.")
        except Exception as exc:
            details = traceback.format_exc()
            self.write_log(f"{exc}\n\n{details}")
            messagebox.showerror("Import Custom Macro CSV", str(exc))

    def save_custom_macro_template(self) -> None:
        current = self.section.get().strip()
        example_section = current if current and current != "General" else "Warrior - Fury"
        path = filedialog.asksaveasfilename(
            title="Save Custom Macro CSV Template",
            defaultextension=".csv",
            initialfile="custom_macro_template.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        rows = [
            *CUSTOM_MACRO_TEMPLATE_INSTRUCTIONS,
            {
                "section": example_section,
                "loader_action": "Bitter Immunity",
                "macro_name": "Rend",
                "macro_text": "/cast Rend",
                "enabled": "true",
            },
            {
                "section": "General",
                "loader_action": "Target Arena1",
                "macro_name": "Target Arena 1",
                "macro_text": "/target arena1",
                "enabled": "true",
            },
        ]
        try:
            with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CUSTOM_MACRO_IMPORT_HEADERS)
                writer.writeheader()
                writer.writerows(rows)
            self.write_log(
                "Saved custom macro CSV template:\n"
                f"{path}\n\n"
                "Columns: section, loader_action, macro_name, macro_text, enabled\n"
                "AI instructions are included as # rows and ignored by import.\n"
                "Use literal \\n inside macro_text for multi-line macros."
            )
            messagebox.showinfo("Save Template", "Custom macro CSV template saved.")
        except Exception as exc:
            details = traceback.format_exc()
            self.write_log(f"{exc}\n\n{details}")
            messagebox.showerror("Save Template", str(exc))

    def add_or_update_custom_pixel(self) -> None:
        section = self.section.get().strip()
        loader_action = self.custom_loader_action.get().strip()
        macro_name = self.custom_macro_name.get().strip()
        macro_text = self.custom_macro_text.get("1.0", "end").strip()
        if not section:
            messagebox.showerror("Custom Pixel", "Choose a class/spec first.")
            return
        if not loader_action:
            messagebox.showerror("Custom Pixel", "Choose the loader action/pixel to bind.")
            return
        action_sources = self.current_custom_action_sources()
        target_section = action_sources.get(loader_action)
        if not target_section:
            messagebox.showerror(
                "Custom Pixel",
                "The loader action is not in the selected class/spec or General targeting actions.",
            )
            return
        if not macro_name:
            messagebox.showerror("Custom Pixel", "Enter the macro name to create in Debounce.")
            return
        self.upsert_custom_pixel(
            target_section,
            loader_action,
            macro_name,
            macro_text,
            self.custom_enabled.get(),
        )
        self.save_current_settings()
        self.refresh_custom_list()
        self.write_log(f"Saved custom pixel for {target_section}: {loader_action} -> {macro_name}")

    def remove_selected_custom_pixel(self) -> None:
        if not self.custom_visible_indices:
            return
        selection = self.custom_list.curselection()
        if not selection:
            return
        remove_indexes = [
            self.custom_visible_indices[index]
            for index in selection
            if index < len(self.custom_visible_indices)
        ]
        for index in sorted(remove_indexes, reverse=True):
            del self.custom_pixels[index]
        self.save_current_settings()
        self.refresh_custom_list()
        self.clear_custom_pixel_fields()

    def custom_overrides_for_section(self, section: str) -> dict[str, sync.MacroOverride]:
        overrides: dict[str, sync.MacroOverride] = {}
        for row in self.custom_pixels:
            if row.get("section") != section or not row.get("enabled", True):
                continue
            loader_action = str(row.get("loader_action", "")).strip()
            macro_name = str(row.get("macro_name", "")).strip()
            macro_text = str(row.get("macro_text", "")).strip()
            if loader_action and macro_name:
                overrides[loader_action] = sync.MacroOverride(macro_name, macro_text or None)
        return overrides

    def selected_keys(self) -> set[int]:
        layout = self.current_layout()
        return {
            scan
            for scan_id, var in self.key_vars.items()
            if (scan := sync.scan_from_id(scan_id)) is not None
            and var.get()
            and layout.supports_scan(scan)
        }

    def selected_mods(self) -> set[str]:
        return {mod for mod, var in self.mod_vars.items() if var.get()}

    def select_default_keys(self) -> None:
        layout = self.current_layout()
        defaults = set(layout.default_enabled_scans)
        for scan_id, var in self.key_vars.items():
            scan = sync.scan_from_id(scan_id)
            var.set(scan is not None and scan in defaults and layout.supports_scan(scan))
        self.refresh_key_rule_labels()
        self.save_current_settings()

    def select_all_safe_keys(self) -> None:
        layout = self.current_layout()
        for scan_id, var in self.key_vars.items():
            scan = sync.scan_from_id(scan_id)
            var.set(scan is not None and layout.supports_scan(scan))
        self.refresh_key_rule_labels()
        self.save_current_settings()

    def set_function_keys(self, enabled: bool) -> None:
        layout = self.current_layout()
        for scan_id, var in self.key_vars.items():
            scan = sync.scan_from_id(scan_id)
            if scan is None:
                continue
            base = sync.SCAN_TO_KEY.get(scan, "")
            if base.startswith("F") and layout.supports_scan(scan):
                var.set(enabled)
        self.refresh_key_rule_labels()
        self.save_current_settings()

    def set_numpad_keys(self, enabled: bool) -> None:
        layout = self.current_layout()
        for scan_id, var in self.key_vars.items():
            scan = sync.scan_from_id(scan_id)
            if scan is not None and scan in sync.NUMPAD_SCANS and layout.supports_scan(scan):
                var.set(enabled)
        self.refresh_key_rule_labels()
        self.save_current_settings()

    def disable_function_keys(self) -> None:
        self.set_function_keys(False)

    def enable_function_keys(self) -> None:
        self.set_function_keys(True)

    def disable_numpad_keys(self) -> None:
        self.set_numpad_keys(False)

    def enable_numpad_keys(self) -> None:
        self.set_numpad_keys(True)

    def clear_keys(self) -> None:
        for var in self.key_vars.values():
            var.set(False)
        self.refresh_key_rule_labels()
        self.save_current_settings()

    def new_random_seed(self) -> None:
        self.random_seed.set(sync.new_random_seed())
        self.randomize.set(True)
        self.save_current_settings()

    def settings_snapshot(self) -> dict[str, object]:
        return {
            "macro_addon": self.macro_addon.get(),
            "dark_mode": self.dark_mode.get(),
            "debounce_path": self.debounce_path.get(),
            "ggl_config": self.ggl_config.get(),
            "seed_config": self.seed_config.get(),
            "bindpad_profile": self.active_bindpad_profile_key() or self.bindpad_profile.get(),
            "global_binds": self.global_binds.get(),
            "bind_all_sections": self.bind_all_sections.get(),
            "overwrite_ggl": self.overwrite_ggl.get(),
            "randomize": self.randomize.get(),
            "random_seed": self.random_seed.get().strip(),
            "blocked_binds": self.blocked_binds.get().strip(),
            "keyboard_layout": self.keyboard_layout_id(),
            "enabled_mods": sorted(self.selected_mods(), key=sync.MODIFIER_ORDER.index),
            "allow_unmodified": self.allow_unmodified.get(),
            "enabled_key_ids": sorted(sync.scan_id(scan) for scan in self.selected_keys()),
            "disabled_actions_by_section": {
                section: sorted(actions)
                for section, actions in sorted(self.disabled_actions_by_section.items())
                if actions
            },
            "custom_pixels": self.custom_pixels,
        }

    def save_current_settings(self) -> None:
        save_settings(self.settings_snapshot())

    def schedule_save_current_settings(self) -> None:
        if self._save_job:
            try:
                self.after_cancel(self._save_job)
            except tk.TclError:
                pass
        self._save_job = self.after(500, self._run_scheduled_save)

    def _run_scheduled_save(self) -> None:
        self._save_job = None
        self.save_current_settings()

    def on_close(self) -> None:
        if self._save_job:
            try:
                self.after_cancel(self._save_job)
            except tk.TclError:
                pass
            self._save_job = None
            self.save_current_settings()
        self.destroy()

    def prompt_for_missing_paths(self) -> None:
        changed = False
        if not self.ggl_config.get().strip() or not Path(self.ggl_config.get()).exists():
            selected = self.choose_path(self.ggl_config)
            if selected:
                self.ggl_config.set(selected)
                seed = sync.default_seed_path(Path(selected))
                if seed and not self.seed_config.get().strip():
                    self.seed_config.set(str(seed))
                changed = True
        if not self.debounce_path.get().strip() or not Path(self.debounce_path.get()).exists():
            selected = self.choose_path(self.debounce_path)
            if selected:
                self.debounce_path.set(selected)
                self.refresh_bindpad_profiles()
                changed = True
        if changed:
            self.save_current_settings()
            self.reload_sections()

    def reload_sections(self) -> None:
        try:
            if not self.ggl_config.get().strip():
                self.write_log("Choose your Config.ini to load class/spec sections.")
                return
            config_path = Path(self.ggl_config.get())
            sections, action_names = load_sections_and_action_names(config_path)
            self.action_names_by_section = action_names
            self.action_names_config_key = safe_path_key(config_path)
            for combo in self.section_combos:
                combo.configure(values=sections)
            self.set_advanced_sections(sections)
            self.set_express_sections(sections)
            config_json = config_path.with_name("config.json")
            inferred = sync.section_from_config_json(config_json)
            current = self.section.get().strip()
            fallback = next((section for section in sections if section != "General"), sections[0] if sections else "")
            if inferred in sections and inferred != "General":
                self.section.set(inferred)
            elif current in sections and current != "General":
                self.section.set(current)
            elif fallback:
                self.section.set(fallback)
            self.on_section_changed()
            self.refresh_bindpad_profiles()
            self.refresh_express_status()
            self.write_log(f"Loaded {len(sections)} sections.")
        except Exception as exc:
            self.refresh_express_status()
            self.write_log(str(exc))
            messagebox.showerror("Could not load sections", str(exc))

    def express_state_snapshot(self) -> dict[str, object]:
        return {
            "global_binds": self.global_binds.get(),
            "overwrite_ggl": self.overwrite_ggl.get(),
            "randomize": self.randomize.get(),
            "random_seed": self.random_seed.get(),
            "blocked_binds": self.blocked_binds.get(),
            "keyboard_layout": self.keyboard_layout_display.get(),
            "enabled_mods": {mod: var.get() for mod, var in self.mod_vars.items()},
            "allow_unmodified": self.allow_unmodified.get(),
            "enabled_keys": {scan_id: var.get() for scan_id, var in self.key_vars.items()},
            "disabled_actions_by_section": {
                section: set(actions)
                for section, actions in self.disabled_actions_by_section.items()
            },
        }

    def restore_express_state_snapshot(self, snapshot: dict[str, object]) -> None:
        self.global_binds.set(bool(snapshot["global_binds"]))
        self.overwrite_ggl.set(bool(snapshot["overwrite_ggl"]))
        self.randomize.set(bool(snapshot["randomize"]))
        self.random_seed.set(str(snapshot["random_seed"]))
        self.blocked_binds.set(str(snapshot["blocked_binds"]))
        self.keyboard_layout_display.set(str(snapshot["keyboard_layout"]))
        for mod, value in dict(snapshot["enabled_mods"]).items():
            if str(mod) in self.mod_vars:
                self.mod_vars[str(mod)].set(bool(value))
        self.allow_unmodified.set(bool(snapshot["allow_unmodified"]))
        for scan_id, value in dict(snapshot["enabled_keys"]).items():
            if str(scan_id) in self.key_vars:
                self.key_vars[str(scan_id)].set(bool(value))
        self.refresh_key_rule_labels()
        self.disabled_actions_by_section = {
            str(section): set(actions)
            for section, actions in dict(snapshot["disabled_actions_by_section"]).items()
        }
        self.refresh_action_list()
        self.save_current_settings()

    def apply_express_defaults(self) -> None:
        if not self.express_seed:
            self.express_seed = sync.new_random_seed()
        self.global_binds.set(True)
        self.overwrite_ggl.set(True)
        self.randomize.set(True)
        self.random_seed.set(self.express_seed)
        for mod in sync.MODIFIER_ORDER:
            self.mod_vars[mod].set(True)
        self.allow_unmodified.set(False)
        layout = self.current_layout()
        default_keys = set(layout.default_enabled_scans)
        for scan_id, var in self.key_vars.items():
            scan = sync.scan_from_id(scan_id)
            var.set(scan is not None and scan in default_keys and layout.supports_scan(scan))
        self.refresh_key_rule_labels()

    def run_express_preflight_check(self) -> None:
        snapshot = self.express_state_snapshot()
        seed_snapshot = self.express_seed
        try:
            self.apply_express_defaults()
            items = self.collect_preflight_items(apply=True)
            text = self.format_preflight(items, apply=True)
            self.write_log(text)
            if self.preflight_has_blockers(items):
                messagebox.showwarning("Check Setup", "Preflight found issues. See Result for details.")
            else:
                messagebox.showinfo("Check Setup", "Express preflight passed. See Result for details.")
        except Exception as exc:
            details = traceback.format_exc()
            self.write_log(f"{exc}\n\n{details}")
            messagebox.showerror("Check Setup", str(exc))
        finally:
            self.restore_express_state_snapshot(snapshot)
            self.express_seed = seed_snapshot

    def run_express(self, apply: bool) -> None:
        snapshot = self.express_state_snapshot()

        try:
            if not apply:
                self.express_seed = sync.new_random_seed()
            self.apply_express_defaults()

            section = self.section.get().strip()
            if not section or section == "General":
                raise RuntimeError("Choose a class/spec first.")
            self.run(apply)
            if apply:
                self.express_seed = None
        finally:
            self.restore_express_state_snapshot(snapshot)

    def run(self, apply: bool) -> None:
        try:
            preflight_items = self.collect_preflight_items(apply=apply)
            preflight_text = self.format_preflight(preflight_items, apply=apply)
            if self.preflight_has_blockers(preflight_items):
                self.write_log(preflight_text)
                messagebox.showerror("Preflight Check", "Fix the blocking preflight issues before continuing.")
                return

            bind_all = self.bind_all_sections.get()
            section = self.section.get().strip()
            if not section and not bind_all:
                raise RuntimeError("Choose a class/spec first.")

            addon_path = Path(self.debounce_path.get())
            macro_addon = "BindPad" if self.macro_addon.get() == "BindPad" else "Debounce"
            if bind_all and macro_addon == "BindPad":
                raise RuntimeError("Bind all class/spec sections is Debounce-only for now.")
            bindpad_profile = self.active_bindpad_profile_key()
            ggl_config = Path(self.ggl_config.get())
            seed_config = Path(self.seed_config.get()) if self.seed_config.get().strip() else None
            reports_dir = self.reports_dir()
            layout = self.current_layout()
            enabled_scans = self.selected_keys()
            enabled_mods = self.selected_mods()
            allow_unmodified = self.allow_unmodified.get()
            try:
                blocked_keys = sync.parse_keybind_set(self.blocked_binds.get(), layout)
            except ValueError as exc:
                raise RuntimeError(f"Reserved binds: {exc}") from exc
            if not enabled_scans:
                raise RuntimeError("Choose at least one allowed keyboard key.")
            if not enabled_mods and not allow_unmodified:
                raise RuntimeError("Choose at least one modifier, or allow no-modifier binds.")
            if not addon_path.exists():
                raise RuntimeError("Choose a valid Debounce.lua or BindPad.lua path.")
            if macro_addon == "Debounce":
                normalized_debounce_path = normalize_debounce_path(addon_path)
                if normalized_debounce_path != addon_path:
                    addon_path = normalized_debounce_path
                    self.debounce_path.set(str(addon_path))
            else:
                try:
                    text, _, _ = sync.read_text(addon_path)
                    sync.parse_bindpad_vars(text)
                except Exception as exc:
                    raise RuntimeError("Choose a valid BindPad.lua SavedVariables file.") from exc
                self.refresh_bindpad_profiles()
                bindpad_profile = self.active_bindpad_profile_key()
                if (bind_all or section != "General") and not bindpad_profile:
                    raise RuntimeError("Choose a BindPad profile for class/spec binds.")
            if not ggl_config.exists():
                raise RuntimeError("Choose a valid Config.ini path.")
            if apply:
                running = find_running_processes(APPLY_BLOCKING_PROCESSES)
                if running:
                    raise RuntimeError(
                        "Close these before applying: "
                        + ", ".join(running)
                        + ". Then run Apply again."
                    )
            random_seed = self.random_seed.get().strip() if self.randomize.get() else None
            if self.randomize.get() and not random_seed:
                random_seed = sync.new_random_seed()
                self.random_seed.set(random_seed)
            self.save_current_settings()

            results = []
            if bind_all:
                keys_from_general: set[sync.KeyBind] = set()
                run_sections = self.playable_sections_for_current_config(macro_addon)
                if not run_sections:
                    raise RuntimeError("No supported class/spec sections found in Config.ini.")

                if self.global_binds.get():
                    general_cleanup_names = set(GLOBAL_ACTIONS)
                    general_action_names = self.selected_action_names_for_section(
                        "General",
                        set(GLOBAL_ACTIONS),
                    )
                    result, plans = run_once(
                        section="General",
                        action_names=general_action_names,
                        addon_path=addon_path,
                        macro_addon=macro_addon,
                        bindpad_profile=bindpad_profile,
                        ggl_config=ggl_config,
                        seed_config=seed_config,
                        apply=apply,
                        overwrite_ggl=self.overwrite_ggl.get(),
                        reports_dir=reports_dir,
                        layout=layout,
                        enabled_scans=enabled_scans,
                        random_seed=random_seed,
                        enabled_mods=enabled_mods,
                        allow_unmodified=allow_unmodified,
                        blocked_keys=blocked_keys,
                        macro_overrides=self.custom_overrides_for_section("General"),
                        loader_context_sections={"General"},
                        cleanup_names=general_cleanup_names,
                    )
                    results.append(result)
                    keys_from_general.update(plan.key for plan in plans if plan.key)

                for run_section in run_sections:
                    loader_context_sections = {"General", run_section}
                    spec_cleanup_names = set(load_action_names(ggl_config, run_section))
                    spec_action_names = self.selected_action_names_for_section(run_section)
                    result, plans = run_once(
                        section=run_section,
                        action_names=spec_action_names,
                        addon_path=addon_path,
                        macro_addon=macro_addon,
                        bindpad_profile=bindpad_profile,
                        ggl_config=ggl_config,
                        seed_config=seed_config,
                        apply=apply,
                        overwrite_ggl=self.overwrite_ggl.get(),
                        reports_dir=reports_dir,
                        layout=layout,
                        enabled_scans=enabled_scans,
                        random_seed=random_seed,
                        enabled_mods=enabled_mods,
                        allow_unmodified=allow_unmodified,
                        blocked_keys=blocked_keys,
                        extra_blocked_keys=keys_from_general,
                        macro_overrides=self.custom_overrides_for_section(run_section),
                        loader_context_sections=loader_context_sections,
                        cleanup_names=spec_cleanup_names,
                    )
                    results.append(result)
            else:
                keys_from_prior_passes: set[sync.KeyBind] = set()
                loader_context_sections = {"General", section} if section != "General" else {"General"}
                if section != "General":
                    spec_cleanup_names = set(load_action_names(ggl_config, section))
                    spec_action_names = self.selected_action_names_for_section(section)
                    result, plans = run_once(
                        section=section,
                        action_names=spec_action_names,
                        addon_path=addon_path,
                        macro_addon=macro_addon,
                        bindpad_profile=bindpad_profile,
                        ggl_config=ggl_config,
                        seed_config=seed_config,
                        apply=apply,
                        overwrite_ggl=self.overwrite_ggl.get(),
                        reports_dir=reports_dir,
                        layout=layout,
                        enabled_scans=enabled_scans,
                        random_seed=random_seed,
                        enabled_mods=enabled_mods,
                        allow_unmodified=allow_unmodified,
                        blocked_keys=blocked_keys,
                        macro_overrides=self.custom_overrides_for_section(section),
                        loader_context_sections=loader_context_sections,
                        cleanup_names=spec_cleanup_names,
                    )
                    results.append(result)
                    keys_from_prior_passes.update(plan.key for plan in plans if plan.key)

                if self.global_binds.get():
                    general_cleanup_names = set(GLOBAL_ACTIONS)
                    general_action_names = self.selected_action_names_for_section(
                        "General",
                        set(GLOBAL_ACTIONS),
                    )
                    result, plans = run_once(
                        section="General",
                        action_names=general_action_names,
                        addon_path=addon_path,
                        macro_addon=macro_addon,
                        bindpad_profile=bindpad_profile,
                        ggl_config=ggl_config,
                        seed_config=seed_config,
                        apply=apply,
                        overwrite_ggl=self.overwrite_ggl.get(),
                        reports_dir=reports_dir,
                        layout=layout,
                        enabled_scans=enabled_scans,
                        random_seed=random_seed,
                        enabled_mods=enabled_mods,
                        allow_unmodified=allow_unmodified,
                        blocked_keys=blocked_keys,
                        extra_blocked_keys=keys_from_prior_passes,
                        macro_overrides=self.custom_overrides_for_section("General"),
                        loader_context_sections=loader_context_sections,
                        cleanup_names=general_cleanup_names,
                    )
                    results.append(result)
                elif section == "General":
                    general_cleanup_names = set(load_action_names(ggl_config, "General"))
                    general_action_names = self.selected_action_names_for_section("General")
                    result, plans = run_once(
                        section="General",
                        action_names=general_action_names,
                        addon_path=addon_path,
                        macro_addon=macro_addon,
                        bindpad_profile=bindpad_profile,
                        ggl_config=ggl_config,
                        seed_config=seed_config,
                        apply=apply,
                        overwrite_ggl=self.overwrite_ggl.get(),
                        reports_dir=reports_dir,
                        layout=layout,
                        enabled_scans=enabled_scans,
                        random_seed=random_seed,
                        enabled_mods=enabled_mods,
                        allow_unmodified=allow_unmodified,
                        blocked_keys=blocked_keys,
                        macro_overrides=self.custom_overrides_for_section("General"),
                        loader_context_sections=loader_context_sections,
                        cleanup_names=general_cleanup_names,
                    )
                    results.append(result)

            prefix = "Applied" if apply else "Preview"
            self.write_log(preflight_text + "\n\n" + prefix + " complete.\n\n" + "\n\n".join(results))
            if apply:
                messagebox.showinfo("Done", "Keybinds applied. Restart/reload WoW and the loader before relying on them.")
        except Exception as exc:
            details = traceback.format_exc()
            self.write_log(f"{exc}\n\n{details}")
            messagebox.showerror("Keybind Sync", str(exc))


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        settings = load_settings()
        raw_config_path = str(settings.get("ggl_config", "")).strip()
        config_path = Path(raw_config_path) if raw_config_path else None
        if config_path and config_path.is_file():
            load_sections(config_path)
        raise SystemExit(0)
    App().mainloop()
