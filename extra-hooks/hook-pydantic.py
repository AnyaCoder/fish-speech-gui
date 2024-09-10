from PyInstaller.utils.hooks import copy_metadata, collect_submodules

datas = copy_metadata('pydantic')
hiddenimports = collect_submodules('pydantic')