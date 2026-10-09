from __future__ import annotations

import sys

from mo2_path_wizard.cli import main as cli_main


def main() -> int:
    if len(sys.argv) == 1:
        # GUI(tkinter)는 인자 없이 실행할 때만 불러온다. tkinter가 없는 환경에서도 CLI는 동작해야 한다.
        from mo2_path_wizard.gui import main as gui_main

        gui_main()
        return 0
    return cli_main()

if __name__ == "__main__":
    raise SystemExit(main())
