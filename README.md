# CHAINED EVOLUTION STUDIO

A production-grade native Windows desktop application built to automate chained image-to-video evolutions using **Google Flow** (powered by Google DeepMind's **Veo 3.1**).

Designed around the strict sequential evolution chain:
```
MASTER IMAGE
  → SCENE PROMPT
  → GENERATE VIDEO
  → WAIT FOR COMPLETION (No fixed timers)
  → DOWNLOAD VIDEO
  → VERIFY DOWNLOAD INTEGRITY
  → EXTRACT EXACT LAST VIDEO FRAME (FFmpeg)
  → USE LAST FRAME AS NEXT SCENE REFERENCE
  → RUN NEXT PROMPT
  → REPEAT
```

---

## 🌟 Core Architecture & Key Features

1. **Strict Sequential Execution Lock**:
   - Only ONE scene is processed at a time.
   - Scene $N+1$ is strictly locked until Scene $N$ is 100% generated, downloaded, verified, and its exact final frame is extracted.

2. **Absolute Batch Continuity**:
   - Work in batches (e.g. Batch 1: Scenes 1–10).
   - Once Scene 10 finishes, its final frame is recorded as the active reference.
   - When you load Batch 2 (Scenes 11–20), **Scene 11 automatically uses Scene 10's Last Frame**—the Master Image is strictly preserved for Scene 1 only.

3. **Exact Last-Frame Video Decoding (FFmpeg)**:
   - **Zero screen captures** or browser UI screenshots.
   - Uses bundled FFmpeg to decode the exact final video frame directly from the MP4 stream into `Last Frames/Scene X.png`.

4. **Legitimate Persistent Google Authentication**:
   - Uses a dedicated persistent browser profile directory (`browser_profile/`).
   - Your Google password is **never** asked for or stored.
   - Sign in once securely via Google's official sign-in page.

5. **Crash Safety & Auto-Recovery**:
   - All state is saved atomically to `Project State/state.json`.
   - If closed or interrupted, it automatically detects completed scenes and missing frames, re-extracting frames from existing MP4s without wasting generation credits.

6. **Native Windows Desktop UI (PySide6)**:
   - Modern Windows 11 Fluent dark theme.
   - Real-time sub-step status pills (Reference Upload, Video Generation, Video Download, Video Verification, Last Frame Extract).
   - Timestamped color-coded activity log.
   - Native Windows Success Chime and Failure Alert notifications.

---

## 📁 Project Directory Layout

Every project created in the studio follows this organized structure:

```
Your Project Name/
├── Master/
│   └── Master Image.png       # Starting master image
├── Videos/
│   ├── Scene 1.mp4            # Verified downloaded scene videos
│   ├── Scene 2.mp4
│   └── ...
├── Last Frames/
│   ├── Scene 1.png            # Exact decoded final video frames
│   ├── Scene 2.png
│   └── ...
├── Prompts/
│   ├── Scene 1.txt            # Individual prompt archives
│   ├── Scene 2.txt
│   └── ...
├── Project State/
│   └── state.json             # Atomic project state & chain pointers
└── Logs/
    └── activity.log           # Timestamped execution logs
```

---

## 🚀 Getting Started

### 1. Launching the Application
Double-click `run.bat` or run from PowerShell:
```powershell
.\.venv\Scripts\python.exe main.py
```

### 2. Basic Workflow
1. **Setup Project**: Enter a project name and select your workspace directory.
2. **Upload Master Image**: Pick your initial starting image (used exclusively for Scene 1).
3. **Enter Scene Prompts**: Paste your batch of prompts (e.g., `SCENE 1: ...`, `SCENE 2: ...`, or plain paragraphs).
4. **Click `RUN BATCH`**:
   - The studio will connect to Google Flow.
   - If it's your first time, log in to your Google Account in the opened browser window.
   - The studio will automatically execute each scene sequentially without any manual intervention.
5. **Batch Completion**:
   - Plays a celebratory success chime.
   - Automatically opens your `Videos/` folder.
   - Ready for your next batch of prompts!

### 3. Simulation / Dry-Run Mode
Check **"Simulation / Dry-Run Mode"** on the control bar to test your prompt lists, directory structure, FFmpeg extraction, and state recovery locally with zero Google Flow credits used.

---

## 🧪 Automated Test Suite
To run the full diagnostic and regression test suite:
```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_studio.py
```
