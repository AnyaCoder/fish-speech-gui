from pathlib import Path

import yaml

from fish.config import application_path, config

# Load i18n files from locales/ directory
i18n_path = application_path / "locales"
i18n_files = list(i18n_path.glob("*.yaml"))

i18n_map = {}
for i18n_file in i18n_files:
    with open(i18n_file, "r", encoding="utf-8") as f:
        i18n_map[i18n_file.stem] = yaml.safe_load(f.read())


def _t(key: str | list[str], locale: str | None = None, fallback: str = "en_US") -> str:
    if locale is None:
        locale = config.locale

    if isinstance(key, str):
        key = key.split(".")

    try:
        node = i18n_map[locale]
        for k in key:
            node = node[k]
    except KeyError:
        if locale != fallback:
            return _t(key, locale=fallback)

        return ".".join(key)

    return node


language_map = {k: v["name"] for k, v in i18n_map.items()}

__all__ = ["_t", "language_map"]
