"""Strict sequential execution engine with retry manager, pause/resume, and crash safety."""
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from core.config import DEFAULT_MAX_RETRIES, ENABLE_SOUNDS
from core.state_manager import ProjectState
from core.project_manager import ProjectManager
from core.ffmpeg_extractor import FFmpegExtractor
from core.video_validator import VideoValidator
from core.sound_player import SoundPlayer
from core.prompt_parser import ScenePrompt
from core.logger import logger
from connector.flow_base import BaseFlowConnector


class ExecutionEngine(QThread):
    # Signals emitted to UI
    sig_scene_started = Signal(int, int)          # current_scene_num, total_scenes
    sig_substep_changed = Signal(str, str)        # substep_name, status ("ACTIVE", "COMPLETE", "FAILED", "WAITING")
    sig_scene_completed = Signal(int)             # scene_number
    sig_batch_completed = Signal(int, int)        # completed_count, total_count
    sig_paused = Signal(str)                      # reason
    sig_resumed = Signal()
    sig_failed = Signal(int, str)                 # scene_number, error_message
    sig_stopped = Signal()

    def __init__(
        self,
        project_state: ProjectState,
        connector: BaseFlowConnector,
        scenes_to_run: List[ScenePrompt],
        max_retries: int = DEFAULT_MAX_RETRIES,
        parent=None
    ):
        super().__init__(parent)
        self.state = project_state
        self.connector = connector
        self.scenes_to_run = scenes_to_run
        self.max_retries = max_retries

        self._is_paused = False
        self._is_stopped = False
        self._pause_requested = False

    def request_pause(self):
        """Safely pause between steps or after current scene finishes."""
        self._pause_requested = True
        logger.info("Pause requested by user. Will pause at next safe state.")

    def resume_execution(self):
        """Resume paused engine."""
        self._is_paused = False
        self._pause_requested = False
        self.sig_resumed.emit()
        logger.info("Execution resumed.")

    def request_stop(self):
        """Stop engine and save project state."""
        self._is_stopped = True
        logger.info("Stop requested by user. Stopping execution...")

    def _check_pause_or_stop(self) -> bool:
        """Helper to sleep while paused and check if stopped."""
        if self._is_stopped:
            return True

        if self._pause_requested:
            self._is_paused = True
            self._pause_requested = False
            self.sig_paused.emit("User paused execution")
            logger.info("Execution safely paused.")

        while self._is_paused:
            if self._is_stopped:
                return True
            time.sleep(0.5)

        return self._is_stopped

    def run(self):
        """Strict sequential execution loop: ONE SCENE AT A TIME."""
        total_scenes = len(self.scenes_to_run)
        logger.info(f"Starting sequential batch execution: {total_scenes} scenes queued.")

        # Pre-execution: Verify and recover existing chain
        ok, msg = self.state.verify_and_recover_chain()
        if not ok:
            err = f"Chain integrity verification failed: {msg}"
            logger.error(err)
            self._handle_failure(0, err)
            return

        # Initialize connector if not already connected
        if not getattr(self.connector, "is_connected", False):
            self.sig_substep_changed.emit("Browser Session", "ACTIVE")
            ok, msg = self.connector.initialize()
            if not ok:
                self._handle_failure(0, f"Could not initialize browser connector: {msg}")
                return
            self.sig_substep_changed.emit("Browser Session", "COMPLETE")

        completed_in_this_run = 0

        for idx, scene in enumerate(self.scenes_to_run):
            if self._check_pause_or_stop():
                break

            s_num = scene.scene_number
            prompt_text = scene.prompt_text

            self.sig_scene_started.emit(s_num, total_scenes)
            logger.info(f"========== SCENE {s_num} STARTED ==========")

            # Check duplicate / already verified
            target_video = ProjectManager.get_scene_video_path(self.state.project_root, s_num)
            target_frame = ProjectManager.get_scene_last_frame_path(self.state.project_root, s_num)

            if target_video.is_file() and target_frame.is_file():
                v_ok, _ = VideoValidator.validate_video_integrity(target_video)
                f_ok, _ = FFmpegExtractor.verify_image(target_frame)
                if v_ok and f_ok:
                    logger.info(f"Scene {s_num} is already completed and verified on disk. Advancing chain...")
                    self.state.mark_scene_completed(s_num, self.state.current_chain_reference, target_video, target_frame)
                    self.sig_scene_completed.emit(s_num)
                    completed_in_this_run += 1
                    continue

            # Execute single scene with automatic retries
            success, err_msg = self._process_single_scene(s_num, prompt_text, target_video, target_frame)
            if not success:
                logger.error(f"Scene {s_num} failed permanently after {self.max_retries} attempts: {err_msg}")
                self._handle_failure(s_num, err_msg)
                return

            completed_in_this_run += 1
            self.sig_scene_completed.emit(s_num)
            logger.success(f"========== SCENE {s_num} 100% COMPLETE ==========")

        if not self._is_stopped:
            logger.success(f"Batch completed successfully! ({completed_in_this_run}/{total_scenes} scenes)")
            if ENABLE_SOUNDS:
                SoundPlayer.play_success()
            self.sig_batch_completed.emit(completed_in_this_run, total_scenes)
        else:
            self.sig_stopped.emit()

    def _process_single_scene(self, s_num: int, prompt_text: str, target_video: Path, target_frame: Path) -> tuple[bool, str]:
        """
        Executes the exact chain for ONE scene:
        REFERENCE -> PROMPT -> GENERATE -> WAIT -> DOWNLOAD -> VERIFY -> EXTRACT FRAME -> VERIFY FRAME -> SET NEXT REF
        """
        attempt = 0
        last_error = ""

        while attempt < self.max_retries:
            attempt += 1
            logger.info(f"Scene {s_num} (Attempt {attempt}/{self.max_retries})")
            self.state.update_scene_status(s_num, "PROCESSING", retry_count=attempt)

            # Determine reference image
            # Scene 1 uses Master Image. Scene > 1 uses previous last frame!
            current_ref = self.state.current_chain_reference
            logger.info(f"Chain reference for Scene {s_num}: {current_ref.name}")

            if not current_ref.is_file():
                return False, f"Reference image file is missing: {current_ref}"

            try:
                # 1. Upload reference image
                self.sig_substep_changed.emit("Reference Upload", "ACTIVE")
                ok, msg = self.connector.upload_reference(current_ref)
                if not ok:
                    raise RuntimeError(f"Reference upload failed: {msg}")
                self.sig_substep_changed.emit("Reference Upload", "COMPLETE")

                if self._check_pause_or_stop():
                    return False, "Execution stopped by user"

                # 2. Enter and verify prompt
                self.sig_substep_changed.emit("Prompt Submission", "ACTIVE")
                ok, msg = self.connector.submit_prompt(prompt_text)
                if not ok:
                    raise RuntimeError(f"Prompt submission failed: {msg}")
                self.sig_substep_changed.emit("Prompt Submission", "COMPLETE")

                if self._check_pause_or_stop():
                    return False, "Execution stopped by user"

                # 3. Trigger generation
                self.sig_substep_changed.emit("Video Generation", "ACTIVE")
                ok, msg = self.connector.trigger_generation()
                if not ok:
                    raise RuntimeError(f"Trigger generation failed: {msg}")

                # 4. Wait for generation completion (no fixed timer)
                ok, msg = self.connector.wait_for_completion()
                if not ok:
                    raise RuntimeError(f"Generation did not complete: {msg}")
                self.sig_substep_changed.emit("Video Generation", "COMPLETE")

                if self._check_pause_or_stop():
                    return False, "Execution stopped by user"

                # 5. Download video
                self.sig_substep_changed.emit("Video Download", "ACTIVE")
                ok, msg = self.connector.download_video(target_video)
                if not ok:
                    raise RuntimeError(f"Video download failed: {msg}")
                self.sig_substep_changed.emit("Video Download", "COMPLETE")

                # 6. Verify video integrity
                self.sig_substep_changed.emit("Video Verification", "ACTIVE")
                ok, msg = VideoValidator.validate_video_integrity(target_video)
                if not ok:
                    raise RuntimeError(f"Video validation failed: {msg}")
                self.sig_substep_changed.emit("Video Verification", "COMPLETE")

                # 7. Extract exact last frame
                self.sig_substep_changed.emit("Last Frame Extraction", "ACTIVE")
                ok, msg = FFmpegExtractor.extract_last_frame(target_video, target_frame)
                if not ok:
                    raise RuntimeError(f"Last frame extraction failed: {msg}")

                # 8. Verify extracted frame
                v_ok, v_msg = FFmpegExtractor.verify_image(target_frame)
                if not v_ok:
                    raise RuntimeError(f"Extracted last frame is invalid: {v_msg}")
                self.sig_substep_changed.emit("Last Frame Extraction", "COMPLETE")

                # 9. Mark completed and update chain reference to target_frame
                self.state.mark_scene_completed(s_num, current_ref, target_video, target_frame)
                return True, "Success"

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Scene {s_num} attempt {attempt} failed: {last_error}")
                if attempt < self.max_retries:
                    logger.info("Retrying recoverable operation in 3 seconds...")
                    time.sleep(3.0)

        return False, last_error

    def _handle_failure(self, scene_number: int, error_message: str):
        """Handle unrecoverable failure: play alert, pause chain, persist state."""
        self.state.update_scene_status(scene_number, "FAILED", error_message=error_message)
        if ENABLE_SOUNDS:
            SoundPlayer.play_failure()
        self.sig_failed.emit(scene_number, error_message)
