from __future__ import annotations

import sys

from mo2_path_wizard.cli import main as cli_main
from mo2_path_wizard.gui import main as gui_main


def main() -> int:
    if len(sys.argv) == 1:
        gui_main()
        return 0
    return cli_main()

if __name__ == "__main__":
    raise SystemExit(main())
