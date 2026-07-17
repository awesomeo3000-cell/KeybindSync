#!/usr/bin/env python3
"""
Sync safe WoW keybinds into Debounce.lua and GGL Config.ini.

Preview first:
    python wow_keybind_sync.py --section "Warrior - Fury"

Apply changes:
    python wow_keybind_sync.py --section "Warrior - Fury" --apply
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import json
import math
import random
import re
import shutil
import sys
from pathlib import Path
from typing import Any


DEFAULT_DEBOUNCE = Path(
    r"C:\World of Warcraft\_retail_\WTF\Account\YOUR ACCOUNT NUMBER\SavedVariables\Debounce.lua"
)
DEFAULT_GGL = Path(r"C:\Program Files (x86)\Your Folder Name\Config.ini")
DEFAULT_CONFIG_JSON = DEFAULT_GGL.with_name("config.json")

OLD_MANAGED_PREFIX = "GGL: "
MANAGED_PREFIX = ""
DEFAULT_ICON = 134400
MANAGED_SOURCE = "WoWKeybindSync"
BINDPAD_DEFAULT_SLOTS = 49
BINDPAD_PROFILE_VERSION = 252
MAX_LUA_DEPTH = 200
_NUM_RE = re.compile(
    r"-?(?:"
    r"0[xX][0-9A-Fa-f]+(?:\.[0-9A-Fa-f]*)?(?:[pP][+-]?\d+)?"
    r"|\d+\.?\d*(?:[eE][+-]?\d+)?"
    r"|\.\d+(?:[eE][+-]?\d+)?"
    r")"
)

CLASS_FILES = {
    "Warrior": "WARRIOR",
    "Paladin": "PALADIN",
    "Hunter": "HUNTER",
    "Rogue": "ROGUE",
    "Priest": "PRIEST",
    "Shaman": "SHAMAN",
    "Mage": "MAGE",
    "Warlock": "WARLOCK",
    "Monk": "MONK",
    "Druid": "DRUID",
    "Demon Hunter": "DEMONHUNTER",
    "Death Knight": "DEATHKNIGHT",
    "Evoker": "EVOKER",
}

SPEC_INDEX = {
    "Warrior": ["Arms", "Fury", "Protection"],
    "Paladin": ["Holy", "Protection", "Retribution"],
    "Hunter": ["Beast Mastery", "Marksmanship", "Survival"],
    "Rogue": ["Assassination", "Outlaw", "Subtlety"],
    "Priest": ["Discipline", "Holy", "Shadow"],
    "Shaman": ["Elemental", "Enhancement", "Restoration"],
    "Mage": ["Arcane", "Fire", "Frost"],
    "Warlock": ["Affliction", "Demonology", "Destruction"],
    "Monk": ["Brewmaster", "Mistweaver", "Windwalker"],
    "Druid": ["Balance", "Feral", "Guardian", "Restoration"],
    "Demon Hunter": ["Havoc", "Vengeance"],
    "Death Knight": ["Blood", "Frost", "Unholy"],
    "Evoker": ["Devastation", "Preservation", "Augmentation"],
}

SCAN_CODES: dict[str, int] = {
    "1": 2,
    "2": 3,
    "3": 4,
    "4": 5,
    "5": 6,
    "6": 7,
    "7": 8,
    "8": 9,
    "9": 10,
    "0": 11,
    "Q": 16,
    "W": 17,
    "E": 18,
    "R": 19,
    "T": 20,
    "Y": 21,
    "U": 22,
    "I": 23,
    "O": 24,
    "P": 25,
    "A": 30,
    "S": 31,
    "D": 32,
    "F": 33,
    "G": 34,
    "H": 35,
    "J": 36,
    "K": 37,
    "L": 38,
    "Z": 44,
    "X": 45,
    "C": 46,
    "V": 47,
    "B": 48,
    "N": 49,
    "M": 50,
    "F1": 59,
    "F2": 60,
    "F3": 61,
    "F4": 62,
    "F5": 63,
    "F6": 64,
    "F7": 65,
    "F8": 66,
    "F9": 67,
    "F10": 68,
    "F11": 87,
    "F12": 88,
    "NUMPAD7": 0x47,
    "NUMPAD8": 0x48,
    "NUMPAD9": 0x49,
    "NUMPADMINUS": 0x4A,
    "NUMPAD4": 0x4B,
    "NUMPAD5": 0x4C,
    "NUMPAD6": 0x4D,
    "NUMPADPLUS": 0x4E,
    "NUMPAD1": 0x4F,
    "NUMPAD2": 0x50,
    "NUMPAD3": 0x51,
    "NUMPAD0": 0x52,
    "NUMPADDECIMAL": 0x53,
    "NUMPADMULTIPLY": 0x37,
    "NUMPADDIVIDE": 0x135,
    "NUMPADENTER": 0x11C,
}

SCAN_TO_KEY = {scan: key for key, scan in SCAN_CODES.items()}

# These bases are never generated. The list intentionally goes a little beyond
# the exact unmodified key so modifier variants do not surprise you later.
FORBIDDEN_BASES = {
    "W",
    "A",
    "S",
    "D",
    "J",
    "L",
    "M",
    "N",
    "O",
    "P",
    "F4",
}

CANDIDATE_BASE_ORDER = [
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "0",
    "Q",
    "W",
    "E",
    "R",
    "T",
    "Y",
    "U",
    "I",
    "O",
    "P",
    "A",
    "S",
    "D",
    "F",
    "G",
    "H",
    "J",
    "K",
    "L",
    "Z",
    "X",
    "C",
    "V",
    "B",
    "N",
    "M",
    "F1",
    "F2",
    "F3",
    "F4",
    "F5",
    "F6",
    "F7",
    "F8",
    "F9",
    "F10",
    "F11",
    "F12",
    "NUMPAD1",
    "NUMPAD2",
    "NUMPAD3",
    "NUMPAD4",
    "NUMPAD5",
    "NUMPAD6",
    "NUMPAD7",
    "NUMPAD8",
    "NUMPAD9",
    "NUMPAD0",
    "NUMPADPLUS",
    "NUMPADMINUS",
    "NUMPADMULTIPLY",
    "NUMPADDIVIDE",
    "NUMPADDECIMAL",
    "NUMPADENTER",
]

NUMPAD_BASES = {
    "NUMPAD0",
    "NUMPAD1",
    "NUMPAD2",
    "NUMPAD3",
    "NUMPAD4",
    "NUMPAD5",
    "NUMPAD6",
    "NUMPAD7",
    "NUMPAD8",
    "NUMPAD9",
    "NUMPADPLUS",
    "NUMPADMINUS",
    "NUMPADMULTIPLY",
    "NUMPADDIVIDE",
    "NUMPADDECIMAL",
    "NUMPADENTER",
}
BASE_CANDIDATE_SCANS = tuple(SCAN_CODES[base] for base in CANDIDATE_BASE_ORDER)
FORBIDDEN_SCANS = {SCAN_CODES[base] for base in FORBIDDEN_BASES}
NUMPAD_SCANS = {SCAN_CODES[base] for base in NUMPAD_BASES}
DEFAULT_BIND_BASES = [
    base
    for base in CANDIDATE_BASE_ORDER
    if base not in FORBIDDEN_BASES and base not in NUMPAD_BASES
]
DEFAULT_BIND_SCANS = [
    scan
    for scan in BASE_CANDIDATE_SCANS
    if scan not in FORBIDDEN_SCANS and scan not in NUMPAD_SCANS
]
MODIFIER_ORDER = ("ALT", "CTRL", "SHIFT")
DEFAULT_ALLOWED_MODIFIERS = set(MODIFIER_ORDER)

GGL_ONLY_ACTIONS = {
    "Rotation",
    "Secondary Rotation",
    "Trinket Rotation",
    "AntiFake CC",
    "AntiFake CC Focus",
    "AntiFake Interrupt",
    "AntiFake Interrupt Focus",
    "AntiFake CC2",
    "AntiFake CC2 Focus",
}

NON_CASTABLE_NOTE_ONLY = {
    "Human Racial",
    "Potion",
}


@dataclasses.dataclass(frozen=True)
class KeyLayout:
    id: str
    name: str
    labels_by_scan: dict[int, str]
    addon_tokens_by_scan: dict[int, str]
    candidate_scans: tuple[int, ...] = BASE_CANDIDATE_SCANS
    default_enabled_scans: tuple[int, ...] = tuple(DEFAULT_BIND_SCANS)
    forbidden_scans: frozenset[int] = frozenset(FORBIDDEN_SCANS)

    def label(self, scan_code: int) -> str:
        return self.labels_by_scan.get(scan_code, SCAN_TO_KEY.get(scan_code, f"SC {scan_code:X}"))

    def addon_token(self, scan_code: int) -> str:
        return self.addon_tokens_by_scan.get(scan_code, SCAN_TO_KEY.get(scan_code, f"SC{scan_code:X}"))

    def supports_scan(self, scan_code: int) -> bool:
        return (
            scan_code in self.candidate_scans
            and scan_code in self.addon_tokens_by_scan
            and scan_code not in self.forbidden_scans
        )

    def scan_from_label(self, label: str) -> int | None:
        target = normalize_key_label(label)
        for scan_code in self.candidate_scans:
            if normalize_key_label(self.label(scan_code)) == target:
                return scan_code
            if normalize_key_label(self.addon_token(scan_code)) == target:
                return scan_code
        scan_code = SCAN_CODES.get(target)
        if scan_code is not None and scan_code in self.candidate_scans:
            return scan_code
        return None


def normalize_key_label(label: str) -> str:
    raw = label.strip().upper().replace(" ", "")
    aliases = {
        "NUM0": "NUMPAD0",
        "NUM1": "NUMPAD1",
        "NUM2": "NUMPAD2",
        "NUM3": "NUMPAD3",
        "NUM4": "NUMPAD4",
        "NUM5": "NUMPAD5",
        "NUM6": "NUMPAD6",
        "NUM7": "NUMPAD7",
        "NUM8": "NUMPAD8",
        "NUM9": "NUMPAD9",
        "NUM+": "NUMPADPLUS",
        "NUM-": "NUMPADMINUS",
        "NUM*": "NUMPADMULTIPLY",
        "NUM/": "NUMPADDIVIDE",
        "NUM.": "NUMPADDECIMAL",
        # NumLock-off labels that DirectInput / WoW Debounde may use
        "NUMPADCLEAR": "NUMPAD5",
        "CLEAR": "NUMPAD5",
        "NUMPADEND": "NUMPAD1",
        "NUMPADDOWN": "NUMPAD2",
        "NUMPADPAGEDOWN": "NUMPAD3",
        "NUMPADLEFT": "NUMPAD4",
        "NUMPADRIGHT": "NUMPAD6",
        "NUMPADHOME": "NUMPAD7",
        "NUMPADUP": "NUMPAD8",
        "NUMPADPAGEUP": "NUMPAD9",
        "NUMPADINSERT": "NUMPAD0",
        "NUMPADDELETE": "NUMPADDECIMAL",
    }
    return aliases.get(raw, raw)


def _layout_with_overrides(
    *,
    layout_id: str,
    name: str,
    label_overrides: dict[int, str] | None = None,
    addon_overrides: dict[int, str] | None = None,
    candidate_scans: tuple[int, ...] = BASE_CANDIDATE_SCANS,
    default_enabled_scans: tuple[int, ...] = tuple(DEFAULT_BIND_SCANS),
    forbidden_scans: frozenset[int] = frozenset(FORBIDDEN_SCANS),
) -> KeyLayout:
    labels = dict(SCAN_TO_KEY)
    tokens = dict(SCAN_TO_KEY)
    if label_overrides:
        labels.update(label_overrides)
    if addon_overrides:
        tokens.update(addon_overrides)
    return KeyLayout(
        id=layout_id,
        name=name,
        labels_by_scan=labels,
        addon_tokens_by_scan=tokens,
        candidate_scans=candidate_scans,
        default_enabled_scans=default_enabled_scans,
        forbidden_scans=forbidden_scans,
    )


SAFE_PROFILE_SCANS = tuple(
    scan
    for scan in BASE_CANDIDATE_SCANS
    if SCAN_TO_KEY.get(scan, "").isdigit()
    or SCAN_TO_KEY.get(scan, "").startswith("F")
    or scan in NUMPAD_SCANS
)
SAFE_PROFILE_DEFAULT_SCANS = tuple(
    scan
    for scan in SAFE_PROFILE_SCANS
    if scan not in FORBIDDEN_SCANS and scan not in NUMPAD_SCANS
)


US_QWERTY_LAYOUT = _layout_with_overrides(layout_id="us_qwerty", name="US QWERTY")
GERMAN_QWERTZ_LAYOUT = _layout_with_overrides(
    layout_id="de_qwertz",
    name="German QWERTZ",
    label_overrides={
        SCAN_CODES["Y"]: "Z",
        SCAN_CODES["Z"]: "Y",
    },
    addon_overrides={
        SCAN_CODES["Y"]: "Z",
        SCAN_CODES["Z"]: "Y",
    },
)
INTERNATIONAL_SAFE_LAYOUT = _layout_with_overrides(
    layout_id="international_safe",
    name="International Safe",
    candidate_scans=SAFE_PROFILE_SCANS,
    default_enabled_scans=SAFE_PROFILE_DEFAULT_SCANS,
)
KEY_LAYOUTS = {
    layout.id: layout
    for layout in (
        US_QWERTY_LAYOUT,
        GERMAN_QWERTZ_LAYOUT,
        INTERNATIONAL_SAFE_LAYOUT,
    )
}
KEY_LAYOUT_ORDER = tuple(KEY_LAYOUTS)
DEFAULT_KEY_LAYOUT_ID = US_QWERTY_LAYOUT.id


def key_layout_from_id(layout_id: str | None) -> KeyLayout:
    if not layout_id:
        return US_QWERTY_LAYOUT
    normalized = layout_id.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "us": "us_qwerty",
        "qwerty": "us_qwerty",
        "us_qwerty": "us_qwerty",
        "de": "de_qwertz",
        "german": "de_qwertz",
        "german_qwertz": "de_qwertz",
        "qwertz": "de_qwertz",
        "safe": "international_safe",
        "international": "international_safe",
        "international_safe": "international_safe",
    }
    return KEY_LAYOUTS.get(aliases.get(normalized, normalized), US_QWERTY_LAYOUT)


def scan_id(scan_code: int) -> str:
    return f"SC_{scan_code:X}"


def scan_from_id(raw: str | int | None) -> int | None:
    if isinstance(raw, int):
        return raw if raw in SCAN_TO_KEY else None
    if raw is None:
        return None
    value = str(raw).strip().upper()
    if not value:
        return None
    if value.startswith("SC_"):
        try:
            return int(value[3:], 16)
        except ValueError:
            return None
    if value.startswith("SC"):
        try:
            return int(value[2:], 16)
        except ValueError:
            return None
    return SCAN_CODES.get(normalize_key_label(value))


def scans_from_saved_keys(raw: object, layout: KeyLayout | None = None) -> set[int]:
    selected_layout = layout or US_QWERTY_LAYOUT
    if not isinstance(raw, list):
        return set(selected_layout.default_enabled_scans)
    out: set[int] = set()
    for item in raw:
        scan_code = scan_from_id(item)
        if scan_code is None and isinstance(item, str):
            scan_code = selected_layout.scan_from_label(item)
        if scan_code is not None:
            out.add(scan_code)
    return out


@dataclasses.dataclass(frozen=True)
class KeyBind:
    scan_code: int
    mods: tuple[str, ...] = ()

    def __init__(self, scan_code: int | str, mods: tuple[str, ...] = ()) -> None:
        if isinstance(scan_code, str):
            resolved = scan_from_id(scan_code)
            if resolved is None:
                raise ValueError(f"unknown key {scan_code!r}")
            scan_code = resolved
        object.__setattr__(self, "scan_code", int(scan_code))
        object.__setattr__(self, "mods", tuple(mods))

    @property
    def base(self) -> str:
        return SCAN_TO_KEY.get(self.scan_code, f"SC{self.scan_code:X}")

    def debounce(self, layout: KeyLayout | None = None) -> str:
        selected_layout = layout or US_QWERTY_LAYOUT
        parts = [m for m in ("ALT", "CTRL", "SHIFT") if m in self.mods]
        parts.append(selected_layout.addon_token(self.scan_code))
        return "-".join(parts)

    def human(self, layout: KeyLayout | None = None) -> str:
        selected_layout = layout or US_QWERTY_LAYOUT
        parts = [m.title() for m in ("ALT", "CTRL", "SHIFT") if m in self.mods]
        parts.append(selected_layout.label(self.scan_code))
        return "+".join(parts)

    def ggl(self, suffix: str) -> str:
        mod = ""
        if "CTRL" in self.mods:
            mod += "^"
        if "ALT" in self.mods:
            mod += "!"
        if "SHIFT" in self.mods:
            mod += "+"
        return f"{mod}sc{self.scan_code:X}_{suffix}"


@dataclasses.dataclass
class GglEntry:
    section: str
    line_index: int
    name: str
    value: str
    tail: str
    full_line: str


@dataclasses.dataclass
class PlannedBind:
    action: GglEntry
    key: KeyBind | None
    ggl_token: str | None
    source: str
    macro: str | None
    icon: int
    warning: str = ""
    debounce_name: str | None = None


@dataclasses.dataclass(frozen=True)
class MacroOverride:
    name: str
    macro: str | None = None


class LuaParseError(ValueError):
    pass


def new_random_seed() -> str:
    return f"{random.SystemRandom().randrange(16**12):012x}"


class LuaParser:
    def __init__(self, text: str, pos: int = 0):
        self.text = text
        self.pos = pos
        self.depth = 0

    def parse_value(self) -> Any:
        self._skip_ws()
        if self.text.startswith("-math.huge", self.pos):
            self.pos += len("-math.huge")
            return -math.inf
        if self.text.startswith("math.huge", self.pos):
            self.pos += len("math.huge")
            return math.inf
        if self.text.startswith("0/0", self.pos):
            self.pos += len("0/0")
            return math.nan
        ch = self._peek()
        if ch == "{":
            return self._parse_table()
        if ch in ('"', "'"):
            return self._parse_string()
        if ch and (ch in "-." or ch.isdigit()):
            return self._parse_number()
        if self.text.startswith("inf", self.pos) or self.text.startswith("nan", self.pos):
            return self._parse_number()
        ident = self._parse_identifier()
        if ident == "true":
            return True
        if ident == "false":
            return False
        if ident == "nil":
            return None
        raise LuaParseError(f"Unexpected identifier {ident!r} at {self.pos}")

    def _parse_table(self) -> dict[Any, Any]:
        self.depth += 1
        if self.depth > MAX_LUA_DEPTH:
            self.depth -= 1
            raise LuaParseError(f"Lua table nesting is too deep at {self.pos}")
        self._expect("{")
        tbl: dict[Any, Any] = {}
        next_index = 1
        try:
            while True:
                self._skip_ws()
                if self._peek() == "}":
                    self.pos += 1
                    return tbl
                if self._peek() == "[":
                    self.pos += 1
                    key = self.parse_value()
                    self._skip_ws()
                    self._expect("]")
                    self._skip_ws()
                    self._expect("=")
                    value = self.parse_value()
                    tbl[key] = value
                else:
                    saved = self.pos
                    key: str | None = None
                    try:
                        ident = self._parse_identifier()
                        self._skip_ws()
                        if self._peek() == "=":
                            self.pos += 1
                            key = ident
                            value = self.parse_value()
                            tbl[key] = value
                        else:
                            self.pos = saved
                    except LuaParseError:
                        self.pos = saved

                    if key is None:
                        value = self.parse_value()
                        while next_index in tbl:
                            next_index += 1
                        tbl[next_index] = value
                        next_index += 1

                self._skip_ws()
                if self._peek() in ",;":
                    self.pos += 1
        finally:
            self.depth -= 1

    def _parse_string(self) -> str:
        quote = self._peek()
        self.pos += 1
        out: list[str] = []
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            self.pos += 1
            if ch == quote:
                return "".join(out)
            if ch == "\\":
                if self.pos >= len(self.text):
                    raise LuaParseError("Trailing string escape")
                esc = self.text[self.pos]
                self.pos += 1
                if esc.isdigit():
                    digits = [esc]
                    while (
                        len(digits) < 3
                        and self.pos < len(self.text)
                        and self.text[self.pos].isdigit()
                    ):
                        digits.append(self.text[self.pos])
                        self.pos += 1
                    out.append(chr(int("".join(digits), 10)))
                elif esc == "n":
                    out.append("\n")
                elif esc == "r":
                    out.append("\r")
                elif esc == "t":
                    out.append("\t")
                elif esc == "a":
                    out.append("\a")
                elif esc == "b":
                    out.append("\b")
                elif esc == "f":
                    out.append("\f")
                elif esc == "v":
                    out.append("\v")
                elif esc == "z":
                    while self.pos < len(self.text) and self.text[self.pos].isspace():
                        self.pos += 1
                elif esc in ('"', "'", "\\"):
                    out.append(esc)
                else:
                    out.append(esc)
            else:
                out.append(ch)
        raise LuaParseError("Unterminated string")

    def _parse_number(self) -> int | float:
        for token, value in (("-inf", -math.inf), ("inf", math.inf), ("nan", math.nan)):
            if self.text.startswith(token, self.pos):
                self.pos += len(token)
                return value
        match = _NUM_RE.match(self.text, self.pos)
        if not match:
            raise LuaParseError(f"Expected number at {self.pos}")
        raw = match.group(0)
        self.pos += len(raw)
        unsigned = raw[1:] if raw.startswith("-") else raw
        if unsigned.lower().startswith("0x"):
            return float.fromhex(raw) if "." in raw or "p" in raw.lower() else int(raw, 16)
        return float(raw) if any(ch in raw for ch in ".eE") else int(raw)

    def _parse_identifier(self) -> str:
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", self.text[self.pos :])
        if not match:
            raise LuaParseError(f"Expected identifier at {self.pos}")
        raw = match.group(0)
        self.pos += len(raw)
        return raw

    def _skip_ws(self) -> None:
        while self.pos < len(self.text):
            if self.text.startswith("--[", self.pos):
                match = re.match(r"--\[(=*)\[", self.text[self.pos :])
                if match:
                    close = "]" + match.group(1) + "]"
                    end = self.text.find(close, self.pos + len(match.group(0)))
                    self.pos = len(self.text) if end == -1 else end + len(close)
                else:
                    end = self.text.find("\n", self.pos)
                    self.pos = len(self.text) if end == -1 else end + 1
            elif self.text.startswith("--", self.pos):
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end == -1 else end + 1
            elif self.text[self.pos].isspace():
                self.pos += 1
            else:
                break

    def _peek(self) -> str:
        if self.pos >= len(self.text):
            return ""
        return self.text[self.pos]

    def _expect(self, expected: str) -> None:
        if self._peek() != expected:
            raise LuaParseError(f"Expected {expected!r} at {self.pos}")
        self.pos += 1


def lua_string(value: str) -> str:
    value = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{value}"'


def lua_key(key: Any) -> str:
    if isinstance(key, bool):
        return "[true]" if key else "[false]"
    if isinstance(key, int):
        return f"[{key}]"
    return f"[{lua_string(str(key))}]"


def dump_lua(value: Any, indent: int = 0, depth: int = 0) -> str:
    if depth > MAX_LUA_DEPTH:
        raise ValueError("Lua table nesting is too deep to write safely")
    pad = " " * indent
    inner = " " * (indent + 4)
    if isinstance(value, dict):
        lines = ["{"]
        for key, item in value.items():
            lines.append(f"{inner}{lua_key(key)} = {dump_lua(item, indent + 4, depth + 1)},")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    if isinstance(value, str):
        return lua_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nil"
    if isinstance(value, float):
        if math.isnan(value):
            return "0/0"
        if math.isinf(value):
            return "math.huge" if value > 0 else "-math.huge"
    return str(value)


def read_text(path: Path) -> tuple[str, str, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        encodings = (("utf-16", "utf-16-le-bom"),)
    elif raw.startswith(b"\xfe\xff"):
        encodings = (("utf-16", "utf-16-be-bom"),)
    elif raw.startswith(b"\xef\xbb\xbf"):
        encodings = (("utf-8-sig", "utf-8-sig"),)
    elif raw[:200].count(b"\x00") > 20:
        encodings = (("utf-16-le", "utf-16-le"), ("utf-16", "utf-16-le-bom"))
    else:
        encodings = (("utf-8", "utf-8"), ("cp1252", "utf-8"))

    write_encoding = "utf-8"
    for decode_encoding, candidate_write_encoding in encodings:
        try:
            text = raw.decode(decode_encoding)
            write_encoding = candidate_write_encoding
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
        write_encoding = "utf-8"
    newline = "\r\n" if "\r\n" in text else "\n"
    return text, write_encoding, newline


def write_text(path: Path, text: str, encoding: str) -> None:
    if encoding == "utf-16-le-bom":
        data = b"\xff\xfe" + text.encode("utf-16-le")
    elif encoding == "utf-16-be-bom":
        data = b"\xfe\xff" + text.encode("utf-16-be")
    else:
        try:
            data = text.encode(encoding)
        except UnicodeEncodeError:
            data = text.encode("utf-8")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    temp = path.with_name(f".{path.name}.tmp-{stamp}")
    try:
        temp.write_bytes(data)
        temp.replace(path)
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


def backup_file(path: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    counter = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.bak-{stamp}-{counter}")
        counter += 1
    shutil.copy2(path, backup)
    return backup


def parse_debounce_vars(text: str) -> dict[Any, Any]:
    match = re.search(r"\bDebounceVars\s*=", text)
    if not match:
        if re.search(r"\bDebounceVarsPerChar\s*=", text):
            raise LuaParseError(
                "This is the per-character Debounce.lua file. Choose the account-wide "
                "WTF\\Account\\<account>\\SavedVariables\\Debounce.lua file instead."
            )
        raise LuaParseError("Could not find DebounceVars assignment")
    parser = LuaParser(text, match.end())
    value = parser.parse_value()
    if not isinstance(value, dict):
        raise LuaParseError("DebounceVars is not a table")
    return value


def parse_bindpad_vars(text: str) -> dict[Any, Any]:
    match = re.search(r"\bBindPadVars\s*=", text)
    if not match:
        raise LuaParseError("Could not find BindPadVars assignment")
    parser = LuaParser(text, match.end())
    value = parser.parse_value()
    if not isinstance(value, dict):
        raise LuaParseError("BindPadVars is not a table")
    return value


def bindpad_profile_keys(vars_table: dict[Any, Any]) -> list[str]:
    return sorted(
        key
        for key, value in vars_table.items()
        if isinstance(key, str) and key.startswith("PROFILE_") and isinstance(value, dict)
    )


def bindpad_profile_label(profile_key: str) -> str:
    raw = profile_key.removeprefix("PROFILE_")
    parts = raw.split("_", 1)
    if len(parts) == 2:
        return f"{parts[0]} / {parts[1]}"
    return raw or profile_key


def bindpad_action(name: str) -> str:
    return f"CLICK BindPadMacro:{name}"


def bindpad_binding_tables(
    vars_table: dict[Any, Any],
    profile_key: str | None,
    spec_index: int | None,
) -> list[dict[Any, Any]]:
    tables: list[dict[Any, Any]] = []
    general = vars_table.get("GeneralKeyBindings")
    if isinstance(general, dict):
        tables.append(general)
    if profile_key and spec_index is not None:
        character = vars_table.get(profile_key)
        if isinstance(character, dict):
            profile_for = character.get("profileForTalentGroup")
            profile_num = spec_index
            if isinstance(profile_for, dict):
                profile_num = profile_for.get(spec_index, spec_index)
            profile = character.get(profile_num)
            if isinstance(profile, dict):
                all_keys = profile.get("AllKeyBindings")
                if isinstance(all_keys, dict):
                    tables.append(all_keys)
    return tables


def bindpad_reserved_keys(
    vars_table: dict[Any, Any],
    profile_key: str | None,
    spec_index: int | None,
    planned_macro_names: set[str],
    layout: KeyLayout | None = None,
) -> set[KeyBind]:
    selected_layout = layout or US_QWERTY_LAYOUT
    planned_actions = {bindpad_action(name) for name in planned_macro_names}
    out: set[KeyBind] = set()
    for table in bindpad_binding_tables(vars_table, profile_key, spec_index):
        for key, action in table.items():
            if not isinstance(key, str) or not isinstance(action, str):
                continue
            if action in planned_actions:
                continue
            try:
                out.add(parse_keybind_label(key, selected_layout))
            except ValueError:
                continue
    return out


def parse_ggl_entries(text: str) -> tuple[dict[str, list[GglEntry]], list[str]]:
    lines = text.splitlines()
    section = ""
    sections: dict[str, list[GglEntry]] = {}
    for index, line in enumerate(lines):
        sec_match = re.match(r"^\[([^\]]+)\]\s*$", line)
        if sec_match:
            section = sec_match.group(1)
            sections.setdefault(section, [])
            continue
        if not section or line.lstrip().startswith(";") or "=" not in line:
            continue
        left, rhs = line.split("=", 1)
        name = left.strip()
        if not name:
            continue
        if ";" in rhs:
            value, tail_part = rhs.split(";", 1)
            tail = ";" + tail_part
        else:
            value = rhs
            tail = ""
        sections.setdefault(section, []).append(
            GglEntry(section, index, name, value.strip(), tail, line)
        )
    return sections, lines


def collect_ggl_reserved_keys(
    sections: dict[str, list[GglEntry]],
    section_names: set[str],
    excluded_entries: list[GglEntry] | None = None,
) -> set[KeyBind]:
    excluded_lines = {entry.line_index for entry in excluded_entries or []}
    out: set[KeyBind] = set()
    for section_name in section_names:
        for entry in sections.get(section_name, []):
            if entry.line_index in excluded_lines or not entry.value:
                continue
            key, _suffix = ggl_token_to_key(entry.value)
            if key:
                out.add(key)
    return out


def set_ggl_line_value(line: str, value: str) -> str:
    eq = line.find("=")
    if eq == -1:
        return line
    semi = line.find(";", eq + 1)
    if semi == -1:
        return line[: eq + 1] + value
    return line[: eq + 1] + value + line[semi:]


def rewrite_ggl_lines(
    lines: list[str],
    plans: list[PlannedBind],
    overwrite: bool,
    cleanup_entries: list[GglEntry] | None = None,
) -> list[str]:
    updated = list(lines)
    planned_line_indices = {plan.action.line_index for plan in plans}

    if overwrite and cleanup_entries:
        for entry in cleanup_entries:
            if entry.line_index not in planned_line_indices:
                updated[entry.line_index] = set_ggl_line_value(updated[entry.line_index], "")

    for plan in plans:
        if not plan.ggl_token:
            if overwrite:
                updated[plan.action.line_index] = set_ggl_line_value(updated[plan.action.line_index], "")
            continue
        entry = plan.action
        if entry.value and not overwrite and plan.source == "current":
            continue
        updated[entry.line_index] = set_ggl_line_value(updated[entry.line_index], plan.ggl_token)
    return updated


def ggl_token_to_key(token: str) -> tuple[KeyBind | None, str | None]:
    match = re.fullmatch(
        r"(?P<mods>[\^\!\+]*?)sc(?P<scan>[0-9A-Fa-f]+)(?:_(?P<suffix>\d+))?",
        token.strip(),
    )
    if not match:
        return None, None
    scan = int(match.group("scan"), 16)
    if scan not in SCAN_TO_KEY:
        return None, match.group("suffix")
    mods_raw = match.group("mods")
    mods: list[str] = []
    if "!" in mods_raw:
        mods.append("ALT")
    if "^" in mods_raw:
        mods.append("CTRL")
    if "+" in mods_raw:
        mods.append("SHIFT")
    return KeyBind(scan, tuple(mods)), match.group("suffix")


def parse_keybind_label(label: str, layout: KeyLayout | None = None) -> KeyBind:
    selected_layout = layout or US_QWERTY_LAYOUT
    raw = label.strip()
    if not raw:
        raise ValueError("empty keybind")
    parts = [part.strip() for part in re.split(r"[+-]", raw) if part.strip()]
    if not parts:
        raise ValueError("empty keybind")
    mods: set[str] = set()
    base = ""
    aliases = {"ALT": "ALT", "CTRL": "CTRL", "CONTROL": "CTRL", "SHIFT": "SHIFT"}
    for part in parts:
        name = part.upper()
        if name in aliases:
            mods.add(aliases[name])
        elif not base:
            base = name
        else:
            raise ValueError(f"too many base keys in {label!r}")
    if not base:
        raise ValueError(f"missing base key in {label!r}")
    scan_code = selected_layout.scan_from_label(base)
    if scan_code is None:
        raise ValueError(f"unknown base key {base!r} in {label!r}")
    return KeyBind(scan_code, tuple(mod for mod in MODIFIER_ORDER if mod in mods))


def parse_keybind_set(raw: str | None, layout: KeyLayout | None = None) -> set[KeyBind]:
    selected_layout = layout or US_QWERTY_LAYOUT
    if not raw:
        return set()
    out: set[KeyBind] = set()
    for item in re.split(r"[,;\n]+", raw):
        item = item.strip()
        if item:
            out.add(parse_keybind_label(item, selected_layout))
    return out


def find_suffix(sections: dict[str, list[GglEntry]], fallback: dict[str, list[GglEntry]] | None) -> str | None:
    for source in (sections, fallback or {}):
        for entries in source.values():
            for entry in entries:
                _, suffix = ggl_token_to_key(entry.value)
                if suffix:
                    return suffix
    return None


def action_restriction(entry: GglEntry) -> set[str]:
    text = f"{entry.name} {entry.tail}".lower()
    disallowed: set[str] = set()
    if "don't use alt ctrl" in text or "dont use alt ctrl" in text:
        disallowed.update({"ALT", "CTRL"})
    elif "don't use ctrl" in text or "dont use ctrl" in text:
        disallowed.add("CTRL")
    elif "don't use alt" in text or "dont use alt" in text:
        disallowed.add("ALT")
    return disallowed


def is_key_allowed(
    key: KeyBind,
    entry: GglEntry | None = None,
    enabled_scans: set[int] | None = None,
    enabled_mods: set[str] | None = None,
    allow_unmodified: bool = True,
    blocked_keys: set[KeyBind] | None = None,
    layout: KeyLayout | None = None,
) -> bool:
    selected_layout = layout or US_QWERTY_LAYOUT
    if not selected_layout.supports_scan(key.scan_code):
        return False
    if blocked_keys and key in blocked_keys:
        return False
    if enabled_scans is not None and key.scan_code not in enabled_scans:
        return False
    if enabled_mods is not None and any(mod not in enabled_mods for mod in key.mods):
        return False
    if not key.mods and not allow_unmodified:
        return False
    if entry:
        blocked_mods = action_restriction(entry)
        if any(mod in key.mods for mod in blocked_mods):
            return False
    return True


def key_candidates(
    enabled_scans: set[int] | None = None,
    random_seed: str | None = None,
    enabled_mods: set[str] | None = None,
    allow_unmodified: bool = True,
    blocked_keys: set[KeyBind] | None = None,
    layout: KeyLayout | None = None,
) -> list[KeyBind]:
    selected_layout = layout or US_QWERTY_LAYOUT
    if enabled_scans is None:
        enabled_scans = set(selected_layout.default_enabled_scans)
    if enabled_mods is None:
        enabled_mods = set(DEFAULT_ALLOWED_MODIFIERS)
    mod_order = [
        (),
        ("ALT",),
        ("CTRL",),
        ("SHIFT",),
        ("ALT", "CTRL"),
        ("ALT", "SHIFT"),
        ("CTRL", "SHIFT"),
        ("ALT", "CTRL", "SHIFT"),
    ]
    scan_order = [
        scan
        for scan in selected_layout.candidate_scans
        if scan in enabled_scans and selected_layout.supports_scan(scan)
    ]
    if random_seed is not None:
        random.Random(str(random_seed)).shuffle(scan_order)

    out: list[KeyBind] = []
    for mods in mod_order:
        if mods and any(mod not in enabled_mods for mod in mods):
            continue
        if not mods and not allow_unmodified:
            continue
        for scan_code in scan_order:
            key = KeyBind(scan_code, mods)
            if is_key_allowed(
                key,
                enabled_scans=enabled_scans,
                enabled_mods=enabled_mods,
                allow_unmodified=allow_unmodified,
                blocked_keys=blocked_keys,
                layout=selected_layout,
            ):
                out.append(key)
    return out


def section_from_config_json(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    raw_class = str(data.get("player_class", "")).replace("_", " ").title()
    raw_spec = str(data.get("player_spec", "")).replace("_", " ").title()
    for class_name, specs in SPEC_INDEX.items():
        if class_name.lower() == raw_class.lower():
            for spec in specs:
                if spec.lower() == raw_spec.lower():
                    return f"{class_name} - {spec}"
    return None


def resolve_section(args: argparse.Namespace) -> str:
    if args.section:
        return args.section
    inferred = section_from_config_json(args.config_json)
    if inferred:
        return inferred
    raise SystemExit("Pass --section, for example: --section \"Warrior - Fury\"")


def retail_debounce_target_from_section(section: str) -> tuple[str, int | None] | None:
    if section.lower() == "general":
        return "GENERAL", None
    if " - " not in section:
        return None
    class_name, spec_name = section.split(" - ", 1)
    class_file = CLASS_FILES.get(class_name)
    if not class_file:
        return None
    specs = SPEC_INDEX[class_name]
    try:
        spec_index = [s.lower() for s in specs].index(spec_name.lower()) + 1
    except ValueError:
        return None
    return class_file, spec_index


def section_to_debounce_target(section: str) -> tuple[str, int | None]:
    target = retail_debounce_target_from_section(section)
    if target:
        return target
    if " - " not in section:
        raise SystemExit(
            f"Cannot infer Debounce class/spec from section {section!r}. "
            "Use a retail section like \"Warrior - Fury\"."
        )
    raise SystemExit(f"Unsupported class/spec in section {section!r}")


def bindpad_spec_index_for_section(section: str) -> int | None:
    target = retail_debounce_target_from_section(section)
    if target:
        _class_file, spec_index = target
        return spec_index
    if section.lower() == "general":
        return None
    return 1


def select_entries(
    sections: dict[str, list[GglEntry]], section: str, names: set[str] | None, limit: int | None
) -> list[GglEntry]:
    if section not in sections:
        available = ", ".join(sorted(sections))
        raise SystemExit(f"Section {section!r} not found. Available sections: {available}")
    entries = sections[section]
    if names is not None:
        entries = [entry for entry in entries if entry.name in names]
        missing = sorted(names - {entry.name for entry in entries})
        if missing:
            print("Warning: action names not found: " + ", ".join(missing), file=sys.stderr)
    if limit is not None:
        entries = entries[:limit]
    return entries


def extract_icon(entry: GglEntry) -> int:
    text = entry.tail
    match = re.search(r"(?:textureID|IconID)\s*[:=]?\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return DEFAULT_ICON


def macro_from_entry(entry: GglEntry) -> str | None:
    name = entry.name.strip()
    if name.startswith("START ") or name in GGL_ONLY_ACTIONS:
        return None

    description = entry.tail[1:].strip() if entry.tail.startswith(";") else entry.tail.strip()
    if description:
        normalized = description.replace("\u00a7", "\n")
        lines = [line.strip() for line in normalized.splitlines()]
        macro_lines: list[str] = []
        for line in lines:
            if not line:
                if macro_lines:
                    break
                continue
            lower = line.lower()
            if lower.startswith(("note:", "macro for ", "only if ", "for retail", "allitemids:")):
                break
            if line.startswith("/"):
                macro_lines.append(line)
            elif macro_lines:
                break
        if macro_lines:
            return "\n".join(macro_lines)

    if name in NON_CASTABLE_NOTE_ONLY or name.startswith("Universal"):
        return None
    if " Member" in name or " Unit" in name or " Arena" in name or name.startswith("Target "):
        return None
    if "|" in name:
        parts = [part.strip() for part in name.split("|") if part.strip()]
        if parts:
            return "\n".join(f"/cast {part}" for part in parts)
    if re.search(r"[A-Za-z]", name):
        return f"/cast {name}"
    return None


def macro_with_showtooltip(macro: str | None, tooltip_name: str) -> str | None:
    if not macro:
        return None
    lines = macro.strip().splitlines()
    if not lines:
        return None
    first_content = next((line.strip() for line in lines if line.strip()), "")
    if first_content.lower().startswith("#showtooltip"):
        return "\n".join(lines)
    tooltip = tooltip_name.strip()
    if not tooltip:
        return "\n".join(lines)
    return "#showtooltip " + tooltip + "\n" + "\n".join(lines)


def map_seed_entries(seed_sections: dict[str, list[GglEntry]] | None, section: str) -> dict[str, GglEntry]:
    if not seed_sections or section not in seed_sections:
        return {}
    return {entry.name: entry for entry in seed_sections[section]}


def plan_bindings(
    entries: list[GglEntry],
    seed_map: dict[str, GglEntry],
    suffix: str,
    overwrite: bool,
    enabled_scans: set[int] | None = None,
    random_seed: str | None = None,
    enabled_mods: set[str] | None = None,
    allow_unmodified: bool = True,
    blocked_keys: set[KeyBind] | None = None,
    macro_overrides: dict[str, MacroOverride] | None = None,
    layout: KeyLayout | None = None,
) -> list[PlannedBind]:
    selected_layout = layout or US_QWERTY_LAYOUT
    candidates = key_candidates(
        enabled_scans,
        random_seed,
        enabled_mods,
        allow_unmodified,
        blocked_keys,
        selected_layout,
    )
    used_keys: set[KeyBind] = set()
    current_keys: dict[int, KeyBind] = {}
    current_warnings: dict[int, str] = {}

    if not overwrite:
        for entry in entries:
            if not entry.value:
                continue
            key, _ = ggl_token_to_key(entry.value)
            if not key or not is_key_allowed(
                key,
                entry,
                enabled_scans,
                enabled_mods,
                allow_unmodified,
                blocked_keys,
                selected_layout,
            ):
                current_warnings[entry.line_index] = (
                    "Existing GGL token is not decodable or violates the safety/modifier/reserved rules"
                )
                continue
            if key in used_keys:
                current_warnings[entry.line_index] = "Existing GGL token duplicates another selected key"
                continue
            current_keys[entry.line_index] = key
            used_keys.add(key)

    plans: list[PlannedBind] = []

    for entry in entries:
        warning = current_warnings.get(entry.line_index, "")
        chosen: KeyBind | None = None
        source = "generated"

        if entry.value and not overwrite:
            key = current_keys.get(entry.line_index)
            if key:
                chosen = key
                source = "current"
            elif entry.line_index in current_warnings:
                plans.append(
                    PlannedBind(
                        action=entry,
                        key=None,
                        ggl_token=None,
                        source="current-invalid",
                        macro=None,
                        icon=extract_icon(entry),
                        warning=warning,
                    )
                )
                continue

        if chosen is None and random_seed is None:
            seed_entry = seed_map.get(entry.name)
            if seed_entry and seed_entry.value:
                seed_key, _ = ggl_token_to_key(seed_entry.value)
                if (
                    seed_key
                    and seed_key not in used_keys
                    and is_key_allowed(
                        seed_key,
                        entry,
                        enabled_scans,
                        enabled_mods,
                        allow_unmodified,
                        blocked_keys,
                        selected_layout,
                    )
                ):
                    chosen = seed_key
                    source = "seed"
                    used_keys.add(seed_key)

        if chosen is None:
            for candidate in candidates:
                if candidate in used_keys:
                    continue
                if not is_key_allowed(
                    candidate,
                    entry,
                    enabled_scans,
                    enabled_mods,
                    allow_unmodified,
                    blocked_keys,
                    selected_layout,
                ):
                    continue
                chosen = candidate
                source = "generated"
                used_keys.add(candidate)
                break

        if chosen is None:
            plans.append(
                PlannedBind(
                    action=entry,
                    key=None,
                    ggl_token=None,
                    source="none",
                    macro=None,
                    icon=extract_icon(entry),
                    warning=warning or "No safe key left to assign",
                )
            )
            continue

        override = macro_overrides.get(entry.name) if macro_overrides else None
        macro = macro_from_entry(entry)
        debounce_name = None
        if override:
            debounce_name = override.name.strip()
            if override.macro is not None and override.macro.strip():
                macro = override.macro.strip()
            elif debounce_name:
                macro = f"/cast {debounce_name}"
        macro_name = debounce_name or entry.name
        macro = macro_with_showtooltip(macro, macro_name)

        plans.append(
            PlannedBind(
                action=entry,
                key=chosen,
                ggl_token=chosen.ggl(suffix),
                source=source,
                macro=macro,
                icon=extract_icon(entry),
                warning=warning,
                debounce_name=debounce_name or None,
            )
        )

    return plans


def layer_to_list(layer: Any) -> list[Any]:
    if not isinstance(layer, dict):
        return []
    numeric = [(key, value) for key, value in layer.items() if isinstance(key, int) and key >= 1]
    return [value for _, value in sorted(numeric, key=lambda item: item[0])]


def list_to_layer(actions: list[Any]) -> dict[int, Any]:
    return {index + 1: action for index, action in enumerate(actions)}


def clear_debounce_target(
    vars_table: dict[Any, Any],
    class_file: str,
    spec_index: int | None,
) -> int:
    if class_file == "GENERAL":
        existing = layer_to_list(vars_table.get("GENERAL", {}))
        vars_table["GENERAL"] = {}
    else:
        class_table = vars_table.setdefault(class_file, {})
        if not isinstance(class_table, dict):
            class_table = {}
            vars_table[class_file] = class_table
        if spec_index is None:
            raise ValueError("spec_index is required for class-specific Debounce target")
        existing = layer_to_list(class_table.get(spec_index, {}))
        class_table[spec_index] = {}

    vars_table["dbver"] = 2
    vars_table.setdefault("options", {}).setdefault("blizzframes", {})
    vars_table.setdefault("ui", {})
    vars_table.setdefault("customStates", {})
    return len(existing)


def update_debounce(
    vars_table: dict[Any, Any],
    class_file: str,
    spec_index: int | None,
    plans: list[PlannedBind],
    replace_managed: bool,
    cleanup_names: set[str] | None = None,
    cleanup_keys: set[str] | None = None,
    layout: KeyLayout | None = None,
) -> int:
    selected_layout = layout or US_QWERTY_LAYOUT
    new_actions = []
    planned_names = set()
    for plan in plans:
        if not plan.key or not plan.macro:
            continue
        debounce_name = plan.debounce_name or plan.action.name
        planned_names.add(plan.action.name)
        planned_names.add(debounce_name)
        new_actions.append(
            {
                "type": "macrotext",
                "name": f"{MANAGED_PREFIX}{debounce_name}",
                "value": plan.macro,
                "icon": plan.icon,
                "key": plan.key.debounce(selected_layout),
                "source": MANAGED_SOURCE,
            }
        )

    names_to_remove = set(cleanup_names or planned_names)
    names_to_remove.update(planned_names)
    keys_to_remove = set(cleanup_keys or ())
    keys_to_remove.update(plan.key.debounce(selected_layout) for plan in plans if plan.key)

    if class_file == "GENERAL":
        layer = vars_table.setdefault("GENERAL", {})
    else:
        class_table = vars_table.setdefault(class_file, {})
        if not isinstance(class_table, dict):
            class_table = {}
            vars_table[class_file] = class_table
        if spec_index is None:
            raise ValueError("spec_index is required for class-specific Debounce target")
        layer = class_table.setdefault(spec_index, {})

    existing = layer_to_list(layer)
    if replace_managed:
        existing = [
            action
            for action in existing
            if not (
                isinstance(action, dict)
                and (
                    action.get("source") == MANAGED_SOURCE
                    or action.get("key") in keys_to_remove
                    or (
                        isinstance(action.get("name"), str)
                        and (
                            action["name"].startswith(OLD_MANAGED_PREFIX)
                            or action["name"] in names_to_remove
                        )
                    )
                )
            )
        ]
    merged = existing + new_actions
    replacement = list_to_layer(merged)

    if class_file == "GENERAL":
        vars_table["GENERAL"] = replacement
    else:
        vars_table[class_file][spec_index] = replacement

    vars_table["dbver"] = 2
    vars_table.setdefault("options", {}).setdefault("blizzframes", {})
    vars_table.setdefault("ui", {})
    vars_table.setdefault("customStates", {})
    return len(new_actions)


def bindpad_numeric_slots(table: dict[Any, Any]) -> list[Any]:
    slots = [(key, value) for key, value in table.items() if isinstance(key, int) and key >= 1]
    return [value for _, value in sorted(slots, key=lambda item: item[0])]


def bindpad_name_cleanup_variants(names: set[str]) -> set[str]:
    variants = set(names)
    for name in names:
        if name.startswith(OLD_MANAGED_PREFIX):
            variants.add(name.removeprefix(OLD_MANAGED_PREFIX))
        else:
            variants.add(OLD_MANAGED_PREFIX + name)
    return variants


def bindpad_action_cleanup_variants(names: set[str]) -> set[str]:
    return {bindpad_action(name) for name in bindpad_name_cleanup_variants(names)}


def bindpad_character_tabs(profile: dict[Any, Any]) -> list[dict[Any, Any]]:
    tabs: list[dict[Any, Any]] = []
    for key, value in profile.items():
        if isinstance(key, str) and key.startswith("CharacterSpecificTab") and isinstance(value, dict):
            tabs.append(value)
    return tabs


def replace_bindpad_slots(
    table: dict[Any, Any],
    new_slots: list[dict[Any, Any]],
    cleanup_names: set[str],
) -> set[str]:
    cleanup_name_variants = bindpad_name_cleanup_variants(cleanup_names)
    planned_actions = bindpad_action_cleanup_variants(cleanup_names)
    removed_actions: set[str] = set(planned_actions)
    existing: list[Any] = []
    for slot in bindpad_numeric_slots(table):
        if (
            isinstance(slot, dict)
            and (
                slot.get("source") == MANAGED_SOURCE
                or slot.get("name") in cleanup_name_variants
                or slot.get("action") in planned_actions
            )
        ):
            action = slot.get("action")
            if isinstance(action, str):
                removed_actions.add(action)
            continue
        existing.append(slot)

    for key in [key for key in table if isinstance(key, int) and key >= 1]:
        del table[key]

    merged = existing + new_slots
    for index, slot in enumerate(merged, start=1):
        table[index] = slot
    table["numSlot"] = max(int(table.get("numSlot") or BINDPAD_DEFAULT_SLOTS), len(merged), BINDPAD_DEFAULT_SLOTS)
    return removed_actions


def remove_bindpad_actions(binding_table: dict[Any, Any], managed_actions: set[str]) -> None:
    if not managed_actions:
        return
    for key in [key for key, action in binding_table.items() if action in managed_actions]:
        del binding_table[key]


def remove_bindpad_keys(binding_table: dict[Any, Any], keys: set[str]) -> None:
    if not keys:
        return
    for key in [key for key in binding_table if isinstance(key, str) and key in keys]:
        del binding_table[key]


def ensure_bindpad_profile(
    vars_table: dict[Any, Any],
    profile_key: str,
    spec_index: int,
) -> tuple[dict[Any, Any], dict[Any, Any], int]:
    character = vars_table.setdefault(profile_key, {})
    if not isinstance(character, dict):
        character = {}
        vars_table[profile_key] = character
    profile_for = character.setdefault("profileForTalentGroup", {})
    if not isinstance(profile_for, dict):
        profile_for = {}
        character["profileForTalentGroup"] = profile_for
    profile_num = profile_for.get(spec_index, spec_index)
    if not isinstance(profile_num, int):
        profile_num = spec_index
    profile_for[spec_index] = profile_num

    profile = character.setdefault(profile_num, {})
    if not isinstance(profile, dict):
        profile = {}
        character[profile_num] = profile
    all_keys = profile.setdefault("AllKeyBindings", {})
    if not isinstance(all_keys, dict):
        all_keys = {}
        profile["AllKeyBindings"] = all_keys
    tab = profile.setdefault("CharacterSpecificTab1", {})
    if not isinstance(tab, dict):
        tab = {}
        profile["CharacterSpecificTab1"] = tab
    tab.setdefault("numSlot", BINDPAD_DEFAULT_SLOTS)
    return profile, tab, profile_num


def update_bindpad(
    vars_table: dict[Any, Any],
    profile_key: str | None,
    spec_index: int | None,
    plans: list[PlannedBind],
    general: bool,
    cleanup_names: set[str] | None = None,
    cleanup_keys: set[str] | None = None,
    layout: KeyLayout | None = None,
) -> int:
    selected_layout = layout or US_QWERTY_LAYOUT
    new_slots: list[dict[Any, Any]] = []
    planned_names: set[str] = set()
    for plan in plans:
        if not plan.key or not plan.macro:
            continue
        name = plan.debounce_name or plan.action.name
        planned_names.add(plan.action.name)
        planned_names.add(name)
        slot = {
            "type": "CLICK",
            "name": name,
            "macrotext": plan.macro,
            "action": bindpad_action(name),
            "texture": plan.icon,
            "source": MANAGED_SOURCE,
        }
        if general:
            slot["isForAllCharacters"] = True
        new_slots.append(slot)

    names_to_remove = set(cleanup_names or planned_names)
    names_to_remove.update(planned_names)
    keys_to_remove = set(cleanup_keys or ())
    keys_to_remove.update(plan.key.debounce(selected_layout) for plan in plans if plan.key)

    vars_table["version"] = 1.3
    vars_table.setdefault("tab", 1)
    general_keys = vars_table.setdefault("GeneralKeyBindings", {})
    if not isinstance(general_keys, dict):
        general_keys = {}
        vars_table["GeneralKeyBindings"] = general_keys

    if general:
        vars_table.setdefault("numSlot", BINDPAD_DEFAULT_SLOTS)
        managed_actions = replace_bindpad_slots(vars_table, new_slots, names_to_remove)
        remove_bindpad_actions(general_keys, managed_actions)
        remove_bindpad_keys(general_keys, keys_to_remove)
        profile_tables: list[dict[Any, Any]] = []
        for candidate_key in bindpad_profile_keys(vars_table):
            character = vars_table.get(candidate_key)
            if not isinstance(character, dict):
                continue
            for profile_num, profile in character.items():
                if not isinstance(profile_num, int) or not isinstance(profile, dict):
                    continue
                all_keys = profile.setdefault("AllKeyBindings", {})
                if isinstance(all_keys, dict):
                    remove_bindpad_actions(all_keys, managed_actions)
                    remove_bindpad_keys(all_keys, keys_to_remove)
                    profile_tables.append(all_keys)
        for plan in plans:
            name = plan.debounce_name or plan.action.name
            if not plan.key or not plan.macro:
                continue
            action = bindpad_action(name)
            key = plan.key.debounce(selected_layout)
            general_keys[key] = action
            for table in profile_tables:
                table[key] = action
        return len(new_slots)

    if not profile_key:
        raise ValueError("Choose a BindPad character/profile for class/spec binds.")
    if spec_index is None:
        raise ValueError("A class/spec section is required for BindPad character-specific binds.")

    _profile, tab, _profile_num = ensure_bindpad_profile(vars_table, profile_key, spec_index)
    managed_actions: set[str] = set()
    for candidate_tab in bindpad_character_tabs(_profile):
        if candidate_tab is tab:
            continue
        managed_actions.update(replace_bindpad_slots(candidate_tab, [], names_to_remove))
    managed_actions.update(replace_bindpad_slots(tab, new_slots, names_to_remove))
    all_keys = _profile.setdefault("AllKeyBindings", {})
    if not isinstance(all_keys, dict):
        all_keys = {}
        _profile["AllKeyBindings"] = all_keys
    remove_bindpad_actions(all_keys, managed_actions)
    remove_bindpad_keys(all_keys, keys_to_remove)
    for plan in plans:
        name = plan.debounce_name or plan.action.name
        if not plan.key or not plan.macro:
            continue
        all_keys[plan.key.debounce(selected_layout)] = bindpad_action(name)
    return len(new_slots)


def write_report(path: Path, plans: list[PlannedBind], layout: KeyLayout | None = None) -> None:
    selected_layout = layout or US_QWERTY_LAYOUT
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "section",
                "loader_action",
                "debounce_name",
                "key",
                "debounce_key",
                "ggl_token",
                "source",
                "debounce_macro",
                "warning",
            ]
        )
        for plan in plans:
            writer.writerow(
                [
                    plan.action.section,
                    plan.action.name,
                    plan.debounce_name or plan.action.name,
                    plan.key.human(selected_layout) if plan.key else "",
                    plan.key.debounce(selected_layout) if plan.key else "",
                    plan.ggl_token or "",
                    plan.source,
                    plan.macro or "",
                    plan.warning,
                ]
            )


def default_seed_path(ggl_config: Path) -> Path | None:
    candidates = [
        ggl_config.with_name("Config BACKUP.ini"),
        ggl_config.with_name("Config - Copy.ini"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync WoW keybinds into Debounce and GGL.")
    parser.add_argument("--section", help='GGL section, for example "Warrior - Fury".')
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this, only preview.")
    parser.add_argument("--overwrite-ggl", action="store_true", help="Replace existing GGL hotkeys too.")
    parser.add_argument(
        "--keep-old-managed",
        action="store_true",
        help="Do not remove earlier Debounce actions whose names start with GGL:.",
    )
    parser.add_argument("--debounce-path", type=Path, default=DEFAULT_DEBOUNCE)
    parser.add_argument("--ggl-config", type=Path, default=DEFAULT_GGL)
    parser.add_argument("--config-json", type=Path, default=DEFAULT_CONFIG_JSON)
    parser.add_argument("--seed-config", type=Path, help="Optional older Config.ini to copy known keys from.")
    parser.add_argument("--no-seed", action="store_true", help="Do not copy keys from a backup config.")
    parser.add_argument("--suffix", help="Override GGL keyboard suffix, for example 67699721.")
    parser.add_argument(
        "--keyboard-layout",
        choices=KEY_LAYOUT_ORDER,
        default=DEFAULT_KEY_LAYOUT_ID,
        help="Keyboard layout/profile used for addon key labels.",
    )
    parser.add_argument("--keys", help="Comma-separated base keys the binder may use, for example 1,2,3,Q,E,R.")
    parser.add_argument("--mods", help="Comma-separated modifiers the binder may use: alt,ctrl,shift.")
    parser.add_argument("--no-unmodified", action="store_true", help="Do not generate plain keys without a modifier.")
    parser.add_argument("--block-binds", help="Comma-separated exact binds to avoid, for example Alt+R,Ctrl+Shift+F12.")
    parser.add_argument("--randomize", action="store_true", help="Generate a randomized safe key order.")
    parser.add_argument("--random-seed", help="Stable seed for a reproducible randomized layout.")
    parser.add_argument("--actions", help="Comma-separated exact action names to bind.")
    parser.add_argument("--limit", type=int, help="Only process the first N selected actions.")
    parser.add_argument("--report", type=Path, help="CSV report path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    layout = key_layout_from_id(args.keyboard_layout)
    section = resolve_section(args)
    action_names = {part.strip() for part in args.actions.split(",")} if args.actions else None
    enabled_scans = None
    if args.keys:
        enabled_scans = set()
        invalid = []
        forbidden = []
        for part in args.keys.split(","):
            raw = part.strip()
            if not raw:
                continue
            scan_code = layout.scan_from_label(raw)
            if scan_code is None:
                invalid.append(raw)
                continue
            if not layout.supports_scan(scan_code):
                forbidden.append(raw)
                continue
            enabled_scans.add(scan_code)
        if invalid:
            raise SystemExit("Unknown key names in --keys: " + ", ".join(invalid))
        if forbidden:
            raise SystemExit("Unavailable keys cannot be enabled: " + ", ".join(forbidden))
        if not enabled_scans:
            raise SystemExit("At least one allowed key must be selected.")

    enabled_mods = None
    if args.mods is not None:
        mod_aliases = {"ALT": "ALT", "CTRL": "CTRL", "CONTROL": "CTRL", "SHIFT": "SHIFT"}
        enabled_mods = set()
        invalid_mods = []
        for part in args.mods.split(","):
            raw = part.strip().upper()
            if not raw:
                continue
            if raw in mod_aliases:
                enabled_mods.add(mod_aliases[raw])
            else:
                invalid_mods.append(part.strip())
        if invalid_mods:
            raise SystemExit("Unknown modifier names in --mods: " + ", ".join(invalid_mods))
    allow_unmodified = not args.no_unmodified
    if enabled_mods == set() and not allow_unmodified:
        raise SystemExit("Enable at least one modifier or allow unmodified keys.")

    try:
        blocked_keys = parse_keybind_set(args.block_binds, layout)
    except ValueError as exc:
        raise SystemExit(f"Invalid --block-binds value: {exc}") from exc

    ggl_text, ggl_encoding, ggl_newline = read_text(args.ggl_config)
    sections, ggl_lines = parse_ggl_entries(ggl_text)

    seed_sections = None
    seed_path = None
    if not args.no_seed:
        seed_path = args.seed_config or default_seed_path(args.ggl_config)
        if seed_path and seed_path.exists():
            seed_text, _, _ = read_text(seed_path)
            seed_sections, _ = parse_ggl_entries(seed_text)

    suffix = args.suffix or find_suffix(sections, seed_sections)
    if not suffix:
        raise SystemExit("Could not find a GGL keyboard suffix. Pass --suffix manually.")

    random_seed = args.random_seed.strip() if args.random_seed else None
    if args.randomize and not random_seed:
        random_seed = new_random_seed()

    entries = select_entries(sections, section, action_names, args.limit)
    loader_context_sections = {section}
    if section != "General":
        loader_context_sections.add("General")
    loader_reserved_keys = collect_ggl_reserved_keys(sections, loader_context_sections, entries)
    blocked_keys.update(loader_reserved_keys)
    seed_map = map_seed_entries(seed_sections, section)
    plan_seed = f"{random_seed}|{section}" if random_seed else None
    plans = plan_bindings(
        entries,
        seed_map,
        suffix,
        args.overwrite_ggl,
        enabled_scans,
        plan_seed,
        enabled_mods,
        allow_unmodified,
        blocked_keys,
        layout=layout,
    )
    class_file, spec_index = section_to_debounce_target(section)

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_section = re.sub(r"[^A-Za-z0-9]+", "_", section).strip("_")
    report_path = args.report or Path(__file__).with_name(f"wow_keybind_plan_{safe_section}_{stamp}.csv")
    write_report(report_path, plans, layout)

    assigned = sum(1 for plan in plans if plan.key)
    debounce_count = sum(1 for plan in plans if plan.key and plan.macro)
    warnings = [plan for plan in plans if plan.warning]

    print(f"Section: {section}")
    print(f"Debounce target: {class_file}" + (f" spec {spec_index}" if spec_index else ""))
    print(f"Planned GGL binds: {assigned}/{len(plans)}")
    print(f"Planned Debounce macro binds: {debounce_count}")
    print(f"GGL keyboard suffix: {suffix}")
    print(f"Keyboard layout: {layout.name}")
    if random_seed:
        print(f"Random layout seed: {random_seed}")
        if not args.overwrite_ggl:
            print("Existing loader hotkeys are being kept; randomized keys only fill open slots.")
    if enabled_mods is not None or not allow_unmodified:
        mods_label = ", ".join(m.title() for m in MODIFIER_ORDER if enabled_mods is None or m in enabled_mods)
        if not mods_label:
            mods_label = "none"
        plain_label = "yes" if allow_unmodified else "no"
        print(f"Allowed modifiers: {mods_label}; unmodified keys: {plain_label}")
    if blocked_keys:
        blocked_label = ", ".join(
            key.human(layout) for key in sorted(blocked_keys, key=lambda item: item.human(layout))
        )
        print(f"Reserved binds: {blocked_label}")
    if loader_reserved_keys:
        print(f"Existing loader hotkeys reserved: {len(loader_reserved_keys)}")
    if seed_path:
        seed_note = " (ignored for randomized layout)" if random_seed else ""
        print(f"Seed config: {seed_path}{seed_note}")
    print(f"Report: {report_path}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
        for warning in warnings[:8]:
            print(f"  - {warning.action.name}: {warning.warning}")
        if len(warnings) > 8:
            print(f"  - ... {len(warnings) - 8} more in the CSV report")

    preview = plans[:12]
    if preview:
        print("")
        print("Preview:")
        for plan in preview:
            key = plan.key.human(layout) if plan.key else "NO KEY"
            macro_note = "Debounce" if plan.macro else "GGL only"
            print(f"  {plan.action.name}: {key} ({plan.source}, {macro_note})")
        if len(plans) > len(preview):
            print(f"  ... {len(plans) - len(preview)} more")

    if not args.apply:
        print("")
        print("Preview only. Re-run with --apply to write backups and update the files.")
        return 0

    debounce_text, debounce_encoding, _ = read_text(args.debounce_path)
    vars_table = parse_debounce_vars(debounce_text)

    debounce_backup = backup_file(args.debounce_path)
    ggl_backup = backup_file(args.ggl_config)

    update_debounce(
        vars_table,
        class_file,
        spec_index,
        plans,
        replace_managed=not args.keep_old_managed,
        layout=layout,
    )
    new_debounce = "DebounceVars = " + dump_lua(vars_table) + "\n"
    write_text(args.debounce_path, new_debounce, debounce_encoding)

    new_lines = rewrite_ggl_lines(ggl_lines, plans, args.overwrite_ggl)
    new_ggl_text = ggl_newline.join(new_lines) + ggl_newline
    write_text(args.ggl_config, new_ggl_text, ggl_encoding)

    print("")
    print("Applied.")
    print(f"Debounce backup: {debounce_backup}")
    print(f"GGL backup: {ggl_backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
