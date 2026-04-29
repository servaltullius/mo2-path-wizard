# v1.0.2 - Pandora Skip, Safe Path Replacement, and Auto-Detection Fixes

## Overview

This release fixes the issues reported during real modpack testing after Pandora updates and folder-renaming tests. It is recommended for users migrating or testing copied modpacks such as `HGM`, `HGM2`, `HGMT`, or `TAKEALOOK`.

## What's Fixed

- Fixed Pandora arguments being recreated after users manually cleared them.
  - Previous behavior: if `arguments 프리셋 적용(덮어쓰기)` was enabled, an existing `Pandora Behaviour Engine+` entry could receive `--tesv:"..." -o:"...\Pandora Output"` again.
  - New behavior: when `--skip-pandora` or `Pandora 자동 추가/프리셋 제외` is enabled, the existing Pandora `arguments=` line is left untouched.
- Fixed path replacement for folders with shared prefixes.
  - Previous behavior: `HGM -> HGM2` could turn existing `HGM2` paths into `HGM22`.
  - Previous behavior: `HGM2 -> HGMT` could turn existing `HGM22` paths into `HGMT2`.
  - New behavior: replacement only happens at real path boundaries, so similarly named sibling folders are preserved.
- Fixed auto-detection for the `G:\TAKEALOOK` layout.
  - Previous behavior: `G:\TAKEALOOK\ModOrganizer.ini` was found, but detection failed while scoring an external `G:\Tools` candidate.
  - New behavior: `G:\TAKEALOOK\TOOLS` is selected correctly, and auto-detection completes without warnings.

## New or Changed Options

- CLI: `--skip-pandora`
  - Skips auto-adding `Pandora Behaviour Engine+`.
  - Skips applying the built-in Pandora arguments preset to existing Pandora entries.
- GUI: `Pandora 자동 추가/프리셋 제외`
  - Same behavior as `--skip-pandora`.

## Verification

- Full test suite:
  - Command: `python -m unittest discover -s tests -p "test*.py" -v`
  - Result: `14` tests passing.
- Verified real `G:\TAKEALOOK` detection:
  - `ini = G:\TAKEALOOK\ModOrganizer.ini`
  - `instance = G:\TAKEALOOK`
  - `game = G:\TAKEALOOK\Stock Game`
  - `tool = G:\TAKEALOOK\TOOLS`
  - `ok = True`
  - `warnings = ()`
- Verified built executable dry-run:
  - `.\dist\mo2-path-wizard.exe --root 'G:\TAKEALOOK' --dry-run --skip-pandora`
  - Result: no auto-detection crash.
- Verified prefix-sibling cases with the built executable:
  - `HGM -> HGM2` does not create `HGM22`.
  - `HGM2 -> HGMT` does not create `HGMT2`.
- Verified Pandora skip with the built executable:
  - without `--skip-pandora`, the Pandora Output preset appears
  - with `--skip-pandora`, the Pandora arguments preset is absent

## Recommended Asset

- `mo2-path-wizard-gui.zip`

## Optional Assets

- `mo2-path-wizard-gui.exe`
- `mo2-path-wizard.exe`

## SHA256

```text
CB7794C87C46B98BDE68C652EEB0B48CC80328EEBFEDDE486470A82B7D7A8F74  mo2-path-wizard-gui.zip
69EBA28A52F4400B91B55A1E9A1C2D31B4E041A74284F82218FBD69082EB3BC3  mo2-path-wizard-gui.exe
63EFEBE235CCA3890B83D7243420023850587889C3C80350120F0607EA57C85B  mo2-path-wizard.exe
```

