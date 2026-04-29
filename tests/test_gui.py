import unittest
from pathlib import Path

from mo2_path_wizard.gui import _PreviewContext, _format_run_output
from mo2_path_wizard.patcher import CustomExecutableEntry, PatchReport


class TestGuiPreviewOutput(unittest.TestCase):
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
        self.assertIn("[현재 등록된 실행 파일]", output)
        self.assertIn("1. SKSE", output)
        self.assertIn("G:/TAKEALOOK/mods/SKSE/skse64_loader.exe", output)
        self.assertIn("17. Pandora Behaviour Engine+", output)
        self.assertIn("[적용 예정 요약]", output)
        self.assertIn("- auto-add: Nemesis", output)
        self.assertIn("[변경 diff]", output)
        self.assertIn("- 는 현재 파일, + 는 적용 후 내용입니다.", output)
        self.assertLess(output.index("[현재 등록된 실행 파일]"), output.index("[변경 diff]"))


if __name__ == "__main__":
    unittest.main()
