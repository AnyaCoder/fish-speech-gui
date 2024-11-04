# fish-speech-gui

![linux_macos_packages](https://img.shields.io/github/actions/workflow/status/AnyaCoder/fish-speech-gui/ci.yml?label=linux-macos-build)

## Basic Setup

<img src="assets/example_1_basic.png" width="800" />

## Text to Speech

<img src="assets/example_1_tts.png" width="800" />

# Build from Source

```bash
conda create -n pyqt python=3.10
conda activate pyqt
pip install pdm
# for windows nuitka build
pip install nuitka
pdm install
pdm run build.py
```

# Debug

```bash
conda activate pyqt
python main.py
```

# Run

```
# windows
dist\fish.exe

# linux
dist/fish
```
