"""Project workspace folder management and asset initialization."""
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from core.config import (
    DIR_MASTER, DIR_VIDEOS, DIR_LAST_FRAMES, DIR_PROMPTS,
    DIR_STATE, DIR_LOGS, MASTER_IMAGE_NAME
)
from core.logger import logger

class ProjectManager:
    @classmethod
    def setup_project_directories(cls, project_root: str | Path) -> dict[str, Path]:
        """Create standard folder layout inside the project directory."""
        root = Path(project_root).resolve()
        dirs = {
            "root": root,
            "master": root / DIR_MASTER,
            "videos": root / DIR_VIDEOS,
            "last_frames": root / DIR_LAST_FRAMES,
            "prompts": root / DIR_PROMPTS,
            "state": root / DIR_STATE,
            "logs": root / DIR_LOGS
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        return dirs

    @classmethod
    def set_master_image(cls, project_root: str | Path, source_image_path: str | Path) -> Tuple[bool, str, Optional[Path]]:
        """
        Copy, convert/verify, and save the project's Master Image in Master/Master Image.png.
        """
        src = Path(source_image_path).resolve()
        if not src.is_file():
            return False, f"Source image does not exist: {src}", None

        dirs = cls.setup_project_directories(project_root)
        dest = dirs["master"] / MASTER_IMAGE_NAME

        try:
            # Open with Pillow to verify and save as standard PNG
            with Image.open(src) as img:
                img.verify()
            with Image.open(src) as img:
                # Convert RGBA/RGB and save cleanly
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                img.save(dest, format="PNG")

            logger.info(f"Master Image saved successfully at: {dest}")
            return True, "Master Image verified and saved", dest
        except Exception as e:
            logger.error(f"Failed to copy/verify Master Image: {e}")
            return False, f"Invalid image file: {e}", None

    @classmethod
    def save_scene_prompt_file(cls, project_root: str | Path, scene_number: int, prompt_text: str) -> Path:
        """Save individual prompt text file into Prompts/Scene {x}.txt."""
        dirs = cls.setup_project_directories(project_root)
        prompt_file = dirs["prompts"] / f"Scene {scene_number}.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt_text.strip() + "\n")
        return prompt_file

    @classmethod
    def get_scene_video_path(cls, project_root: str | Path, scene_number: int) -> Path:
        dirs = cls.setup_project_directories(project_root)
        return dirs["videos"] / f"Scene {scene_number}.mp4"

    @classmethod
    def get_scene_last_frame_path(cls, project_root: str | Path, scene_number: int) -> Path:
        dirs = cls.setup_project_directories(project_root)
        return dirs["last_frames"] / f"Scene {scene_number}.png"
