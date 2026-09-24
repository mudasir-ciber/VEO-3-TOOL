"""Script to build standalone executable and create Desktop shortcut installer."""
import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def build():
    import playwright
    import imageio_ffmpeg

    playwright_dir = Path(playwright.__file__).parent
    imageio_dir = Path(imageio_ffmpeg.__file__).parent

    pw_driver = playwright_dir / "driver"
    ff_binaries = imageio_dir / "binaries"

    print("=== BUILDING CHAINED EVOLUTION STUDIO EXECUTABLE ===")
    print(f"Base Directory: {BASE_DIR}")
    print(f"Playwright Driver: {pw_driver}")
    print(f"FFmpeg Binaries: {ff_binaries}")

    # PyInstaller arguments
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name=ChainedEvolutionStudio",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--icon={BASE_DIR / 'app_icon.ico'}",
        f"--add-data={BASE_DIR / 'ui' / 'styles' / 'dark_theme.qss'};ui/styles",
        f"--add-data={BASE_DIR / 'app_icon.ico'};.",
        f"--add-data={BASE_DIR / 'app_icon.png'};.",
        f"--add-data={BASE_DIR / 'extension'};extension",
        f"--add-data={pw_driver};playwright/driver",
        f"--add-data={ff_binaries};imageio_ffmpeg/binaries",
        "--hidden-import=PySide6",
        "--hidden-import=playwright",
        "--hidden-import=imageio_ffmpeg",
        "--hidden-import=PIL",
        str(BASE_DIR / "main.py")
    ]

    print("Running PyInstaller...")
    res = subprocess.run(cmd, cwd=str(BASE_DIR))
    if res.returncode != 0:
        print("Build failed with returncode:", res.returncode)
        return False

    print("=== BUILD COMPLETED SUCCESSFULLY ===")
    return True

if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
