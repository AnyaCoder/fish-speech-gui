import os
import platform
import subprocess as sp

package_type = os.environ.get("PACKAGE_TYPE", "onefile")
assert package_type in ("onedir", "onefile"), "PACKAGE_TYPE must be onedir or onefile"

# upgrade dependencies manually
if platform.system() == "Windows":
    sp.check_call(["pip", "install", "--upgrade", "pywin32", "cffi"])

sep = ";" if platform.system() == "Windows" else ":"

# Use nuitka for faster gui
if platform.system() == "Windows":
    args = [
        "python",
        "-m",
        "nuitka",
        # "--mingw64",
        "--standalone",
        f"--output-dir=dist",
        "--follow-import-to=fish",
        "main.py",
        f"--onefile",  # default onefile is enough (not unzipping)
        "--output-filename=fish",
        "--include-data-dir=assets=assets",
        "--include-data-dir=locales=locales",
        "--windows-disable-console",
        "--enable-plugins=pkg-resources",
        "--enable-plugins=pyqt6",
        "--nofollow-import-to=numpy,mkl,click",
        "--include-qt-plugins=sensible,multimedia",
        "--show-memory",
        "--show-progress",
        # "--debug",
    ]

else:
    args = [
        "pyinstaller",
        "main.py",
        f"--{package_type}",
        "-n",
        "fish",
        "--additional-hooks=extra-hooks",
        "--noconfirm",
        "--add-data",
        f"assets{sep}assets",
        "--add-data",
        f"locales{sep}locales",
        "--noconsole",
    ]

sp.check_call(args)
