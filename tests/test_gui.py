import unittest
from pathlib import Path

from mo2_path_wizard.external import ExternalChange
from mo2_path_wizard.gui import _App, _PreviewContext, _format_run_output
from mo2_path_wizard.mo2proc import Mo2Status
from mo2_path_wizard.patcher import CustomExecutableEntry, PatchReport


class TestGuiPreviewOutput(unittest.TestCase):
    def test_primary_flow_labels_explain_preview_runs_auto_detect(self) -> None:
        app = _App()
        try:
            app.withdraw()

            self.assertEqual("경로만 자동 감지", app.btn_auto_detect.cget("text"))
            self.assertEqual("자동 감지 + 미리보기", app.btn_preview.cget("text"))
            self.assertIn("바로 미리보기를 누르면 자동 감지", app.modpack_hint.cget("text"))
        finally:
            app.destroy()

    def test_preview_output_includes_current_executables_before_diff(self) -> None:
        context = _PreviewContext(
            ini_path=Path("G:/TAKEALOOK/ModOrganizer.ini"),
            instance_root=Path("G:/TAKEALOOK"),
            game_path=Path("G:/TAKEALOOK/Stock Game"),
            tool_root=Path("G:/TAKEALOOK/TOOLS"),
            executables=(
                CustomExecutableEntry(
                    index=1,
                    title="SKSE",
                    binary="G:/TAKEALOOK/mods/SKSE/skse64_loader.exe",
                    working_directory="G:/TAKEALOOK/mods/SKSE",
                    arguments="",
                ),
                CustomExecutableEntry(
                    index=17,
                    title="Pandora Behaviour Engine+",
                    binary="G:/TAKEALOOK/mods/Pandora/Pandora Behaviour Engine+.exe",
                    working_directory="G:/TAKEALOOK/mods/Pandora",
                    arguments="",
                ),
            ),
        )
        report = PatchReport(
            ok=True,
            changed=True,
            summary="dry-run: 파일은 수정하지 않았습니다.\n- auto-add: Nemesis",
            diff="--- G:/TAKEALOOK/ModOrganizer.ini\n+++ G:/TAKEALOOK/ModOrganizer.ini\n+27\\title=Nemesis\n",
        )

        output = _format_run_output(dry_run=True, context=context, discovery_warnings=(), report=report)

        self.assertIn("[현재 감지된 경로]", output)
        self.assertIn("INI: G:/TAKEALOOK/ModOrganizer.ini", output)
        self.assertIn("[Pandora/Nemesis 자동 판단]", output)
        self.assertIn("Pandora 등록됨", output)
        self.assertIn("Nemesis 자동 추가", output)
        self.assertIn("[현재 등록된 실행 파일]", output)
        self.assertIn("1. SKSE", output)
        self.assertIn("G:/TAKEALOOK/mods/SKSE/skse64_loader.exe", output)
        self.assertIn("17. Pandora Behaviour Engine+", output)
        self.assertIn("[적용 예정 요약]", output)
        self.assertIn("- auto-add: Nemesis", output)
        self.assertIn("[변경 diff]", output)
        self.assertIn("- 는 현재 파일, + 는 적용 후 내용입니다.", output)
        self.assertLess(output.index("[현재 등록된 실행 파일]"), output.index("[변경 diff]"))


    def test_output_shows_mo2_status_external_configs_and_missing_executables(self) -> None:
        missing = CustomExecutableEntry(index=24, title="EasyNPC", binary="G:/Pack/TOOLS/EasyNPC/EasyNPC.exe", working_directory="", arguments="")
        context = _PreviewContext(
            ini_path=Path("G:/Pack/ModOrganizer.ini"),
            instance_root=Path("G:/Pack"),
            game_path=None,
            tool_root=None,
            executables=(missing,),
            mo2_status=Mo2Status(supported=True, running=(Path("G:/Pack/ModOrganizer.exe"),), same_instance=True),
            missing_indices=frozenset({24}),
        )
        report = PatchReport(
            ok=True,
            changed=True,
            summary="dry-run: 파일은 수정하지 않았습니다.",
            diff="",
            missing_binaries=(missing,),
            external=(
                ExternalChange(
                    tool="BethINI",
                    path=Path("G:/Pack/TOOLS/BethINI/BethINI.ini"),
                    changed_lines=(("sGamePath=D:\\Pack\\Stock Game\\", "sGamePath=G:\\Pack\\Stock Game\\"),),
                    count=1,
                    sensitive=False,
                    new_bytes=b"",
                ),
                ExternalChange(
                    tool="SSE-AT",
                    path=Path("G:/Pack/TOOLS/SSE-AT/data/user/config.json"),
                    changed_lines=(),
                    count=3,
                    sensitive=True,
                    new_bytes=b"",
                ),
            ),
        )

        output = _format_run_output(dry_run=True, context=context, discovery_warnings=(), report=report)

        self.assertIn("[MO2 실행 상태]", output)
        self.assertIn("이 모드팩의 MO2가 실행 중입니다", output)
        self.assertIn("24. EasyNPC  [warn] 실행 파일 없음", output)
        self.assertIn("[외부 툴 설정 파일]", output)
        self.assertIn("[BethINI]", output)
        self.assertIn("민감한 정보", output)
        self.assertIn("[실행 파일이 없는 항목]", output)

    def test_external_config_option_is_on_by_default(self) -> None:
        app = _App()
        try:
            app.withdraw()
            self.assertTrue(app.external_configs.get())
            self.assertEqual("auto", app.edition.get())
            inputs = app._snapshot_inputs(dry_run=True)
            self.assertTrue(inputs["external_configs"])
            self.assertFalse(inputs["force"])
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
