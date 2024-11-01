import os
import platform
import subprocess as sp

package_type = os.environ.get("PACKAGE_TYPE", "onefile")
assert package_type in ("onedir", "onefile"), "PACKAGE_TYPE must be onedir or onefile"

# upgrade dependencies manually
if platform.system() == "Windows":
    sp.check_call(["pip", "install", "--upgrade", "pywin32", "cffi"])

sep = ";" if platform.system() == "Windows" else ":"

args = [
    "pyinstaller",
    "fish/__main__.py",
    f"--{package_type}",
    "-n",
    "fish",
    "--additional-hooks=extra-hooks",
    "--noconfirm",
    "--add-data",
    f"fish/assets{sep}assets",
    "--add-data",
    f"fish/locales{sep}locales",
    "--noconsole",
]

sp.check_call(args)
