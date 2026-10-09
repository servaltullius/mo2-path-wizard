import unittest
from pathlib import Path

from mo2_path_wizard.presets import ArgContext, arg_preset_for, classify_tool


class TestClassifyTool(unittest.TestCase):
    def test_game_executables_are_never_presets(self) -> None:
        cases = (
            ("Skyrim Special Edition", "G:/Pack/Stock Game/SkyrimSE.exe"),
            ("Skyrim Special Edition Launcher", "G:/Pack/Stock Game/SkyrimSELauncher.exe"),
            ("SKSE", "G:/Pack/Stock Game/skse64_loader.exe"),
        )
        for title, binary in cases:
            with self.subTest(title=title):
                self.assertIsNone(classify_tool(title, binary))

    def test_title_without_binary_does_not_match_edition(self) -> None:
        self.assertIsNone(classify_tool("Skyrim Special Edition", ""))
        self.assertIsNone(classify_tool("zEdit", ""))
        self.assertEqual("xedit", classify_tool("SSEEdit (Quick Auto Clean)", ""))
        self.assertEqual("xedit", classify_tool("Edit", ""))

    def test_zedit_is_not_xedit(self) -> None:
        self.assertIsNone(classify_tool("zEdit", "G:/Pack/TOOLS/zEdit/zEdit.exe"))

    def test_xedit_variants(self) -> None:
        for exe in (
            "SSEEdit.exe",
            "SSEEdit64.exe",
            "SSEEditQuickAutoClean.exe",
            "xEdit.exe",
            "xEdit64.exe",
            "xEditQuickAutoClean.exe",
        ):
            with self.subTest(exe=exe):
                self.assertEqual("xedit", classify_tool("anything", f"G:/Pack/TOOLS/SSEEdit/{exe}"))

    def test_binary_decides_over_title(self) -> None:
        # title에 Edit이 있어도 실행 파일이 xEdit이 아니면 프리셋 대상이 아니다.
        self.assertIsNone(classify_tool("Edit Profile Notes", "C:/Windows/notepad.exe"))

    def test_lodgen_and_pandora(self) -> None:
        self.assertEqual("lodgen", classify_tool("DynDOLOD", "G:/Pack/TOOLS/DynDOLOD/DynDOLODx64.exe"))
        self.assertEqual("lodgen", classify_tool("TexGen", "G:/Pack/TOOLS/DynDOLOD/TexGenx64.exe"))
        self.assertEqual("lodgen", classify_tool("xLODGen", "G:/Pack/TOOLS/xLODGen/xLODGenx64.exe"))
        self.assertEqual(
            "pandora", classify_tool("Pandora", "G:/Pack/mods/Pandora/Pandora Behaviour Engine+.exe")
        )


class TestArgPreset(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = ArgContext(
            instance_root=Path("G:/Pack"), game_path=Path("G:/Pack/Stock Game"), edition="sse", language="korean"
        )

    def test_renamed_xedit_gets_game_mode_flag(self) -> None:
        preset = arg_preset_for("xEdit", "G:/Pack/TOOLS/xEdit/xEdit64.exe", self.ctx)
        self.assertIsNotNone(preset)
        self.assertTrue(preset.startswith("-sse "))

    def test_sseedit_has_no_extra_game_mode_flag(self) -> None:
        preset = arg_preset_for("SSEEdit", "G:/Pack/TOOLS/SSEEdit/SSEEdit.exe", self.ctx)
        self.assertTrue(preset.startswith("-D:"))

    def test_vr_flag_uses_tes5vr(self) -> None:
        ctx = ArgContext(instance_root=Path("G:/Pack"), game_path=Path("G:/VR"), edition="vr", language="english")
        self.assertIn("-tes5vr", arg_preset_for("DynDOLOD", "DynDOLODx64.exe", ctx))


if __name__ == "__main__":
    unittest.main()
