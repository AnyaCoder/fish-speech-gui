import os
import platform
import subprocess as sp

package_type = os.environ.get("PACKAGE_TYPE", "onedir")
assert package_type in ("onedir", "onefile"), "PACKAGE_TYPE must be onedir or onefile"

# upgrade dependencies manually
if platform.system() == "Windows":
    sp.check_call(["pip", "install", "--upgrade", "pywin32", "cffi"])

sep = ";" if platform.system() == "Windows" else ":"

args = [
    "pyinstaller",
    "rtvc/__main__.py",
    f"--{package_type}",
    "-n",
    "rtvc",
    "--additional-hooks=extra-hooks",
    "--noconfirm",
    "--add-data",
    f"rtvc/assets{sep}assets",
    "--add-data",
    f"rtvc/locales{sep}locales",
]

sp.check_call(args)
