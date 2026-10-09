import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mo2_path_wizard.external import describe_changes, find_config_targets, plan_change, write_change
from mo2_path_wizard.paths import build_replacements


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class TestExternalConfigs(unittest.TestCase):
    def test_finds_known_config_files_case_insensitively(self) -> None:
        with TemporaryDirectory() as td:
            tools = Path(td) / "TOOLS"
            exe = _write(tools / "BethINI Standalone" / "BethINI.exe", b"")
            _write(tools / "BethINI Standalone" / "BethINI.ini", b"x")
            syn = _write(tools / "Synthesis" / "Synthesis.exe", b"")
            _write(tools / "Synthesis" / "PipelineSettings.json", b"{}")
            _write(tools / "Synthesis" / "Data" / "Skyrim Special Edition" / "Patcher" / "settings.json", b"{}")
            _write(tools / "DynDOLOD" / "Edit Scripts" / "Export" / "LODGen_SSE_Export_Tamriel.txt", b"x")
            dyn = _write(tools / "DynDOLOD" / "DynDOLODx64.exe", b"")

            targets = find_config_targets([exe, syn, dyn])

            names = sorted(t.path.name for t in targets)
            self.assertEqual(["BethINI.ini", "PipelineSettings.json", "settings.json"], names)

    def test_json_ini_xml_paths_are_rewritten_and_format_preserved(self) -> None:
        rules = build_replacements("D:/TAKEALOOK", "G:/TAKEALOOK")
        cases = {
            "settings.json": (b'\xef\xbb\xbf{\r\n  "dir": "D:\\\\TAKEALOOK\\\\Stock Game",\r\n  "other": "D:\\\\TAKEALOOK - Outputs"\r\n}\r\n',
                              b'\xef\xbb\xbf{\r\n  "dir": "G:\\\\TAKEALOOK\\\\Stock Game",\r\n  "other": "D:\\\\TAKEALOOK - Outputs"\r\n}\r\n'),
            "BethINI.ini": (b"sGamePath=D:\\TAKEALOOK\\Stock Game\\\nsModOrganizerPath=D:\\TAKEALOOK\\\n",
                            b"sGamePath=G:\\TAKEALOOK\\Stock Game\\\nsModOrganizerPath=G:\\TAKEALOOK\\\n"),
            "Config.xml": (b"<GameDataPath>D:\\TAKEALOOK\\Stock Game\\Data\\</GameDataPath>\n",
                           b"<GameDataPath>G:\\TAKEALOOK\\Stock Game\\Data\\</GameDataPath>\n"),
        }
        from mo2_path_wizard.external import ExternalTarget

        with TemporaryDirectory() as td:
            for name, (before, after) in cases.items():
                with self.subTest(name=name):
                    path = _write(Path(td) / name, before)
                    change = plan_change(ExternalTarget(tool="t", path=path), rules)
                    self.assertIsNotNone(change)
                    self.assertEqual(after, change.new_bytes)
                    bak = write_change(change, backup=True)
                    self.assertEqual(before, bak.read_bytes())
                    self.assertEqual(after, path.read_bytes())

    def test_sensitive_files_do_not_expose_lines(self) -> None:
        from mo2_path_wizard.external import ExternalTarget

        with TemporaryDirectory() as td:
            path = _write(Path(td) / "config.json", b'{"api_key": "SECRET", "base_folder": "D:\\\\TAKEALOOK"}')
            change = plan_change(
                ExternalTarget(tool="SSE-AT", path=path, sensitive=True), build_replacements("D:/TAKEALOOK", "G:/TAKEALOOK")
            )
            self.assertEqual((), change.changed_lines)
            self.assertNotIn("SECRET", describe_changes([change]))
            self.assertIn(b"SECRET", change.new_bytes)

    def test_no_change_returns_none(self) -> None:
        from mo2_path_wizard.external import ExternalTarget

        with TemporaryDirectory() as td:
            path = _write(Path(td) / "x.json", b'{"dir": "E:\\\\Elsewhere"}')
            self.assertIsNone(plan_change(ExternalTarget(tool="t", path=path), build_replacements("D:/A", "G:/A")))


if __name__ == "__main__":
    unittest.main()
