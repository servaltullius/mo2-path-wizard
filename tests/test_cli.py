import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from mo2_path_wizard.cli import main


def _write_bytes(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


class TestCli(unittest.TestCase):
    def test_skip_nemesis_excludes_nemesis_auto_add(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Modpack"
            mods = instance / "mods"
            nemesis_dir = mods / "Nemesis Unlimited Behavior Engine"
            nemesis_dir.mkdir(parents=True)
            (nemesis_dir / "Nemesis Unlimited Behavior Engine.exe").write_bytes(b"")

            ini_path = instance / "ModOrganizer.ini"
            _write_bytes(
                ini_path,
                "[customExecutables]\r\n"
                "size=0\r\n",
            )

            out = io.StringIO()
            with redirect_stdout(out):
                code = main(
                    [
                        "--ini",
                        str(ini_path),
                        "--instance-root",
                        str(instance),
                        "--auto-add-missing",
                        "--skip-nemesis",
                        "--dry-run",
                    ]
                )

        self.assertEqual(code, 0)
        output = out.getvalue()
        self.assertNotIn("title=Nemesis", output)
        self.assertNotIn("auto-add: Nemesis", output)


if __name__ == "__main__":
    unittest.main()
