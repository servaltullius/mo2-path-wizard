import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mo2_path_wizard.relocate import infer_root_moves


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


class TestInferRootMoves(unittest.TestCase):
    def test_infers_pack_move_from_existing_suffix(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "TAKEALOOK"
            _touch(pack / "mods" / "SKSE" / "Root" / "skse64_loader.exe")
            moves = infer_root_moves(["D:/TAKEALOOK/mods/SKSE/Root/skse64_loader.exe"], [pack])
            self.assertEqual([("D:/TAKEALOOK", pack)], [(m.old_root, m.new_root) for m in moves])

    def test_renamed_pack_needs_two_votes(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack v2"
            _touch(pack / "mods" / "A" / "a.exe")
            _touch(pack / "tools" / "B" / "b.exe")
            one = infer_root_moves(["D:/Pack v1/mods/A/a.exe"], [pack])
            two = infer_root_moves(["D:/Pack v1/mods/A/a.exe", "D:/Pack v1/tools/B/b.exe"], [pack])
            self.assertEqual([], one)
            self.assertEqual(["D:/Pack v1"], [m.old_root for m in two])

    def test_unrelated_user_folder_is_not_mapped(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "TAKEALOOK"
            (pack / "downloads").mkdir(parents=True)
            moves = infer_root_moves(["C:/Users/me/downloads/new folder", "C:/Users/me/downloads/x"], [pack])
            self.assertEqual([], moves)

    def test_generic_folder_name_is_not_a_name_match(self) -> None:
        with TemporaryDirectory() as td:
            tools = Path(td) / "TAKEALOOK" / "TOOLS"
            _touch(tools / "zEdit" / "zEdit.exe")
            moves = infer_root_moves(["D:/OtherPack/TOOLS/zEdit/zEdit.exe"], [tools], require_name_match=True)
            self.assertEqual([], moves)

    def test_require_name_match_ignores_votes(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "TAKEALOOK"
            _touch(pack / "TOOLS" / "zEdit" / "zEdit.exe")
            _touch(pack / "TOOLS" / "zEdit" / "merges" / "x.json")
            paths = ["D:/BabyRim/TOOLS/zEdit/zEdit.exe", "D:/BabyRim/TOOLS/zEdit/merges/x.json"]
            self.assertEqual([], infer_root_moves(paths, [pack], require_name_match=True))
            self.assertEqual(["D:/TAKEALOOK"], [m.old_root for m in infer_root_moves(["D:/TAKEALOOK/TOOLS/zEdit/zEdit.exe"], [pack], require_name_match=True)])

    def test_paths_already_under_new_root_are_ignored(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "TAKEALOOK"
            _touch(pack / "mods" / "a.exe")
            self.assertEqual([], infer_root_moves([f"{pack.as_posix()}/mods/a.exe"], [pack]))


if __name__ == "__main__":
    unittest.main()
