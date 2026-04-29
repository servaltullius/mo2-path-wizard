# Changelog

## v1.0.2 - 2026-04-29

### Summary

This release focuses on safer MO2 path migration, Pandora compatibility after recent Pandora updates, and more reliable modpack auto-detection across real-world folder layouts.

### Added

- Added `--skip-pandora` for CLI users.
- Added `Pandora 자동 추가/프리셋 제외` in the GUI.
- Added regression coverage for Pandora skip behavior, prefix-sibling folder names, and the `G:\TAKEALOOK` style auto-detection layout.

### Changed

- `--skip-pandora` now excludes both Pandora behaviors:
  - auto-adding `Pandora Behaviour Engine+` when missing from `[customExecutables]`
  - applying the built-in Pandora `arguments` preset to an existing Pandora entry
- The GUI checkbox text now reflects the full behavior: `Pandora 자동 추가/프리셋 제외`.
- Package metadata version is now `1.0.2`.

### Fixed

- Fixed Pandora arguments being recreated after users manually cleared them.
  - Before: existing `Pandora Behaviour Engine+` entries could get `--tesv:"..." -o:"...\Pandora Output"` inserted again when `arguments 프리셋 적용(덮어쓰기)` was enabled.
  - Now: with Pandora skip enabled, existing Pandora `arguments=` stays untouched.
- Fixed path replacement for folder names that share a prefix.
  - Before: moving from `HGM` to `HGM2` could rewrite existing `HGM2` paths into `HGM22`.
  - Before: moving from `HGM2` to `HGMT` could rewrite existing `HGM22` paths into `HGMT2`.
  - Now: path replacement only happens at path boundaries, so sibling folders with similar names are preserved.
- Fixed auto-detection when a modpack has an internal `TOOLS` folder and the drive/root also has a sibling `Tools` folder.
  - Real failing layout: `G:\TAKEALOOK` plus `G:\Tools`.
  - Before: auto-detection found `G:\TAKEALOOK\ModOrganizer.ini`, then crashed while scoring the external `G:\Tools` candidate.
  - Now: root-external tool candidates no longer crash detection, and the internal `G:\TAKEALOOK\TOOLS` folder is selected.

### Verification

- Verified `G:\TAKEALOOK` auto-detection:
  - `ini = G:\TAKEALOOK\ModOrganizer.ini`
  - `instance = G:\TAKEALOOK`
  - `game = G:\TAKEALOOK\Stock Game`
  - `tool = G:\TAKEALOOK\TOOLS`
  - `ok = True`
  - `warnings = ()`
- Verified prefix-sibling path migration with the built executable:
  - `HGM -> HGM2` preserves existing `HGM2` paths and does not create `HGM22`.
  - `HGM2 -> HGMT` preserves existing `HGM22` paths and does not create `HGMT2`.
- Verified Pandora skip with the built executable:
  - without `--skip-pandora`, the Pandora Output preset appears
  - with `--skip-pandora`, the Pandora arguments preset is absent
- Ran the full test suite:
  - `python -m unittest discover -s tests -p "test*.py" -v`
  - result: `14` tests passing

### Release Artifacts

- `dist\mo2-path-wizard-gui.zip`
- `dist\mo2-path-wizard-gui.exe`
- `dist\mo2-path-wizard.exe`

