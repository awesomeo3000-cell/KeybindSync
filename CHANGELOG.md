# Changelog

## Unreleased

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
