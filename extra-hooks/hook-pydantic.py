from PyInstaller.utils.hooks import collect_submodules, copy_metadata

datas = copy_metadata("pydantic")
hiddenimports = collect_submodules("pydantic")
