import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mo2_path_wizard.executables import DEFAULT_EXECUTABLE_SPECS, locate_executable


def _spec(title: str):
    return next(s for s in DEFAULT_EXECUTABLE_SPECS if s.title == title)


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


class TestLocateExecutable(unittest.TestCase):
    def test_finds_new_tools(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            tools = pack / "TOOLS"
            expected = {
                "Edit": _touch(tools / "SSEEdit (4.1.5)" / "SSEEdit64.exe"),
                "PGPatcher": _touch(tools / "ParallaxGen" / "ParallaxGen.exe"),
                "LOOT": _touch(tools / "LOOT" / "LOOT.exe"),
                "BethINI": _touch(tools / "BethINI Standalone" / "BethINI.exe"),
                "SSE-AT": _touch(tools / "SSE-AT" / "SSE-AT.exe"),
                "Cathedral Assets Optimizer": _touch(tools / "CAO" / "Cathedral_Assets_Optimizer.exe"),
                "BodySlide x64": _touch(
                    pack / "mods" / "BodySlide and Outfit Studio" / "CalienteTools" / "BodySlide" / "BodySlide x64.exe"
                ),
                "Explore Virtual Folder": _touch(pack / "explorer++" / "Explorer++.exe"),
            }
            # BodySlide 프리셋 모드(이름에 bodyslide 포함)가 먼저 와도 실제 BodySlide 폴더를 찾아야 한다.
            (pack / "mods" / "(BodySlide 3BA) Preset").mkdir(parents=True)

            for title, path in expected.items():
                with self.subTest(title=title):
                    found = locate_executable(_spec(title), instance_root=pack, tool_root=tools)
                    self.assertEqual(path, found)

    def test_missing_tool_returns_none(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            (pack / "mods").mkdir(parents=True)
            self.assertIsNone(locate_executable(_spec("LOOT"), instance_root=pack, tool_root=None))


if __name__ == "__main__":
    unittest.main()
