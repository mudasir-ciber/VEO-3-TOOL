"""Exact last-frame video extraction using bundled/system FFmpeg."""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from core.system_checker import SystemChecker
from core.logger import logger

class FFmpegExtractor:
    @classmethod
    def get_ffmpeg_executable(cls) -> str:
        exe = SystemChecker.find_ffmpeg()
        if not exe:
            raise RuntimeError("FFmpeg executable not found. Please verify dependencies.")
        return exe

    @classmethod
    def extract_last_frame(cls, video_path: str | Path, output_png_path: str | Path) -> Tuple[bool, str]:
        """
        Extract the exact final frame of a video file into a PNG image.
        Guarantees clean frame extraction directly from the video stream.
        No screen captures or browser artifacts.
        
        Returns: (success: bool, message: str)
        """
        video_path = Path(video_path).resolve()
        output_png_path = Path(output_png_path).resolve()

        if not video_path.is_file():
            return False, f"Video file not found at: {video_path}"

        if video_path.stat().st_size == 0:
            return False, f"Video file is 0 bytes (empty/incomplete): {video_path}"

        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_exe = cls.get_ffmpeg_executable()

        # Strategy A: Precise backward seek (-sseof -0.5) with -update 1
        # Captures the final decoded video frame quickly.
        cmd_a = [
            ffmpeg_exe,
            "-y",                   # Overwrite output
            "-sseof", "-0.8",       # Seek to near the very end
            "-i", str(video_path),
            "-update", "1",
            "-q:v", "1",            # Highest PNG quality
            str(output_png_path)
        ]

        logger.debug(f"Attempting frame extraction Strategy A on: {video_path.name}")
        proc = subprocess.run(
            cmd_a,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )

        valid, err = cls.verify_image(output_png_path)
        if valid:
            logger.info(f"Successfully extracted exact last frame for {video_path.name} -> {output_png_path.name}")
            return True, "Success"

        # Strategy B: Fallback using stream reverse (-vf reverse -vframes 1)
        # Guaranteed true last frame on short clips even with irregular timestamps.
        logger.warning(f"Strategy A did not produce valid image ({err}). Trying Strategy B (reverse filter)...")
        cmd_b = [
            ffmpeg_exe,
            "-y",
            "-i", str(video_path),
            "-vf", "reverse",
            "-vframes", "1",
            str(output_png_path)
        ]

        proc_b = subprocess.run(
            cmd_b,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )

        valid_b, err_b = cls.verify_image(output_png_path)
        if valid_b:
            logger.info(f"Strategy B successfully extracted last frame for {video_path.name}")
            return True, "Success"

        # If both fail, return error with stderr details
        stderr_text = proc_b.stderr.decode("utf-8", errors="replace")[-400:]
        return False, f"Frame extraction failed: {err_b}. FFmpeg output: {stderr_text}"

    @classmethod
    def verify_image(cls, image_path: Path) -> Tuple[bool, str]:
        """Verify that the extracted image exists, is not corrupt, and has valid dimensions."""
        if not image_path.is_file():
            return False, "Output image file was not created"

        size = image_path.stat().st_size
        if size < 512:
            return False, f"Output image file is abnormally small ({size} bytes)"

        try:
            with Image.open(image_path) as img:
                img.verify()
            with Image.open(image_path) as img:
                w, h = img.size
                if w < 16 or h < 16:
                    return False, f"Image dimensions too small: {w}x{h}"
            return True, "Valid"
        except Exception as e:
            return False, f"Image verification error: {e}"


if __name__ == "__main__":
    print("Testing FFmpeg availability...")
    exe = FFmpegExtractor.get_ffmpeg_executable()
    print("Found FFmpeg:", exe)
