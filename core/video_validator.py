"""Video download stabilization, container integrity, and readability validator."""
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Tuple

from core.system_checker import SystemChecker
from core.logger import logger

class VideoValidator:
    @classmethod
    def wait_for_file_stability(
        cls,
        file_path: str | Path,
        stability_duration_sec: float = 2.0,
        timeout_sec: float = 60.0
    ) -> Tuple[bool, str]:
        """
        Polls file until its size stops changing for `stability_duration_sec`
        and no temporary extensions (.crdownload, .tmp, .part) exist.
        """
        p = Path(file_path).resolve()
        start_time = time.time()
        last_size = -1
        stable_since: float | None = None

        logger.debug(f"Monitoring download stabilization for: {p.name}")

        while time.time() - start_time < timeout_sec:
            # Check for temporary download files
            temp_crdownload = p.with_name(p.name + ".crdownload")
            temp_tmp = p.with_name(p.name + ".tmp")
            temp_part = p.with_name(p.name + ".part")

            if temp_crdownload.exists() or temp_tmp.exists() or temp_part.exists():
                logger.debug("Download is still in progress (temporary extension active)...")
                time.sleep(1.0)
                stable_since = None
                continue

            if not p.is_file():
                time.sleep(0.5)
                continue

            try:
                curr_size = p.stat().st_size
            except OSError:
                time.sleep(0.5)
                continue

            if curr_size > 0 and curr_size == last_size:
                if stable_since is None:
                    stable_since = time.time()
                elif (time.time() - stable_since) >= stability_duration_sec:
                    logger.debug(f"File size stabilized at {curr_size} bytes: {p.name}")
                    return True, "File stabilized"
            else:
                last_size = curr_size
                stable_since = None

            time.sleep(0.5)

        return False, f"Timeout ({timeout_sec}s) waiting for download file to stabilize"

    @classmethod
    def validate_video_integrity(cls, video_path: str | Path) -> Tuple[bool, str]:
        """
        Runs an FFmpeg integrity probe on the video container and decodability.
        Returns: (is_valid: bool, reason: str)
        """
        p = Path(video_path).resolve()
        if not p.is_file():
            return False, f"File does not exist: {p}"

        size = p.stat().st_size
        if size < 1024:  # At least 1KB
            return False, f"File size too small ({size} bytes). Download may be corrupted."

        ffmpeg_exe = SystemChecker.find_ffmpeg()
        if not ffmpeg_exe:
            # If FFmpeg not available, at least size check passed
            return True, "Valid (basic check)"

        # Probe container by running null muxer read for 1 second
        cmd = [
            ffmpeg_exe,
            "-v", "error",
            "-i", str(p),
            "-f", "null",
            "-"
        ]

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                timeout=15
            )
            stderr_str = res.stderr.decode("utf-8", errors="replace").strip()
            # If severe error was output
            if res.returncode != 0:
                logger.warning(f"Video container probe warning on {p.name}: {stderr_str}")
                return False, f"Video decoding failed: {stderr_str[:200]}"

            return True, "Video container verified successfully"
        except subprocess.TimeoutExpired:
            return False, "FFmpeg validation probe timed out"
        except Exception as e:
            return False, f"Validation error: {e}"


if __name__ == "__main__":
    print("Testing VideoValidator...")
    res, msg = VideoValidator.validate_video_integrity("nonexistent.mp4")
    print("Nonexistent test:", res, msg)
