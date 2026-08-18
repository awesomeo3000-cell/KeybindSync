# Changelog

## 1.4.1

- Fixed a `NameError: 'bindpad_numeric_slots' is not defined` crash when applying BindPad binds or running cleanup. The helper function was accidentally dropped in the v1.4.0 Debind refactor.

## 1.4.0

- Added Debind support. Debounce 3.x was renamed to Debind and now stores its settings in `SavedVariables\Debind.lua` as an account-wide `DebindVars` table (`dbver = 5`) with layers under `shared.GENERAL` and `shared.classes[class][spec]`.
- Debind is now the default addon choice; Debounce and BindPad remain fully supported.
- Debind actions are marked with a `$wowKeybindSync` field because Debind strips unknown action fields (including `source`) from its saved data on login.
- When Debind is selected and an old `Debounce.lua` is still present, the app backs it up and removes it on Apply so Debind's one-time migration cannot overwrite the newly written binds.
- Added the `--addon debind|debounce` and `--debind-path` command line options.
- The Advanced cleanup action now clears Debind layers as well as Debounce.

## 1.3.5

- Replaces legacy NumLock-off aliases such as `NUMPAGEDOWN`, `NUMPADPAGEDOWN`, `NUMPAGEUP`, and `NUMPADPAGEUP` instead of leaving stale entries beside the new numeric NumPad binds.
- Applies alias-aware cleanup to both Debounce and BindPad key tables across class/spec profiles.

## 1.3.4

- Stopped generating Shift + NumPad digit binds, which can be interpreted as navigation keys such as End, Clear, or Page Down instead of the numeric keypad key selected by the user.
- Ctrl + NumPad digit binds remain available.

## 1.3.3

- The Advanced cleanup action can now clear old key assignments from the selected `Config.ini` section, the selected Debounce target, or both, with backups and verification.
- General actions now match common loader spellings such as `Trinket 1`, `Health Stone`, and `Healing Potion`; observed `NUMPADDCLE`/`NUMPADCLE` labels are treated as NumPad 5.
- General binds are now discovered dynamically from the Config.ini `[General]` section, including `StopCasting`, party focus actions, `Whipper Root Tuber`, and other user-defined entries.
- Key Rules now explicitly explains the NumPad 5 / NumLock-off `CLEAR` label relationship and the Enable Numpad action.
- NumPad selections now show live NumLock guidance; Apply requests confirmation when NumLock is off instead of silently proceeding.

## 1.3.2

- Detects any running executable launched from the selected `Config.ini` folder, so renamed loader executables are blocked before Apply.
- Added an optional Advanced `Loader exe` path for setups where the executable is stored outside the `Config.ini` folder.
- Added exclusive-access checks for the addon file and `Config.ini`, with a second process/file check immediately before each write.
- Added post-write verification and whole-run rollback so a failed Apply does not leave the addon and loader files out of sync.
- Fixed reserved-bind parsing for `NUM+`, `NUM-`, and modifier variants such as `CTRL+NUM+`.
- Stopped generating `Alt` + numpad digit binds because Windows may consume them as character-entry sequences.
- Added automated process-safety and numpad regression tests to local builds and GitHub Actions.

## 1.3.1

- Added NumLock-off key aliases: NUMPADCLEAR, NUMPADPAGEDOWN, NUMPADEND, NUMPADHOME, NUMPADINSERT, NUMPADDELETE, and all arrow/PageUp variants now resolve to their NumLock-on counterparts.
- Added missing NUMPADENTER key (scan 0x11C) to SCAN_CODES, candidate lists, and display labels.
- Fixed mismatched binds caused by addon keys stored with NumLock-off labels being unparsable.

## 1.3.0

- Added Advanced Batch Specs mode for selecting multiple Debounce-supported class/spec sections.
- Added a dedicated Batch Specs workflow with searchable checkbox rows, Select Visible, and Clear controls.
- Batch Specs mode now hides the single-spec spell/action editor while batch mode is active.
- Batch runs use saved per-spec spell/action toggles and process General global binds once.
- Fixed Result window scrolling so mousewheel movement inside the result text no longer scrolls the whole app.
- Cleaned stale BindPad managed macros across all character-specific tabs before writing new binds.
- Added cleanup for older `GGL: ` BindPad macro names.
- Added a preflight warning when active loader actions would create duplicate addon macro names.
- Fixed BindPad support for non-retail sections like `TBC Paladin`.

## 1.2.5

- Added preflight setup checks.
- Added Backup Manager.
- Added redacted support bundle export.
- Added keyboard layout support work in progress.
- Added Disable Selected and Disable All controls to Spell / Loader Actions.
- Preserved Spell / Loader Actions scroll position after toggling actions.

## 1.2.4

- Fixed the GitHub release workflow permission so tagged releases can publish the Windows `.exe`.

## 1.2.3

- Added AI instruction rows to the custom macro CSV template.
- Custom macro CSV import now ignores template instruction rows beginning with `#`.
- Added a Death Knight Unholy custom macro example CSV.

## 1.2.1

- Improved theme switching performance.
- Preloaded Advanced shortly after Express opens.
- Kept disabled custom macro row coloring consistent after refreshes and theme swaps.

## 1.2.0

- Added custom macro CSV import.
- Added Save Template for custom macro CSV format.
- Added custom macro support to Express setup.
- Added searchable, scrollable Advanced class/spec picker.
- Cleaned up the Advanced tab layout.
