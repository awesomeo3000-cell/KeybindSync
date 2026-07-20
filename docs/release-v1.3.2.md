# WoW Keybind Sync v1.3.2

This release focuses on loader overwrite reliability and numpad compatibility.

## Fixes

- Apply now detects any running executable in the selected `Config.ini` folder, including renamed loader executables.
- Advanced users can optionally select the loader executable directly when it is stored elsewhere.
- Apply checks whether the addon file or `Config.ini` is in use, then repeats the safety check immediately before writing.
- Written files are read back and verified. A failed Apply restores both files to their pre-Apply state.
- `NUM+`, `NUM-`, and modifier variants now parse correctly in reserved binds.
- Alt+numpad digit combinations are no longer generated because Windows can consume them as character input.

## Before Applying

Close WoW and the loader. If Advanced has an old `Loader exe` path after you rename the loader, select the renamed executable or clear the optional field when it remains beside `Config.ini`.
