"""Mock Flow connector for testing, dry-runs, and automated validation."""
import os
import time
import subprocess
from pathlib import Path
from typing import Tuple, Optional

from core.ffmpeg_extractor import FFmpegExtractor
from core.video_validator import VideoValidator
from core.logger import logger
from connector.flow_base import BaseFlowConnector

class SimulatedFlowConnector(BaseFlowConnector):
    """
    Simulates Google Flow generation using local FFmpeg to produce genuine MP4s.
    Perfect for dry-run verification, UI testing, and regression suites.
    """
    def __init__(self, step_delay_sec: float = 1.0):
        self.step_delay = step_delay_sec
        self.is_connected = False
        self.current_reference: Optional[Path] = None
        self.current_prompt: Optional[str] = None

    def initialize(self, headless: bool = False, profile_dir: Optional[Path] = None) -> Tuple[bool, str]:
        self.is_connected = True
        logger.info("[SIMULATION MODE] Connector initialized.")
        return True, "Simulation initialized"

    def check_authenticated(self) -> Tuple[bool, str]:
        return True, "Authenticated (Simulation)"

    def prepare_scene_interface(self) -> Tuple[bool, str]:
        time.sleep(self.step_delay)
        return True, "Interface ready"

    def upload_reference(self, image_path: Path) -> Tuple[bool, str]:
        img = Path(image_path).resolve()
        if not img.is_file():
            return False, f"Reference image does not exist: {img}"
        self.current_reference = img
        time.sleep(self.step_delay)
        logger.info(f"[SIMULATION MODE] Reference uploaded: {img.name}")
        return True, "Reference uploaded"

    def submit_prompt(self, prompt_text: str) -> Tuple[bool, str]:
        self.current_prompt = prompt_text
        time.sleep(self.step_delay)
        logger.info(f"[SIMULATION MODE] Prompt submitted: {prompt_text[:40]}...")
        return True, "Prompt submitted"

    def trigger_generation(self) -> Tuple[bool, str]:
        time.sleep(self.step_delay)
        logger.info("[SIMULATION MODE] Generation started...")
        return True, "Generation started"

    def wait_for_completion(self, timeout_sec: float = 600.0) -> Tuple[bool, str]:
        time.sleep(self.step_delay * 2)
        logger.info("[SIMULATION MODE] Generation finished.")
        return True, "Generation complete"

    def download_video(self, destination_mp4_path: Path, timeout_sec: float = 300.0) -> Tuple[bool, str]:
        dest = Path(destination_mp4_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_exe = FFmpegExtractor.get_ffmpeg_executable()

        # Generate a genuine, 2-second valid MP4 test clip with scene color/counter
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "lavfi",
            "-i", "testsrc=size=640x360:rate=24",
            "-t", "2",
            "-pix_fmt", "yuv420p",
            str(dest)
        ]

        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            check=True
        )

        ok, msg = VideoValidator.wait_for_file_stability(dest, timeout_sec=10)
        if not ok:
            return False, f"Simulation file failed stability: {msg}"

        logger.info(f"[SIMULATION MODE] Video generated and saved to: {dest.name}")
        return True, "Downloaded successfully"

    def close(self):
        self.is_connected = False
        logger.info("[SIMULATION MODE] Closed.")
