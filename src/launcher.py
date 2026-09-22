"""
Entry point used ONLY for the PyInstaller .exe build (build_exe.bat).

Running `streamlit run app.py` normally works by shelling out to the
`streamlit` command - but inside a bundled .exe there's no separate
`streamlit` executable to find, so PyInstaller needs a plain Python script
that starts Streamlit in-process instead. This is the standard trick
recommended by Streamlit's own community docs for packaging with
PyInstaller. Not used at all when running normally via `run_app.bat` /
`streamlit run app.py` - those don't touch this file.
"""
import os
import sys

from streamlit.web import cli as stcli


def resolve_path(path: str) -> str:
    if getattr(sys, "frozen", False):
        # Running from inside the PyInstaller-built .exe
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, path)


if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())
