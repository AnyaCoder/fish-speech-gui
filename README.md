# fish-speech-gui

## Basic Setup

<img src="fish/assets/example_1_basic.png" width="800" />

## Text to Speech

<img src="fish/assets/example_1_tts.png" width="800" />

# Build from Source

```bash
conda create -n pyqt python=3.10
conda activate pyqt
pip install pdm
pdm install
pdm run build.py
```

# Debug

```bash
conda activate pyqt
python fish/__main__.py
```

# Run

```
# windows
dist\fish.exe

# linux
dist/fish
```
