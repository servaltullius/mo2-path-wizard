import unittest
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mo2_path_wizard.patcher import (
    PatchOptions,
    _apply_replacements,
    _build_replacements,
    inspect_custom_executables,
    patch_modorganizer_ini,
)


def _write_bytes(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


class TestPatcher(unittest.TestCase):
    def test_inspect_custom_executables_lists_current_entries_only(self) -> None:
        ini_text = (
            "[customExecutables]\r\n"
            "size=2\r\n"
            "1\\arguments=\r\n"
            "1\\binary=G:/Pack/mods/SKSE/skse64_loader.exe\r\n"
            "1\\title=SKSE\r\n"
            "1\\workingDirectory=G:/Pack/mods/SKSE\r\n"
            "2\\arguments=\r\n"
            "2\\binary=G:/Pack/mods/Pandora/Pandora Behaviour Engine+.exe\r\n"
            "2\\title=Pandora Behaviour Engine+\r\n"
            "2\\workingDirectory=G:/Pack/mods/Pandora\r\n"
            "\r\n"
            "[recentDirectories]\r\n"
            "size=1\r\n"
            "1\\name=editExecutableBinary\r\n"
            "1\\directory=G:/Pack/mods/Nemesis/Nemesis_Engine\r\n"
        )

        with TemporaryDirectory() as td:
            ini_path = Path(td) / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            entries = inspect_custom_executables(ini_path)

        self.assertEqual([entry.index for entry in entries], [1, 2])
        self.assertEqual([entry.title for entry in entries], ["SKSE", "Pandora Behaviour Engine+"])
        self.assertEqual(entries[0].binary, "G:/Pack/mods/SKSE/skse64_loader.exe")
        self.assertNotIn("Nemesis", [entry.title for entry in entries])

    def test_replacements_do_not_match_path_prefix_siblings(self) -> None:
        replacements = _build_replacements("F:/HGM", "F:/HGM2")

        self.assertEqual(_apply_replacements("F:/HGM/mods/Tool.exe", replacements), "F:/HGM2/mods/Tool.exe")
        self.assertEqual(_apply_replacements("F:/HGM2/mods/Tool.exe", replacements), "F:/HGM2/mods/Tool.exe")
        self.assertEqual(_apply_replacements(r"F:\HGM2\explorer++", replacements), r"F:\HGM2\explorer++")
        self.assertEqual(_apply_replacements(r"F:\\HGM2\\explorer++", replacements), r"F:\\HGM2\\explorer++")

        next_replacements = _build_replacements("F:/HGM2", "F:/HGMT")
        self.assertEqual(_apply_replacements("F:/HGM22/explorer++", next_replacements), "F:/HGM22/explorer++")
        self.assertEqual(_apply_replacements(r"F:\HGM2\explorer++", next_replacements), r"F:\HGMT\explorer++")
        self.assertEqual(_apply_replacements(r"F:\\HGM2\\explorer++", next_replacements), r"F:\\HGMT\\explorer++")

    def test_patch_does_not_rewrite_paths_that_only_share_prefix(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            old_instance = tmp / "HGM"
            new_instance = tmp / "HGM2"
            game = new_instance / "Stock Game"
            old_posix = str(old_instance).replace("\\", "/")
            new_posix = str(new_instance).replace("\\", "/")
            new_win = new_posix.replace("/", "\\")

            ini_text = (
                "[General]\r\n"
                "\r\n"
                "[Settings]\r\n"
                f"base_directory={old_posix}\r\n"
                "\r\n"
                "[customExecutables]\r\n"
                "size=2\r\n"
                "1\\title=Already New Tool\r\n"
                f"1\\binary={new_posix}/mods/AlreadyNew/Tool.exe\r\n"
                f"1\\workingDirectory={new_win}\\explorer++\r\n"
                "1\\arguments=\r\n"
                "2\\title=Old Tool\r\n"
                f"2\\binary={old_posix}/mods/Old/Tool.exe\r\n"
                f"2\\workingDirectory={old_posix}/explorer++\r\n"
                "2\\arguments=\r\n"
            )

            (game / "Data").mkdir(parents=True, exist_ok=True)
            (game / "SkyrimSE.exe").write_bytes(b"")
            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=new_instance,
                game_path=game,
                tool_root=None,
                options=PatchOptions(backup=False),
            )

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn(f"1\\binary={new_posix}/mods/AlreadyNew/Tool.exe", patched)
            self.assertIn(f"1\\workingDirectory={new_win}\\explorer++", patched)
            self.assertIn(f"2\\binary={new_posix}/mods/Old/Tool.exe", patched)
            self.assertIn(f"2\\workingDirectory={new_posix}/explorer++", patched)
            self.assertNotIn("HGM22", patched)

    def test_patches_base_game_tools_and_args(self) -> None:
        ini_text = (
            "[General]\r\n"
            "gamePath=@ByteArray(C:\\\\Old\\\\Stock Game)\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
            "\r\n"
            "[customExecutables]\r\n"
            "size=1\r\n"
            "1\\title=Edit\r\n"
            "1\\binary=C:/Old/Tool/SSEEdit/SSEEdit.exe\r\n"
            "1\\workingDirectory=\r\n"
            "1\\arguments=-D:\\\"C:\\\\Old\\\\Stock Game\\\\Data\\\" -l:english\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                instance_root = Path("D:/New/Instance")
                game_root = Path("D:/New/Instance/Stock Game")
                tool_root = Path("D:/New/Instance/tools")

                (game_root / "Data").mkdir(parents=True, exist_ok=True)
                (game_root / "SkyrimSE.exe").write_bytes(b"")
                (tool_root / "SSEEdit").mkdir(parents=True, exist_ok=True)
                (tool_root / "SSEEdit" / "SSEEdit.exe").write_bytes(b"")

                report = patch_modorganizer_ini(
                    ini_path=ini_path,
                    instance_root=instance_root,
                    game_path=game_root,
                    tool_root=tool_root,
                    options=PatchOptions(apply_arg_presets=True, language="english", backup=False),
                )
            finally:
                os.chdir(old_cwd)

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn("base_directory=D:/New/Instance", patched)
            self.assertIn("gamePath=@ByteArray(D:\\\\New\\\\Instance\\\\Stock Game)", patched)
            self.assertIn("1\\binary=D:/New/Instance/tools/SSEEdit/SSEEdit.exe", patched)
            self.assertIn("1\\workingDirectory=D:/New/Instance/tools/SSEEdit", patched)
            self.assertIn("-D:\\\"D:\\\\New\\\\Instance\\\\Stock Game\\\\Data\\\" -l:english", patched)

    def test_args_override_template(self) -> None:
        ini_text = (
            "[General]\r\n"
            "gamePath=@ByteArray(C:\\\\Old\\\\Stock Game)\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
            "\r\n"
            "[customExecutables]\r\n"
            "size=1\r\n"
            "1\\title=Edit\r\n"
            "1\\binary=C:/Old/Tool/SSEEdit/SSEEdit.exe\r\n"
            "1\\workingDirectory=\r\n"
            "1\\arguments=\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                instance_root = Path("D:/New/Instance")
                game_root = Path("D:/New/Instance/Stock Game")
                tool_root = Path("D:/New/Instance/tools")

                (game_root / "Data").mkdir(parents=True, exist_ok=True)
                (game_root / "SkyrimSE.exe").write_bytes(b"")
                (tool_root / "SSEEdit").mkdir(parents=True, exist_ok=True)

                report = patch_modorganizer_ini(
                    ini_path=ini_path,
                    instance_root=instance_root,
                    game_path=game_root,
                    tool_root=tool_root,
                    options=PatchOptions(
                        apply_arg_presets=False,
                        backup=False,
                        args_overrides={"edit": '-D:"{data}" -l:korean'},
                    ),
                )
            finally:
                os.chdir(old_cwd)

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn("-D:\\\"D:\\\\New\\\\Instance\\\\Stock Game\\\\Data\\\" -l:korean", patched)

    def test_recent_directories_rewrite(self) -> None:
        ini_text = (
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
            "\r\n"
            "[recentDirectories]\r\n"
            "size=1\r\n"
            "1\\name=editExecutableBinary\r\n"
            "1\\directory=C:/Old/Instance/mods/PGPatcher\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=Path("D:/New/Instance"),
                game_path=None,
                tool_root=None,
                options=PatchOptions(backup=False),
            )

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn("1\\directory=D:/New/Instance/mods/PGPatcher", patched)

    def test_game_path_normalizes_to_exe_parent_dir(self) -> None:
        ini_text = (
            "[General]\r\n"
            "gamePath=@ByteArray(C:\\\\Old\\\\Game)\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                instance_root = Path("D:/New/Instance")
                stock_parent = Path("D:/New/Instance/STOCKGAME")
                game_dir = stock_parent / "Skyrim Special Edition"

                (game_dir / "Data").mkdir(parents=True, exist_ok=True)
                (game_dir / "SkyrimSE.exe").write_bytes(b"")

                report = patch_modorganizer_ini(
                    ini_path=ini_path,
                    instance_root=instance_root,
                    game_path=stock_parent,
                    tool_root=None,
                    options=PatchOptions(backup=False),
                )
            finally:
                os.chdir(old_cwd)

            self.assertTrue(report.ok)
            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn(
                "gamePath=@ByteArray(D:\\\\New\\\\Instance\\\\STOCKGAME\\\\Skyrim Special Edition)", patched
            )

    def test_rewrites_old_stockgame_paths_from_custom_executables(self) -> None:
        ini_text = (
            "[General]\r\n"
            "gamePath=@ByteArray(G:\\\\SteamLibrary\\\\steamapps\\\\common\\\\Skyrim Special Edition)\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=D:/ENIRIM Classic/SkyrimSE\r\n"
            "\r\n"
            "[customExecutables]\r\n"
            "size=2\r\n"
            "1\\title=SSEEdit\r\n"
            "1\\binary=D:/ENIRIM Classic/Tools/SSEEdit/SSEEdit.exe\r\n"
            "1\\workingDirectory=D:/ENIRIM Classic/STOCKGAME\r\n"
            "1\\arguments=-d:\\\"D:\\\\ENIRIM Classic\\\\STOCKGAME\\\\data\\\" -l:korean\r\n"
            "2\\title=Explore Virtual Folder\r\n"
            "2\\binary=D:/ENIRIM Classic/MO2/explorer++/Explorer++.exe\r\n"
            "2\\workingDirectory=D:/ENIRIM Classic/MO2/explorer++\r\n"
            "2\\arguments=\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)

            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                pack_root = Path("G:/ENIRIM Classic")
                instance_root = pack_root / "SkyrimSE"
                game_root = pack_root / "STOCKGAME"
                tool_root = pack_root / "Tools"

                (instance_root / "mods").mkdir(parents=True, exist_ok=True)
                (instance_root / "profiles").mkdir(parents=True, exist_ok=True)
                (game_root / "Data").mkdir(parents=True, exist_ok=True)
                (game_root / "SkyrimSE.exe").write_bytes(b"")
                (tool_root / "SSEEdit").mkdir(parents=True, exist_ok=True)
                (tool_root / "SSEEdit" / "SSEEdit.exe").write_bytes(b"")

                ini_path = pack_root / "MO2" / "ModOrganizer.ini"
                ini_path.parent.mkdir(parents=True, exist_ok=True)
                _write_bytes(ini_path, ini_text)

                report = patch_modorganizer_ini(
                    ini_path=ini_path,
                    instance_root=instance_root,
                    game_path=game_root,
                    tool_root=tool_root,
                    options=PatchOptions(backup=False),
                )
            finally:
                os.chdir(old_cwd)

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = (tmp / ini_path).read_text(encoding="utf-8")
            self.assertIn("base_directory=G:/ENIRIM Classic/SkyrimSE", patched)
            self.assertIn("gamePath=@ByteArray(G:\\\\ENIRIM Classic\\\\STOCKGAME)", patched)
            self.assertIn("1\\workingDirectory=G:/ENIRIM Classic/STOCKGAME", patched)
            self.assertIn('1\\arguments=-d:\\\"G:\\\\ENIRIM Classic\\\\STOCKGAME\\\\data\\\" -l:korean', patched)
            self.assertIn("2\\binary=G:/ENIRIM Classic/MO2/explorer++/Explorer++.exe", patched)
            self.assertIn("2\\workingDirectory=G:/ENIRIM Classic/MO2/explorer++", patched)

    def test_auto_add_missing_executables(self) -> None:
        ini_text = (
            "[General]\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
            "\r\n"
            "[customExecutables]\r\n"
            "size=0\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Instance Root"
            tools = instance / "tools"
            mods = instance / "mods"
            game = instance / "Stock Game" / "Skyrim Special Edition"

            (tools / "SSEEdit").mkdir(parents=True, exist_ok=True)
            (tools / "DynDOLOD").mkdir(parents=True, exist_ok=True)
            (tools / "xLODGen").mkdir(parents=True, exist_ok=True)
            (tools / "Synthesis").mkdir(parents=True, exist_ok=True)

            (mods / "Nemesis Unlimited Behavior Engine").mkdir(parents=True, exist_ok=True)
            (mods / "Pandora Behaviour Engine 4.0.4").mkdir(parents=True, exist_ok=True)
            (mods / "PGPatcher-0.9.9" / "PGPatcher").mkdir(parents=True, exist_ok=True)

            (game / "Data").mkdir(parents=True, exist_ok=True)
            (game / "SkyrimSE.exe").write_bytes(b"")

            (tools / "SSEEdit" / "SSEEdit.exe").write_bytes(b"")
            (tools / "SSEEdit" / "SSEEditQuickAutoClean.exe").write_bytes(b"")
            (tools / "DynDOLOD" / "TexGenx64.exe").write_bytes(b"")
            (tools / "DynDOLOD" / "DynDOLODx64.exe").write_bytes(b"")
            (tools / "xLODGen" / "xLODGenx64.exe").write_bytes(b"")
            (tools / "Synthesis" / "Synthesis.exe").write_bytes(b"")

            (mods / "Nemesis Unlimited Behavior Engine" / "Nemesis Unlimited Behavior Engine.exe").write_bytes(b"")
            (mods / "Pandora Behaviour Engine 4.0.4" / "Pandora Behaviour Engine+.exe").write_bytes(b"")
            (mods / "PGPatcher-0.9.9" / "PGPatcher" / "PGPatcher.exe").write_bytes(b"")

            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=game,
                tool_root=tools,
                options=PatchOptions(auto_add_missing=True, apply_arg_presets=False, backup=False),
            )

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            # Auto-added titles
            self.assertIn("\\title=Edit", patched)
            self.assertIn("\\title=Quick Auto Clean", patched)
            self.assertIn("\\title=TexGen", patched)
            self.assertIn("\\title=DynDOLOD", patched)
            self.assertIn("\\title=xLODGen", patched)
            self.assertIn("\\title=Synthesis", patched)
            self.assertIn("\\title=Nemesis", patched)
            self.assertIn("\\title=Pandora Behaviour Engine+", patched)
            self.assertIn("\\title=PGPatcher", patched)

    def test_auto_add_missing_can_skip_pandora(self) -> None:
        ini_text = (
            "[General]\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
            "\r\n"
            "[customExecutables]\r\n"
            "size=0\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Instance Root"
            mods = instance / "mods"

            (mods / "Nemesis Unlimited Behavior Engine").mkdir(parents=True, exist_ok=True)
            (mods / "Pandora Behaviour Engine 4.0.4").mkdir(parents=True, exist_ok=True)
            (mods / "PGPatcher-0.9.9" / "PGPatcher").mkdir(parents=True, exist_ok=True)

            (mods / "Nemesis Unlimited Behavior Engine" / "Nemesis Unlimited Behavior Engine.exe").write_bytes(b"")
            (mods / "Pandora Behaviour Engine 4.0.4" / "Pandora Behaviour Engine+.exe").write_bytes(b"")
            (mods / "PGPatcher-0.9.9" / "PGPatcher" / "PGPatcher.exe").write_bytes(b"")

            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=None,
                tool_root=None,
                options=PatchOptions(
                    auto_add_missing=True,
                    skip_auto_add_titles=("Pandora Behaviour Engine+",),
                    backup=False,
                ),
            )

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn("\\title=Nemesis", patched)
            self.assertIn("\\title=PGPatcher", patched)
            self.assertNotIn("\\title=Pandora Behaviour Engine+", patched)
            self.assertNotIn("Pandora Behaviour Engine+.exe", patched)

    def test_arg_presets_can_skip_existing_pandora_arguments(self) -> None:
        ini_text = (
            "[General]\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
            "\r\n"
            "[customExecutables]\r\n"
            "size=2\r\n"
            "1\\arguments=-D:\\\"C:\\\\Old\\\\Game\\\\Data\\\" -l:english\r\n"
            "1\\binary=C:/Tools/SSEEdit/SSEEdit.exe\r\n"
            "1\\hide=false\r\n"
            "1\\ownicon=false\r\n"
            "1\\steamAppID=\r\n"
            "1\\title=Edit\r\n"
            "1\\toolbar=false\r\n"
            "1\\workingDirectory=C:/Tools/SSEEdit\r\n"
            "2\\arguments=\r\n"
            "2\\binary=C:/Old/Instance/mods/Pandora/Pandora Behaviour Engine+.exe\r\n"
            "2\\hide=false\r\n"
            "2\\ownicon=false\r\n"
            "2\\steamAppID=\r\n"
            "2\\title=Pandora Behaviour Engine+\r\n"
            "2\\toolbar=true\r\n"
            "2\\workingDirectory=C:/Old/Instance/mods/Pandora\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Instance Root"
            game = instance / "Stock Game"

            (game / "Data").mkdir(parents=True, exist_ok=True)
            (game / "SkyrimSE.exe").write_bytes(b"")

            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=game,
                tool_root=None,
                options=PatchOptions(
                    apply_arg_presets=True,
                    skip_arg_preset_titles=("Pandora Behaviour Engine+",),
                    backup=False,
                ),
            )

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn('1\\arguments=-D:\\"', patched)
            self.assertIn("-l:korean", patched)
            self.assertIn("2\\arguments=", patched.splitlines())
            self.assertNotIn("2\\arguments=--tesv", patched)
            self.assertNotIn("Pandora Output", patched)

    def test_auto_add_pgpatcher_from_proteus_mod_folder(self) -> None:
        ini_text = (
            "[General]\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
            "\r\n"
            "[customExecutables]\r\n"
            "size=0\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Instance Root"
            mods = instance / "mods"

            pg_dir = mods / "Project Proteus" / "PGPatcher"
            pg_dir.mkdir(parents=True, exist_ok=True)
            (pg_dir / "PGPatcher.exe").write_bytes(b"")

            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=None,
                tool_root=None,
                options=PatchOptions(auto_add_missing=True, apply_arg_presets=False, backup=False),
            )

            self.assertTrue(report.ok)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn("\\title=PGPatcher", patched)
            self.assertIn(str(pg_dir / "PGPatcher.exe").replace("\\", "/"), patched)

    def test_auto_add_sseedit_from_mod_folder(self) -> None:
        ini_text = (
            "[General]\r\n"
            "\r\n"
            "[Settings]\r\n"
            "base_directory=C:/Old/Instance\r\n"
            "\r\n"
            "[customExecutables]\r\n"
            "size=0\r\n"
        )

        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Instance Root"
            mods = instance / "mods"

            edit_dir = mods / "SSEEdit"
            edit_dir.mkdir(parents=True, exist_ok=True)
            (edit_dir / "SSEEdit.exe").write_bytes(b"")
            (edit_dir / "SSEEditQuickAutoClean.exe").write_bytes(b"")

            ini_path = tmp / "ModOrganizer.ini"
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=None,
                tool_root=None,
                options=PatchOptions(auto_add_missing=True, apply_arg_presets=False, backup=False),
            )

            self.assertTrue(report.ok)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn("\\title=Edit", patched)
            self.assertIn(str(edit_dir / "SSEEdit.exe").replace("\\", "/"), patched)


if __name__ == "__main__":
    unittest.main()
