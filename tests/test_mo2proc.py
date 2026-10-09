import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mo2_path_wizard.mo2proc import check_mo2_status


class TestMo2Status(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "Windows에서는 실제 프로세스 목록을 본다")
    def test_unsupported_environment(self) -> None:
        status = check_mo2_status(Path("x/ModOrganizer.ini"))
        self.assertFalse(status.supported)
        self.assertFalse(status.same_instance)

    def test_portable_instance_matches_by_folder(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            pack.mkdir()
            (pack / "ModOrganizer.exe").write_bytes(b"")
            ini = pack / "ModOrganizer.ini"
            same = check_mo2_status(ini, running=[pack / "ModOrganizer.exe"])
            other = check_mo2_status(ini, running=[Path(td) / "Other" / "ModOrganizer.exe"])
            none = check_mo2_status(ini, running=[])
            self.assertTrue(same.same_instance)
            self.assertFalse(other.same_instance)
            self.assertTrue(other.any_running)
            self.assertFalse(none.any_running)

    def test_unknown_process_path_is_treated_as_same(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            pack.mkdir()
            (pack / "ModOrganizer.exe").write_bytes(b"")
            status = check_mo2_status(pack / "ModOrganizer.ini", running=[Path("ModOrganizer.exe")])
            self.assertTrue(status.same_instance)

    def test_global_instance_any_mo2_counts(self) -> None:
        with TemporaryDirectory() as td:
            ini = Path(td) / "AppData" / "ModOrganizer.ini"
            status = check_mo2_status(ini, running=[Path(td) / "MO2" / "ModOrganizer.exe"])
            self.assertTrue(status.same_instance)


if __name__ == "__main__":
    unittest.main()
