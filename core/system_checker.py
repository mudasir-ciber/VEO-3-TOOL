"""System inspector for Windows version, CPU architecture, storage, browsers, and FFmpeg."""
import os
import sys
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List

class SystemChecker:
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Collect comprehensive diagnostic and dependency information."""
        info = {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "platform_detail": platform.platform(),
            "architecture": platform.machine(),
            "is_64bit": sys.maxsize > 2**32,
            "python_version": sys.version.split()[0],
            "ffmpeg_available": False,
            "ffmpeg_path": None,
            "chrome_available": False,
            "chrome_path": None,
            "edge_available": False,
            "edge_path": None,
            "storage_free_gb": 0.0,
            "storage_total_gb": 0.0,
            "compatibility_passed": True,
            "compatibility_messages": []
        }

        # Check OS compatibility
        if info["os_name"] != "Windows":
            info["compatibility_passed"] = False
            info["compatibility_messages"].append(f"Chained Evolution Studio requires Windows (detected: {info['os_name']}).")
        else:
            try:
                major_version = int(platform.release())
                if major_version < 10:
                    info["compatibility_messages"].append(f"Windows 10 or 11 recommended (detected: Windows {platform.release()}).")
            except Exception:
                pass

        # Check CPU Architecture
        if not info["is_64bit"]:
            info["compatibility_messages"].append("32-bit Windows detected. 64-bit Windows is recommended for optimal video processing.")

        # Check Disk Storage
        try:
            drive = os.path.splitdrive(os.path.abspath("."))[0] or "C:"
            usage = shutil.disk_usage(drive + "\\")
            info["storage_free_gb"] = round(usage.free / (1024**3), 2)
            info["storage_total_gb"] = round(usage.total / (1024**3), 2)
            if info["storage_free_gb"] < 5.0:
                info["compatibility_messages"].append(
                    f"Low storage warning: Only {info['storage_free_gb']} GB free on {drive}. At least 5 GB is recommended."
                )
        except Exception as e:
            info["compatibility_messages"].append(f"Could not inspect disk usage: {e}")

        # Check FFmpeg
        ffmpeg_exe = SystemChecker.find_ffmpeg()
        if ffmpeg_exe:
            info["ffmpeg_available"] = True
            info["ffmpeg_path"] = str(ffmpeg_exe)
        else:
            info["compatibility_passed"] = False
            info["compatibility_messages"].append("FFmpeg could not be located or initialized.")

        # Check Google Chrome
        chrome_exe = SystemChecker.find_chrome()
        if chrome_exe:
            info["chrome_available"] = True
            info["chrome_path"] = str(chrome_exe)
        else:
            info["compatibility_messages"].append("Google Chrome not found in standard paths. Edge or Chromium fallback will be required.")

        # Check Microsoft Edge
        edge_exe = SystemChecker.find_edge()
        if edge_exe:
            info["edge_available"] = True
            info["edge_path"] = str(edge_exe)

        return info

    @staticmethod
    def find_ffmpeg() -> str | None:
        """Find FFmpeg in imageio_ffmpeg, system PATH, or local tools dir."""
        # 1. Try bundled imageio-ffmpeg
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.isfile(exe):
                return exe
        except Exception:
            pass

        # 2. Check local tools folder
        local_tool = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg.exe"
        if local_tool.is_file():
            return str(local_tool)

        # 3. Check system PATH
        path_exe = shutil.which("ffmpeg")
        if path_exe:
            return path_exe

        return None

    @staticmethod
    def find_chrome() -> str | None:
        """Find Google Chrome executable."""
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            shutil.which("chrome"),
            shutil.which("google-chrome")
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return None

    @staticmethod
    def find_edge() -> str | None:
        """Find Microsoft Edge executable."""
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            shutil.which("msedge")
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return None


if __name__ == "__main__":
    import pprint
    pprint.pprint(SystemChecker.get_system_info())
