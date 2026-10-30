import os
import sys

# Add root directory and iconstudio directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICONSTUDIO_DIR = os.path.join(BASE_DIR, "iconstudio")

for path in [BASE_DIR, ICONSTUDIO_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

def main():
    if len(sys.argv) > 1:
        from iconstudio.cli import main as cli_main
        cli_main()
    else:
        from iconstudio.gui.app import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
