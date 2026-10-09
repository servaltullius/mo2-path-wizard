import unittest
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


def _posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def _escaped_win(path: Path) -> str:
    """INI의 @ByteArray/arguments 안에 들어가는 백슬래시 2개 형태."""
    return str(path).replace("/", "\\").replace("\\", "\\\\")


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

            instance_root = tmp / "New" / "Instance"
            game_root = instance_root / "Stock Game"
            tool_root = instance_root / "tools"

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

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn(f"base_directory={_posix(instance_root)}", patched)
            self.assertIn(f"gamePath=@ByteArray({_escaped_win(game_root)})", patched)
            self.assertIn(f"1\\binary={_posix(tool_root)}/SSEEdit/SSEEdit.exe", patched)
            self.assertIn(f"1\\workingDirectory={_posix(tool_root)}/SSEEdit", patched)
            self.assertIn(f'-D:\\"{_escaped_win(game_root / "Data")}\\" -l:english', patched)

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

            instance_root = tmp / "New" / "Instance"
            game_root = instance_root / "Stock Game"
            tool_root = instance_root / "tools"

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

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn(f'-D:\\"{_escaped_win(game_root / "Data")}\\" -l:korean', patched)

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

            instance_root = tmp / "New" / "Instance"
            stock_parent = instance_root / "STOCKGAME"
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

            self.assertTrue(report.ok)
            patched = ini_path.read_text(encoding="utf-8")
            self.assertIn(f"gamePath=@ByteArray({_escaped_win(game_dir)})", patched)

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
            # 실제 드라이브(G:\ 등)에 쓰지 않도록 임시 폴더를 새 모드팩 위치로 사용한다.
            pack_root = Path(td) / "ENIRIM Classic"
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

            self.assertTrue(report.ok)
            self.assertTrue(report.changed)

            patched = ini_path.read_text(encoding="utf-8")
            self.assertNotIn("D:/ENIRIM Classic", patched)
            self.assertIn(f"base_directory={_posix(instance_root)}", patched)
            self.assertIn(f"gamePath=@ByteArray({_escaped_win(game_root)})", patched)
            self.assertIn(f"1\\workingDirectory={_posix(game_root)}", patched)
            self.assertIn(f'1\\arguments=-d:\\"{_escaped_win(game_root / "data")}\\" -l:korean', patched)
            self.assertIn(f"2\\binary={_posix(pack_root)}/MO2/explorer++/Explorer++.exe", patched)
            self.assertIn(f"2\\workingDirectory={_posix(pack_root)}/MO2/explorer++", patched)

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

    def test_existing_pandora_auto_detect_skips_nemesis_and_pandora_preset(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Pack"
            pack = _posix(instance)
            ini_text = (
                "[customExecutables]\r\n"
                "size=1\r\n"
                "1\\arguments=\r\n"
                f"1\\binary={pack}/mods/Pandora/Pandora Behaviour Engine+.exe\r\n"
                "1\\hide=false\r\n"
                "1\\ownicon=false\r\n"
                "1\\steamAppID=\r\n"
                "1\\title=Pandora Behaviour Engine+\r\n"
                "1\\toolbar=true\r\n"
                f"1\\workingDirectory={pack}/mods/Pandora\r\n"
            )
            mods = instance / "mods"
            game = instance / "Stock Game"
            nemesis = mods / "Nemesis Unlimited Behavior Engine"
            nemesis.mkdir(parents=True)
            (nemesis / "Nemesis Unlimited Behavior Engine.exe").write_bytes(b"")
            (game / "Data").mkdir(parents=True)
            (game / "SkyrimSE.exe").write_bytes(b"")

            ini_path = instance / "ModOrganizer.ini"
            ini_path.parent.mkdir(parents=True, exist_ok=True)
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=game,
                tool_root=None,
                options=PatchOptions(auto_add_missing=True, apply_arg_presets=True, backup=False),
            )
            patched = ini_path.read_text(encoding="utf-8")

        self.assertTrue(report.ok)
        self.assertFalse(report.changed)

        self.assertIn("size=1", patched)
        self.assertIn("1\\arguments=", patched.splitlines())
        self.assertNotIn("\\title=Nemesis", patched)
        self.assertNotIn("Pandora Output", patched)

    def test_existing_nemesis_auto_detect_skips_pandora_auto_add(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Pack"
            pack = _posix(instance)
            ini_text = (
                "[customExecutables]\r\n"
                "size=1\r\n"
                "1\\arguments=\r\n"
                f"1\\binary={pack}/mods/Nemesis/Nemesis Unlimited Behavior Engine.exe\r\n"
                "1\\hide=false\r\n"
                "1\\ownicon=false\r\n"
                "1\\steamAppID=\r\n"
                "1\\title=Nemesis\r\n"
                "1\\toolbar=true\r\n"
                f"1\\workingDirectory={pack}/mods/Nemesis\r\n"
            )
            pandora = instance / "mods" / "Pandora Behaviour Engine"
            pandora.mkdir(parents=True)
            (pandora / "Pandora Behaviour Engine+.exe").write_bytes(b"")

            ini_path = instance / "ModOrganizer.ini"
            ini_path.parent.mkdir(parents=True, exist_ok=True)
            _write_bytes(ini_path, ini_text)

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=None,
                tool_root=None,
                options=PatchOptions(auto_add_missing=True, backup=False),
            )
            patched = ini_path.read_text(encoding="utf-8")

        self.assertTrue(report.ok)
        self.assertFalse(report.changed)

        self.assertIn("size=1", patched)
        self.assertIn("1\\title=Nemesis", patched)
        self.assertNotIn("\\title=Pandora Behaviour Engine+", patched)

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
                    overwrite_existing_args=True,
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



def _custom_entries(text: str) -> dict[int, dict[str, str]]:
    entries: dict[int, dict[str, str]] = {}
    in_section = False
    for line in text.splitlines():
        if line.startswith("["):
            in_section = line.strip() == "[customExecutables]"
            continue
        if not in_section or "\\" not in line.split("=", 1)[0]:
            continue
        key, value = line.split("=", 1)
        idx, name = key.split("\\", 1)
        entries.setdefault(int(idx), {})[name] = value
    return entries


class TestPatcherRegressions(unittest.TestCase):
    def _make_synthesis(self, tmp: Path) -> Path:
        tool = tmp / "Instance" / "tools" / "Synthesis"
        tool.mkdir(parents=True)
        (tool / "Synthesis.exe").write_bytes(b"")
        return tmp / "Instance"

    def _run(self, ini_path: Path, instance: Path, **opts) -> str:
        report = patch_modorganizer_ini(
            ini_path=ini_path,
            instance_root=instance,
            game_path=None,
            tool_root=None,
            options=PatchOptions(backup=False, **opts),
        )
        self.assertTrue(report.ok)
        return ini_path.read_text(encoding="utf-8")

    def test_auto_add_without_size_line_keeps_existing_entries(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = self._make_synthesis(tmp)
            ini_path = instance / "ModOrganizer.ini"
            _write_bytes(
                ini_path,
                "[customExecutables]\r\n"
                "1\\arguments=-foo\r\n"
                "1\\binary=C:/Keep/One.exe\r\n"
                "1\\title=One\r\n"
                "2\\arguments=-bar\r\n"
                "2\\binary=C:/Keep/Two.exe\r\n"
                "2\\title=Two\r\n"
                "\r\n"
                "[Settings]\r\n"
                "language=ko\r\n",
            )

            patched = self._run(ini_path, instance, auto_add_missing=True)

            entries = _custom_entries(patched)
            self.assertEqual({"arguments": "-foo", "binary": "C:/Keep/One.exe", "title": "One"}, entries[1])
            self.assertEqual({"arguments": "-bar", "binary": "C:/Keep/Two.exe", "title": "Two"}, entries[2])
            self.assertEqual("Synthesis", entries[3]["title"])
            self.assertIn("size=3", patched.splitlines())
            self.assertIn("[Settings]\nlanguage=ko", patched)

    def test_auto_add_never_reuses_index_beyond_size(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = self._make_synthesis(tmp)
            ini_path = instance / "ModOrganizer.ini"
            _write_bytes(
                ini_path,
                "[customExecutables]\r\n"
                "size=1\r\n"
                "1\\binary=C:/Keep/One.exe\r\n"
                "1\\title=One\r\n"
                "2\\binary=C:/Keep/Two.exe\r\n"
                "2\\title=Two\r\n",
            )

            patched = self._run(ini_path, instance, auto_add_missing=True)

            entries = _custom_entries(patched)
            self.assertEqual("Two", entries[2]["title"])
            self.assertEqual("C:/Keep/Two.exe", entries[2]["binary"])
            self.assertEqual("Synthesis", entries[3]["title"])
            self.assertIn("size=3", patched.splitlines())

    def test_presets_do_not_touch_game_exes_or_existing_args(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Pack"
            game = instance / "Stock Game"
            (game / "Data").mkdir(parents=True)
            (game / "SkyrimSE.exe").write_bytes(b"")
            ini_path = instance / "ModOrganizer.ini"
            _write_bytes(
                ini_path,
                "[customExecutables]\r\n"
                "size=4\r\n"
                "1\\arguments=\r\n"
                f"1\\binary={_posix(game)}/SkyrimSE.exe\r\n"
                "1\\title=Skyrim Special Edition\r\n"
                "2\\arguments=\r\n"
                f"2\\binary={_posix(instance)}/TOOLS/zEdit/zEdit.exe\r\n"
                "2\\title=zEdit\r\n"
                "3\\arguments=-IKnowWhatImDoing -PseudoESL\r\n"
                f"3\\binary={_posix(instance)}/TOOLS/SSEEdit/SSEEdit64.exe\r\n"
                "3\\title=SSEEdit (64bit)\r\n"
                "4\\arguments=\r\n"
                f"4\\binary={_posix(instance)}/TOOLS/SSEEdit/SSEEdit.exe\r\n"
                "4\\title=SSEEdit\r\n",
            )

            report = patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=game,
                tool_root=None,
                options=PatchOptions(apply_arg_presets=True, backup=False),
            )
            self.assertTrue(report.ok)
            entries = _custom_entries(ini_path.read_text(encoding="utf-8"))

            self.assertEqual("", entries[1]["arguments"])
            self.assertEqual("", entries[2]["arguments"])
            self.assertEqual("-IKnowWhatImDoing -PseudoESL", entries[3]["arguments"])
            self.assertIn(_escaped_win(game / "Data"), entries[4]["arguments"])

    def test_overwrite_existing_args_replaces_xedit_args_only(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "Pack"
            game = instance / "Stock Game"
            (game / "Data").mkdir(parents=True)
            (game / "SkyrimSE.exe").write_bytes(b"")
            ini_path = instance / "ModOrganizer.ini"
            _write_bytes(
                ini_path,
                "[customExecutables]\r\n"
                "size=2\r\n"
                "1\\arguments=-custom\r\n"
                f"1\\binary={_posix(game)}/SkyrimSE.exe\r\n"
                "1\\title=Skyrim Special Edition\r\n"
                "2\\arguments=-old\r\n"
                f"2\\binary={_posix(instance)}/TOOLS/SSEEdit/SSEEdit.exe\r\n"
                "2\\title=SSEEdit\r\n",
            )

            patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=game,
                tool_root=None,
                options=PatchOptions(apply_arg_presets=True, overwrite_existing_args=True, backup=False),
            )
            entries = _custom_entries(ini_path.read_text(encoding="utf-8"))

            self.assertEqual("-custom", entries[1]["arguments"])
            self.assertIn("-l:korean", entries[2]["arguments"])

    def test_korean_game_path_is_written_in_qt_bytearray_form(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            instance = tmp / "모드팩"
            game = instance / "Stock Game"
            (game / "Data").mkdir(parents=True)
            (game / "SkyrimSE.exe").write_bytes(b"")
            ini_path = instance / "ModOrganizer.ini"
            _write_bytes(ini_path, "[General]\r\ngamePath=@ByteArray(D:\\\\Old\\\\Stock Game)\r\n")

            patch_modorganizer_ini(
                ini_path=ini_path,
                instance_root=instance,
                game_path=game,
                tool_root=None,
                options=PatchOptions(backup=False),
            )
            patched = ini_path.read_text(encoding="utf-8")

            line = next(l for l in patched.splitlines() if l.startswith("gamePath="))
            self.assertNotIn("모드팩", line)
            self.assertIn("\\xeb\\xaa\\xa8", line)
            from mo2_path_wizard import qtini

            self.assertEqual(str(game).replace("/", "\\"), qtini.decode_path_bytearray(line.split("=", 1)[1]))

    def test_sibling_folder_with_space_dash_is_not_rewritten(self) -> None:
        rules = _build_replacements("D:/TAKEALOOK", "G:/TAKEALOOK")
        value = '-o:\\"D:\\\\TAKEALOOK - Outputs\\\\lodgen output\\" -d:\\"D:\\\\TAKEALOOK\\\\Stock Game\\\\Data\\"'
        out = _apply_replacements(value, rules)
        self.assertIn("D:\\\\TAKEALOOK - Outputs", out)
        self.assertIn("G:\\\\TAKEALOOK\\\\Stock Game", out)

    def test_space_before_next_flag_still_ends_path(self) -> None:
        rules = _build_replacements("D:/Pack", "G:/Pack")
        self.assertEqual("-o:G:/Pack -sse", _apply_replacements("-o:D:/Pack -sse", rules))
        self.assertEqual("G:/Pack", _apply_replacements("D:/Pack", rules))

    def test_replacement_into_nested_new_root_is_not_chained(self) -> None:
        rules = _build_replacements("D:/X", "D:/X/Lists/Pack") + _build_replacements("D:/X", "D:/X/Lists/Pack")
        out = _apply_replacements("D:/X/Stock Game/skse64_loader.exe", rules)
        self.assertEqual("D:/X/Lists/Pack/Stock Game/skse64_loader.exe", out)

    def test_replacement_is_case_insensitive(self) -> None:
        rules = _build_replacements("D:/Old", "E:/New")
        self.assertEqual("E:/New/mods/a.exe", _apply_replacements("d:/old/mods/a.exe", rules))
        self.assertEqual("E:\\New\\x", _apply_replacements("D:\\OLD\\x", rules))

    def test_replacement_requires_start_boundary(self) -> None:
        rules = _build_replacements("tmp/pack/tools", "/tmp/new/tools")
        self.assertEqual("/tmp/pack/tools/a.exe", _apply_replacements("/tmp/pack/tools/a.exe", rules))



def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _patch(ini_path: Path, instance=None, game=None, tools=None, **opts):
    return patch_modorganizer_ini(
        ini_path=ini_path, instance_root=instance, game_path=game, tool_root=tools, options=PatchOptions(backup=False, **opts)
    )


class TestPatcherV110(unittest.TestCase):
    def test_settings_directories_and_plugin_paths_are_rewritten(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            (pack / "mods").mkdir(parents=True)
            ini = pack / "ModOrganizer.ini"
            _write_bytes(
                ini,
                "[Settings]\r\n"
                "base_directory=D:/Pack\r\n"
                "download_directory=D:/Pack/downloads\r\n"
                "cache_directory=%BASE_DIR%/webcache\r\n"
                "\r\n"
                "[Plugins]\r\n"
                "FNIS%20Integration%20Tool\\fnis-path=D:/Pack/mods/FNIS/tools/GenerateFNIS_for_Users/GenerateFNISforUsers.exe\r\n",
            )
            _patch(ini, pack)
            text = ini.read_text(encoding="utf-8")
            self.assertIn(f"download_directory={_posix(pack)}/downloads", text)
            self.assertIn("cache_directory=%BASE_DIR%/webcache", text)
            self.assertIn(f"fnis-path={_posix(pack)}/mods/FNIS/tools/", text)

    def test_portable_pack_without_base_directory_or_tools_is_fully_moved(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "TAKEALOOK"
            _touch(pack / "mods" / "SKSE" / "Root" / "skse64_loader.exe")
            _touch(pack / "explorer++" / "Explorer++.exe")
            _touch(pack / "Stock Game" / "SkyrimSE.exe")
            (pack / "profiles").mkdir()
            ini = pack / "ModOrganizer.ini"
            _write_bytes(
                ini,
                "[General]\r\n"
                "gamePath=@ByteArray(D:\\\\TAKEALOOK\\\\Stock Game)\r\n"
                "\r\n"
                "[customExecutables]\r\n"
                "size=2\r\n"
                "1\\binary=D:/TAKEALOOK/mods/SKSE/Root/skse64_loader.exe\r\n"
                "1\\title=SKSE\r\n"
                "1\\workingDirectory=D:/TAKEALOOK/Stock Game\r\n"
                "2\\binary=D:/TAKEALOOK/explorer++/Explorer++.exe\r\n"
                "2\\title=Explore Virtual Folder\r\n"
                "2\\workingDirectory=D:\\\\TAKEALOOK\\\\explorer++\r\n"
                "\r\n"
                "[recentDirectories]\r\n"
                "size=1\r\n"
                "1\\directory=D:/TAKEALOOK/mods/(SFW) Nemesis/Nemesis_Engine\r\n",
            )
            report = _patch(ini)
            text = ini.read_text(encoding="utf-8")
            self.assertTrue(report.ok, report.summary)
            self.assertNotIn("D:/TAKEALOOK", text)
            self.assertNotIn("D:\\\\TAKEALOOK", text)
            self.assertIn(f"1\\binary={_posix(pack)}/mods/SKSE/Root/skse64_loader.exe", text)
            self.assertNotIn("base_directory", text)

    def test_copy_then_patch_points_to_the_copy(self) -> None:
        with TemporaryDirectory() as td:
            old = Path(td) / "Old"
            new = Path(td) / "New"
            for root in (old, new):
                _touch(root / "mods" / "SKSE" / "skse64_loader.exe")
            ini = new / "ModOrganizer.ini"
            _write_bytes(
                ini,
                f"[Settings]\r\nbase_directory={_posix(old)}\r\n\r\n[customExecutables]\r\nsize=1\r\n"
                f"1\\binary={_posix(old)}/mods/SKSE/skse64_loader.exe\r\n1\\title=SKSE\r\n",
            )
            _patch(ini)
            text = ini.read_text(encoding="utf-8")
            self.assertIn(f"base_directory={_posix(new)}", text)
            self.assertIn(f"1\\binary={_posix(new)}/mods/SKSE/skse64_loader.exe", text)

    def test_global_instance_without_instance_root_is_an_error(self) -> None:
        with TemporaryDirectory() as td:
            ini = Path(td) / "AppData" / "ModOrganizer.ini"
            ini.parent.mkdir()
            _write_bytes(ini, "[Settings]\r\nbase_directory=D:/Gone/Instance\r\n")
            report = _patch(ini)
            self.assertFalse(report.ok)
            self.assertIn("--instance-root", report.summary)
            self.assertEqual("[Settings]\r\nbase_directory=D:/Gone/Instance\r\n", ini.read_bytes().decode())

    def test_utf8_bom_ini_is_parsed(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            _touch(pack / "Stock Game" / "SkyrimSE.exe")
            (pack / "mods").mkdir()
            ini = pack / "ModOrganizer.ini"
            ini.write_bytes(b"\xef\xbb\xbf[General]\r\ngamePath=@ByteArray(D:\\\\Pack\\\\Stock Game)\r\n")
            _patch(ini)
            data = ini.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf[General]"))
            self.assertNotIn(b"D:\\\\Pack", data)

    def test_auto_add_creates_missing_section(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            _touch(pack / "tools" / "Synthesis" / "Synthesis.exe")
            ini = pack / "ModOrganizer.ini"
            _write_bytes(ini, "[General]\r\ngameName=Skyrim Special Edition\r\n")
            report = _patch(ini, pack, auto_add_missing=True)
            text = ini.read_text(encoding="utf-8")
            self.assertIn("Synthesis", report.added)
            self.assertIn("[customExecutables]\r\nsize=1\r\n1\\arguments=", ini.read_bytes().decode())
            self.assertIn(f"1\\binary={_posix(pack)}/tools/Synthesis/Synthesis.exe", text)

    def test_inferred_move_is_skipped_when_old_folder_still_exists(self) -> None:
        from unittest import mock

        from mo2_path_wizard import patcher
        from mo2_path_wizard.relocate import RootMove

        with TemporaryDirectory() as td:
            old = Path(td) / "A" / "TAKEALOOK"
            new = Path(td) / "B" / "TAKEALOOK"
            old.mkdir(parents=True)
            gone = Path(td) / "C" / "TAKEALOOK"
            moves = [RootMove(old_root=_posix(old), new_root=new, votes=3), RootMove(old_root=_posix(gone), new_root=new, votes=3)]
            rules: list = []
            applied: list = []
            warnings: list = []
            with mock.patch.object(patcher, "infer_root_moves", return_value=moves):
                patcher._add_inferred_moves(rules, applied, [], [new], warnings)
            self.assertEqual([(_posix(gone), _posix(new))], applied)
            self.assertTrue(any(_posix(old) in w and "그대로 둡니다" in w for w in warnings))

    def test_missing_binaries_are_reported(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            (pack / "mods").mkdir(parents=True)
            ini = pack / "ModOrganizer.ini"
            _write_bytes(ini, "[customExecutables]\r\nsize=1\r\n1\\binary=C:/Nowhere/EasyNPC.exe\r\n1\\title=EasyNPC\r\n")
            report = _patch(ini, pack, dry_run=True)
            self.assertEqual(["EasyNPC"], [e.title for e in report.missing_binaries])

    def test_edition_auto_uses_game_name(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "Pack"
            game = _touch(pack / "Stock Game" / "SkyrimVR.exe").parent
            (pack / "mods").mkdir()
            ini = pack / "ModOrganizer.ini"
            _write_bytes(ini, "[General]\r\ngameName=Skyrim VR\r\ngamePath=@ByteArray(D:\\\\Old)\r\n")
            _patch(ini, pack, edition="auto")
            from mo2_path_wizard import qtini

            line = next(l for l in ini.read_text(encoding="utf-8").splitlines() if l.startswith("gamePath="))
            self.assertEqual(str(game).replace("/", "\\"), qtini.decode_path_bytearray(line.split("=", 1)[1]))

    def test_external_configs_are_patched_even_when_ini_is_already_correct(self) -> None:
        with TemporaryDirectory() as td:
            pack = Path(td) / "TAKEALOOK"
            (pack / "mods").mkdir(parents=True)
            exe = _touch(pack / "TOOLS" / "BethINI Standalone" / "BethINI.exe")
            cfg = exe.parent / "BethINI.ini"
            cfg.write_bytes(b"sGamePath=D:\\TAKEALOOK\\Stock Game\\\r\nsModOrganizerPath=D:\\TAKEALOOK\\\r\n")
            ini = pack / "ModOrganizer.ini"
            _write_bytes(ini, f"[customExecutables]\r\nsize=1\r\n1\\binary={_posix(exe)}\r\n1\\title=BethINI\r\n")

            preview = _patch(ini, pack, dry_run=True)
            self.assertTrue(preview.changed)
            self.assertEqual([cfg], [c.path for c in preview.external])
            self.assertIn(b"D:\\TAKEALOOK", cfg.read_bytes())

            patch_modorganizer_ini(
                ini_path=ini, instance_root=pack, game_path=None, tool_root=None, options=PatchOptions(backup=True)
            )
            self.assertIn(f"sGamePath={str(pack)}".replace("/", "\\").encode(), cfg.read_bytes().replace(b"/", b"\\"))
            self.assertTrue(cfg.with_name("BethINI.ini.bak").is_file())

            off = _patch(ini, pack, dry_run=True, external_configs=False)
            self.assertEqual((), off.external)


if __name__ == "__main__":
    unittest.main()
