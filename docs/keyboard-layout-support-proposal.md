# Keyboard Layout Support Proposal v2

## Goal

Support non-US keyboard layouts without creating duplicate physical binds or mismatched loader/addon binds.

The key correction from review is that key identity must be based on the physical key/scancode, not the visible label. Labels change by layout. Physical keys do not.

## Core Rule

Use this identity everywhere inside the planner:

```text
key identity = scancode + modifiers
```

Use layout-specific labels only at the edges:

- GUI display: what the user sees.
- Debounce/BindPad output: what the addon expects.
- Reports: show both user label and generated loader token when helpful.

This avoids a German layout treating `Z` and US `Y` as separate keys when they are the same physical key.

## Why This Fits The Current Code

The project is already halfway there:

- Loader output already uses scancodes through `KeyBind.ggl()`.
- Addon output already uses labels through `KeyBind.debounce()`.
- Today `base == display label == addon token` because only US QWERTY exists.

The refactor finishes that separation.

## Revised Phases

### Phase 0: Scancode Identity Refactor

This is the foundation and should ship with US output byte-equivalent to the current release.

Change `KeyBind` from label-based:

```python
KeyBind(base="Y", mods=("ALT",))
```

to scancode-based:

```python
KeyBind(scan_code=0x15, mods=("ALT",))
```

Then use a selected layout only when rendering or emitting:

```python
key.ggl(suffix)                         # loader scancode token
key.debounce(layout)                    # addon token
key.human(layout)                       # GUI/report label
```

Primary code surfaces:

- `SCAN_CODES`
- `SCAN_TO_KEY`
- `FORBIDDEN_BASES`
- `CANDIDATE_BASE_ORDER`
- `DEFAULT_BIND_BASES`
- `KeyBind`
- `parse_keybind_label`
- `parse_keybind_set`
- `is_key_allowed`
- `key_candidates`
- `plan_bindings`
- report/addon emit calls using `plan.key.debounce()` or `plan.key.human()`

Regression gate:

- US QWERTY output must match the current release for the same settings, seed, config, and selected keys.

### Phase 1: Keyboard Layout Dropdown + German QWERTZ

Add `Keyboard layout` to Express and Advanced:

```text
US QWERTY
German QWERTZ
International Safe
Nordic ISO - Swedish/Finnish
Nordic ISO - Danish/Norwegian
```

Ship the first actual layout as German QWERTZ because it is low risk:

- No new scancodes required.
- `Y` and `Z` already exist.
- Only display/addon labels swap:
  - scancode `0x15`: US `Y`, German `Z`
  - scancode `0x2C`: US `Z`, German `Y`

### Phase 2: International Safe Profile

Add a curated profile for users who do not want layout-specific risk:

- number row
- safe F keys, still excluding `F4`
- optional numpad
- modifiers

Avoid phrasing this as "letters are dangerous." It is a conservative allowlist for easier support and fewer layout surprises.

### Phase 3: Nordic/German Special Keys

Do this only after tester data and the encoding fix are complete.

Special keys are not currently just disabled keys. They are missing scancode entries entirely.

Likely new physical positions include:

```text
US [  / German Ü / Nordic Å candidate: scancode 0x1A
US ;  / German Ö candidate: scancode 0x27
US '  / German Ä candidate: scancode 0x28
US -  / German ß candidate: scancode 0x0C
```

Do not ship these from guesses. Confirm exact Debounce/BindPad tokens first.

## Critical Dependency: Encoding Fix

Before Phase 3, fix the SavedVariables encoding path.

If WoW stores `Å`, `Ä`, `Ö`, `Æ`, `Ø`, `Ü`, `ß` literally and the detected file encoding is `cp1252` or another narrow encoding, writes can fail with `UnicodeEncodeError`.

Phase 3 must not ship until writes safely preserve or upgrade encoding instead of aborting mid-apply.

## Tester Request

Ask testers to manually bind each key in WoW/BindPad/Debounce and send the stored output.

Request both bare and modified binds:

```text
Swedish/Finnish:
Å
SHIFT-Å
Ä
SHIFT-Ä
Ö
SHIFT-Ö

Danish/Norwegian:
Æ
SHIFT-Æ
Ø
SHIFT-Ø
Å
SHIFT-Å

German:
Y
SHIFT-Y
Z
SHIFT-Z
Ü
SHIFT-Ü
Ö
SHIFT-Ö
Ä
SHIFT-Ä
ß
SHIFT-ß
```

Also ask which keys refuse to bind at all in WoW. Those become layout-specific forbidden/reserved keys.

## Settings Migration

Current setting:

```json
"enabled_keys": ["Q", "E", "R", "F1"]
```

New setting should be scancode-based:

```json
"enabled_key_ids": ["SC_10", "SC_12", "SC_13", "SC_3B"]
```

Migration rule:

- Treat old `enabled_keys` as US QWERTY labels.
- Convert each label through the existing `SCAN_CODES` table.
- Save as scancode IDs.
- Default layout after migration is `US QWERTY`.

When layout changes:

- Keep enabled scancodes where the new layout supports them.
- Report any enabled keys that became unavailable.
- Tell the user exactly which keys changed, not just a generic warning.

## Suggested Data Model

```python
@dataclass(frozen=True)
class KeyLayout:
    id: str
    name: str
    labels_by_scan: dict[int, str]
    addon_tokens_by_scan: dict[int, str]
    forbidden_scans: set[int]
    default_enabled_scans: list[int]
```

```python
@dataclass(frozen=True)
class KeyBind:
    scan_code: int
    mods: tuple[str, ...] = ()

    def ggl(self, suffix: str) -> str:
        ...

    def debounce(self, layout: KeyLayout) -> str:
        ...

    def human(self, layout: KeyLayout) -> str:
        ...
```

Avoid putting `display_label` or `addon_token` into `KeyBind` identity.

## Function Signature Sketch

Current:

```python
def key_candidates(
    enabled_bases: set[str] | None = None,
    random_seed: str | None = None,
    enabled_mods: set[str] | None = None,
    allow_unmodified: bool = True,
    blocked_keys: set[KeyBind] | None = None,
) -> list[KeyBind]:
```

Proposed:

```python
def key_candidates(
    layout: KeyLayout,
    enabled_scans: set[int] | None = None,
    random_seed: str | None = None,
    enabled_mods: set[str] | None = None,
    allow_unmodified: bool = True,
    blocked_keys: set[KeyBind] | None = None,
) -> list[KeyBind]:
```

Current:

```python
def plan_bindings(..., enabled_bases: set[str] | None = None, ...)
```

Proposed:

```python
def plan_bindings(
    ...,
    layout: KeyLayout,
    enabled_scans: set[int] | None = None,
    ...
) -> list[PlannedBind]:
```

Current emit:

```python
plan.key.debounce()
plan.key.human()
```

Proposed emit:

```python
plan.key.debounce(layout)
plan.key.human(layout)
```

## Implementation Risks

- Settings migration must not scramble enabled keys.
- Duplicate prevention must use scancode identity only.
- Reports need enough detail to debug layout mismatches.
- Existing reserved bind parsing still accepts old user-entered labels; parsing should be layout-aware.
- Special-key support depends on encoding and tester data.

## Recommendation

Do not jump straight to Nordic special letters.

Ship in this order:

1. Phase 0: scancode identity refactor, US behavior unchanged.
2. Phase 1: dropdown + German QWERTZ.
3. Phase 2: International Safe profile.
4. Phase 3: special keys after encoding fix and tester data.

This gives real layout support without betting the app on unverified non-ASCII key behavior.
