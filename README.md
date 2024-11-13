# fish-speech-gui

![linux_macos_packages](https://img.shields.io/github/actions/workflow/status/AnyaCoder/fish-speech-gui/ci.yml?label=linux-macos-build)

## Features

1. **User-Friendly API Requests** :
   <u>Easily send requests to the Fish-Speech API</u> through a clean and intuitive interface. Users can quickly set up configurations, select voice settings, and manage audio processing with minimal setup.

2. **Integrated Audio Processing Toolkits**:
   Provides essential toolkits for various audio tasks, including <u>resampling, vocal separation, and transcription</u>. These tools are seamlessly integrated, allowing for smooth workflows and efficient processing of audio files.

3. **Extensibility and Flexibility**:
   Designed with extension in mind, the GUI supports adding new features and plugins, enabling users to tailor the tool to specific needs and projects.

4. **Real-Time Monitoring and Streaming**
   Offers options for real-time audio streaming and detailed latency information, enhancing user experience for both playback and synthesis monitoring.

## Basic Setup

<img src="images/basic.png" width="800" />

## Text to Speech

<img src="images/tts.png" width="800" />

## Chat With Your Agent

<img src="images/agent.png" width="800" />

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
