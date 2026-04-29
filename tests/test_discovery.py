import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mo2_path_wizard.discovery import discover_from_root


class TestDiscovery(unittest.TestCase):
    def test_discovers_paths_from_modpack_root(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td) / "Modpack"
            mo2 = root / "MO2"
            (root / "mods").mkdir(parents=True)
            (root / "profiles").mkdir(parents=True)
            (root / "tools").mkdir(parents=True)

            game = root / "Stock Game" / "Skyrim Special Edition"
            (game / "Data").mkdir(parents=True)
            (game / "SkyrimSE.exe").write_bytes(b"")

            mo2.mkdir(parents=True)
            (mo2 / "ModOrganizer.exe").write_bytes(b"")
            (mo2 / "ModOrganizer.ini").write_text("[Settings]\nbase_directory=C:/Old/Instance\n", encoding="utf-8")

            discovered = discover_from_root(root, edition="sse")
            self.assertTrue(discovered.ok)
            self.assertEqual(discovered.ini_path, mo2 / "ModOrganizer.ini")
            self.assertEqual(discovered.instance_root, root)
            self.assertEqual(discovered.tool_root, root / "tools")
            self.assertEqual(discovered.game_path, game)

    def test_discovers_internal_tools_when_parent_has_tools_folder(self) -> None:
        with TemporaryDirectory() as td:
            drive = Path(td) / "Drive"
            root = drive / "TAKEALOOK"
            parent_tools = drive / "Tools"
            internal_tools = root / "TOOLS"

            parent_tools.mkdir(parents=True)
            internal_tools.mkdir(parents=True)
            (internal_tools / "SSEEdit" / "SSEEdit.exe").parent.mkdir(parents=True)
            (internal_tools / "SSEEdit" / "SSEEdit.exe").write_bytes(b"")
            (root / "mods").mkdir(parents=True)
            (root / "profiles").mkdir(parents=True)
            game = root / "Stock Game"
            (game / "Data").mkdir(parents=True)
            (game / "SkyrimSE.exe").write_bytes(b"")
            (root / "ModOrganizer.exe").write_bytes(b"")
            (root / "ModOrganizer.ini").write_text(
                "[General]\n"
                f"gamePath=@ByteArray({str(game).replace('/', '\\\\').replace('\\\\', '\\\\\\\\')})\n",
                encoding="utf-8",
            )

            discovered = discover_from_root(root, edition="sse")

            self.assertTrue(discovered.ok)
            self.assertEqual(discovered.ini_path, root / "ModOrganizer.ini")
            self.assertEqual(discovered.instance_root, root)
            self.assertEqual(discovered.game_path, game)
            self.assertEqual(discovered.tool_root, internal_tools)


if __name__ == "__main__":
    unittest.main()
