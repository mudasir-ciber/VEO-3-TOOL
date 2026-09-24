"""Persistent state manager with atomic disk writes, batch continuity, and chain recovery."""
import os
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from core.config import DIR_STATE, STATE_FILE_NAME, MASTER_IMAGE_NAME
from core.project_manager import ProjectManager
from core.ffmpeg_extractor import FFmpegExtractor
from core.logger import logger

class ProjectState:
    def __init__(self, project_root: str | Path, project_name: str = "Default Project"):
        self.project_root = Path(project_root).resolve()
        self.project_name = project_name
        self.state_dir = self.project_root / DIR_STATE
        self.state_file = self.state_dir / STATE_FILE_NAME
        self._lock = threading.Lock()

        self.data: Dict[str, Any] = {
            "project_name": self.project_name,
            "project_root": str(self.project_root),
            "master_image_path": str(self.project_root / "Master" / MASTER_IMAGE_NAME),
            "last_completed_scene": 0,
            "current_chain_reference": str(self.project_root / "Master" / MASTER_IMAGE_NAME),
            "next_scene": 1,
            "project_status": "READY",  # READY, RUNNING, PAUSED, COMPLETED, FAILED
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "scenes": {}  # keyed by string scene number e.g. "1": {...}
        }

        self.load()

    def load(self):
        """Load state from disk or initialize fresh if file does not exist."""
        with self._lock:
            if self.state_file.is_file():
                try:
                    with open(self.state_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        self.data.update(loaded)
                    logger.info(f"Loaded existing project state from {self.state_file} (Last Completed: {self.data.get('last_completed_scene', 0)})")
                except Exception as e:
                    logger.error(f"Error loading state file: {e}. Keeping current memory state.")
            else:
                self.save_locked()

    def save(self):
        """Thread-safe public save method."""
        with self._lock:
            self.save_locked()

    def save_locked(self):
        """Atomic write to prevent corruption during unexpected shutdowns."""
        self.data["updated_at"] = datetime.now().isoformat()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = self.state_dir / f"{STATE_FILE_NAME}.tmp"

        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, self.state_file)
        except Exception as e:
            logger.error(f"Critical error saving state atomically: {e}")

    @property
    def last_completed_scene(self) -> int:
        with self._lock:
            return int(self.data.get("last_completed_scene", 0))

    @property
    def next_scene(self) -> int:
        with self._lock:
            return int(self.data.get("next_scene", 1))

    @property
    def current_chain_reference(self) -> Path:
        with self._lock:
            ref = self.data.get("current_chain_reference")
            if ref and Path(ref).is_file():
                return Path(ref)
            # Default fallback to master image if scene is 1
            master = self.project_root / "Master" / MASTER_IMAGE_NAME
            return master

    def register_scene_batch(self, scene_prompts: list[tuple[int, str]]):
        """
        Register a batch of scenes into project state while strictly preserving continuity.
        scene_prompts: list of (scene_number, prompt_text)
        """
        with self._lock:
            for s_num, prompt_text in scene_prompts:
                s_key = str(s_num)
                # Save prompt text file
                prompt_file = ProjectManager.save_scene_prompt_file(self.project_root, s_num, prompt_text)
                video_file = ProjectManager.get_scene_video_path(self.project_root, s_num)
                frame_file = ProjectManager.get_scene_last_frame_path(self.project_root, s_num)

                if s_key not in self.data["scenes"]:
                    self.data["scenes"][s_key] = {
                        "scene_number": s_num,
                        "prompt_text": prompt_text,
                        "prompt_path": str(prompt_file),
                        "video_path": str(video_file),
                        "last_frame_path": str(frame_file),
                        "status": "PENDING",  # PENDING, GENERATING, DOWNLOADING, VERIFYING, EXTRACTING, COMPLETED, FAILED
                        "reference_used": None,
                        "retry_count": 0,
                        "error_message": None,
                        "completed_at": None
                    }
                else:
                    # Update prompt text if existing
                    self.data["scenes"][s_key]["prompt_text"] = prompt_text
                    self.data["scenes"][s_key]["prompt_path"] = str(prompt_file)

            self.save_locked()

    def update_scene_status(self, scene_number: int, status: str, error_message: str | None = None, retry_count: int | None = None):
        """Update scene status in memory and persist atomically."""
        with self._lock:
            s_key = str(scene_number)
            if s_key in self.data["scenes"]:
                self.data["scenes"][s_key]["status"] = status
                if error_message is not None:
                    self.data["scenes"][s_key]["error_message"] = error_message
                if retry_count is not None:
                    self.data["scenes"][s_key]["retry_count"] = retry_count
            self.save_locked()

    def mark_scene_completed(self, scene_number: int, reference_used: Path, video_path: Path, last_frame_path: Path):
        """
        Mark a scene 100% completed and advance project chain pointer.
        Strictly sets current_chain_reference to this scene's last frame!
        """
        with self._lock:
            s_key = str(scene_number)
            if s_key in self.data["scenes"]:
                self.data["scenes"][s_key].update({
                    "status": "COMPLETED",
                    "reference_used": str(reference_used),
                    "video_path": str(video_path),
                    "last_frame_path": str(last_frame_path),
                    "error_message": None,
                    "completed_at": datetime.now().isoformat()
                })

            self.data["last_completed_scene"] = scene_number
            self.data["current_chain_reference"] = str(last_frame_path)
            self.data["next_scene"] = scene_number + 1
            self.save_locked()

        logger.success(f"Scene {scene_number} marked COMPLETED. Next chain reference set to: {last_frame_path.name}")

    def verify_and_recover_chain(self) -> Tuple[bool, str]:
        """
        Audit project files on disk and automatically recover missing assets.
        Example: Scene 10.mp4 exists, but Scene 10.png is missing:
        Re-extracts the frame from Scene 10.mp4 without re-generating!
        """
        with self._lock:
            last_completed = int(self.data.get("last_completed_scene", 0))
            if last_completed == 0:
                master = Path(self.data.get("master_image_path", ""))
                if not master.is_file():
                    return False, f"Master image not found at {master}"
                return True, "Chain healthy (at Master Image)"

            # Check all scenes up to last_completed
            for s_num in range(1, last_completed + 1):
                video_file = ProjectManager.get_scene_video_path(self.project_root, s_num)
                frame_file = ProjectManager.get_scene_last_frame_path(self.project_root, s_num)

                if not video_file.is_file():
                    return False, f"Missing video file for Scene {s_num}: {video_file}"

                if not frame_file.is_file() or frame_file.stat().st_size == 0:
                    logger.warning(f"Scene {s_num} frame missing or 0 bytes. Re-extracting from video: {video_file.name}")
                    ok, msg = FFmpegExtractor.extract_last_frame(video_file, frame_file)
                    if not ok:
                        return False, f"Failed to auto-recover frame for Scene {s_num}: {msg}"
                    logger.info(f"Auto-recovered frame for Scene {s_num}")

            # Ensure current_chain_reference points to the last completed frame
            last_frame = ProjectManager.get_scene_last_frame_path(self.project_root, last_completed)
            self.data["current_chain_reference"] = str(last_frame)
            self.data["next_scene"] = last_completed + 1
            self.save_locked()

            return True, f"Chain verified and intact up to Scene {last_completed}"
