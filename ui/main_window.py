"""Main application window for Chained Evolution Studio."""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QScrollArea, QDialog
)
from PySide6.QtCore import Qt, Slot

from core.config import APP_NAME, APP_VERSION, DEFAULT_PROJECTS_DIR
from core.state_manager import ProjectState
from core.project_manager import ProjectManager
from core.sound_player import SoundPlayer
from core.logger import logger, AppLogger
from core.execution_engine import ExecutionEngine
from connector.flow_browser import PlaywrightFlowConnector
from connector.flow_mock import SimulatedFlowConnector

from ui.components.project_header import ProjectHeaderWidget
from ui.components.prompt_editor import PromptEditorWidget
from ui.components.progress_card import ProgressCardWidget
from ui.components.control_bar import ControlBarWidget
from ui.components.log_viewer import LogViewerWidget
from ui.components.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1120, 880)
        self.setMinimumSize(960, 720)

        self.project_state: Optional[ProjectState] = None
        self.engine: Optional[ExecutionEngine] = None
        self.active_connector = None
        self.is_simulation_mode = False
        self.max_retries = 3
        self.auto_open_folder = True

        self._init_ui()
        self._load_styles()
        self._setup_logging()
        self._init_default_project()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Project & Master Image Header
        self.header_widget = ProjectHeaderWidget(self)
        self.header_widget.sig_project_changed.connect(self._on_project_changed)
        self.header_widget.sig_master_image_set.connect(self._on_master_image_set)
        main_layout.addWidget(self.header_widget)

        # 2. Batch Scene Prompts & Continuity Editor
        self.prompt_editor = PromptEditorWidget(self)
        main_layout.addWidget(self.prompt_editor)

        # 3. Step Progression Card
        self.progress_card = ProgressCardWidget(self)
        main_layout.addWidget(self.progress_card)

        # 4. Action Control Bar
        self.control_bar = ControlBarWidget(self)
        self.control_bar.sig_run_clicked.connect(self._start_execution)
        self.control_bar.sig_pause_clicked.connect(self._pause_execution)
        self.control_bar.sig_resume_clicked.connect(self._resume_execution)
        self.control_bar.sig_stop_clicked.connect(self._stop_execution)
        self.control_bar.sig_settings_clicked.connect(self._open_settings)
        self.control_bar.sig_sim_mode_toggled.connect(self._on_simulation_toggled)
        main_layout.addWidget(self.control_bar)

        # 5. Real-Time Activity Log Viewer
        self.log_viewer = LogViewerWidget(self)
        main_layout.addWidget(self.log_viewer)

    def _load_styles(self):
        from core.config import BUNDLE_DIR
        candidates = [
            BUNDLE_DIR / "ui" / "styles" / "dark_theme.qss",
            Path(__file__).resolve().parent / "styles" / "dark_theme.qss"
        ]
        for qss_path in candidates:
            if qss_path.is_file():
                try:
                    with open(qss_path, "r", encoding="utf-8") as f:
                        self.setStyleSheet(f.read())
                    break
                except Exception:
                    pass

    def _setup_logging(self):
        AppLogger.get_instance().register_callback(self.log_viewer.append_log)
        logger.info(f"{APP_NAME} started. System diagnostics initialized.")

    def _init_default_project(self):
        proj_name = self.header_widget.get_project_name()
        proj_dir = self.header_widget.get_project_path()
        self._load_project(proj_name, proj_dir)

    def _on_project_changed(self, name: str, dir_str: str):
        self._load_project(name, Path(dir_str))

    def _load_project(self, name: str, directory: Path):
        ProjectManager.setup_project_directories(directory)
        self.project_state = ProjectState(directory, name)

        # Hook project file logger
        log_file = directory / "Logs" / "activity.log"
        AppLogger.get_instance().set_project_log_file(log_file)

        # Check existing master image
        master_img = directory / "Master" / "Master Image.png"
        if master_img.is_file():
            self.header_widget.set_master_image(str(master_img))

        # Check continuity
        self._sync_continuity_ui()
        logger.info(f"Loaded project: {name} (Workspace: {directory})")

    def _sync_continuity_ui(self):
        if not self.project_state:
            return

        last_comp = self.project_state.last_completed_scene
        curr_ref = self.project_state.current_chain_reference
        next_sc = self.project_state.next_scene

        ref_display = curr_ref.name if curr_ref and curr_ref.is_file() else "Master Image.png"
        self.prompt_editor.set_continuity_info(last_comp, ref_display, next_sc)

    def _on_master_image_set(self, image_path: str):
        if not self.project_state:
            return

        ok, msg, dest = ProjectManager.set_master_image(self.project_state.project_root, image_path)
        if ok and dest:
            self.project_state.data["master_image_path"] = str(dest)
            if self.project_state.last_completed_scene == 0:
                self.project_state.data["current_chain_reference"] = str(dest)
            self.project_state.save()
            self._sync_continuity_ui()
            logger.info("Master Image successfully saved into project workspace.")
        else:
            QMessageBox.warning(self, "Invalid Image", f"Could not set Master Image: {msg}")

    def _on_simulation_toggled(self, is_sim: bool):
        self.is_simulation_mode = is_sim
        if is_sim:
            logger.info("[MODE SWITCH] Simulation / Dry-Run mode enabled. Generations will be local.")
        else:
            logger.info("[MODE SWITCH] Live Google Flow mode enabled.")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            settings = dlg.get_settings()
            self.max_retries = settings.get("max_retries", 3)
            self.auto_open_folder = settings.get("auto_open_folder", True)
            logger.info("Settings updated successfully.")

    # ------------------ Execution Lifecycle ------------------

    def _start_execution(self):
        # 1. Pre-flight verifications
        if not self.project_state:
            QMessageBox.critical(self, "Error", "Project state is not initialized.")
            return

        parsed_scenes = self.prompt_editor.get_parsed_scenes()
        if not parsed_scenes:
            QMessageBox.warning(
                self,
                "No Prompts",
                "Please enter or import at least one scene prompt before running."
            )
            return

        # Verify reference for first scene to run
        first_scene = parsed_scenes[0].scene_number
        current_ref = self.project_state.current_chain_reference

        if first_scene == 1 and (not current_ref or not current_ref.is_file()):
            QMessageBox.warning(
                self,
                "Master Image Required",
                "Scene 1 requires a valid Master Image. Please upload a Master Image."
            )
            return

        # Register prompts batch in project state
        self.project_state.register_scene_batch(
            [(s.scene_number, s.prompt_text) for s in parsed_scenes]
        )

        # 2. Select Connector
        if self.is_simulation_mode:
            self.active_connector = SimulatedFlowConnector(step_delay_sec=1.0)
        else:
            self.active_connector = PlaywrightFlowConnector()

        # 3. Create and launch ExecutionEngine QThread
        self.engine = ExecutionEngine(
            project_state=self.project_state,
            connector=self.active_connector,
            scenes_to_run=parsed_scenes,
            max_retries=self.max_retries,
            parent=self
        )

        self.engine.sig_scene_started.connect(self._on_scene_started)
        self.engine.sig_substep_changed.connect(self._on_substep_changed)
        self.engine.sig_scene_completed.connect(self._on_scene_completed)
        self.engine.sig_batch_completed.connect(self._on_batch_completed)
        self.engine.sig_paused.connect(self._on_engine_paused)
        self.engine.sig_resumed.connect(self._on_engine_resumed)
        self.engine.sig_failed.connect(self._on_engine_failed)
        self.engine.sig_stopped.connect(self._on_engine_stopped)

        self.control_bar.set_running_state(is_running=True, is_paused=False)
        self.engine.start()

    def _pause_execution(self):
        if self.engine and self.engine.isRunning():
            self.engine.request_pause()

    def _resume_execution(self):
        if self.engine and self.engine.isRunning():
            self.engine.resume_execution()
            self.control_bar.set_running_state(is_running=True, is_paused=False)

    def _stop_execution(self):
        if self.engine and self.engine.isRunning():
            self.engine.request_stop()
            self.control_bar.set_running_state(is_running=False)

    # ------------------ Engine Signal Handlers ------------------

    @Slot(int, int)
    def _on_scene_started(self, scene_num: int, total: int):
        completed_so_far = self.project_state.last_completed_scene if self.project_state else 0
        self.progress_card.set_current_scene(scene_num, total, completed_so_far)

    @Slot(str, str)
    def _on_substep_changed(self, step_name: str, status: str):
        self.progress_card.update_substep(step_name, status)

    @Slot(int)
    def _on_scene_completed(self, scene_num: int):
        self._sync_continuity_ui()

    @Slot(int, int)
    def _on_batch_completed(self, completed: int, total: int):
        self.control_bar.set_running_state(is_running=False)
        self.progress_card.mark_completed_all(total)
        self._sync_continuity_ui()

        QMessageBox.information(
            self,
            "Batch Completed!",
            f"🎉 Success!\n\nAll {completed} / {total} scenes completed successfully!\n"
            f"Next Chain Reference is ready for your next batch."
        )

        if self.auto_open_folder and self.project_state:
            videos_dir = self.project_state.project_root / "Videos"
            if sys.platform == "win32":
                os.startfile(str(videos_dir))

    @Slot(str)
    def _on_engine_paused(self, reason: str):
        self.control_bar.set_running_state(is_running=True, is_paused=True)

    @Slot()
    def _on_engine_resumed(self):
        self.control_bar.set_running_state(is_running=True, is_paused=False)

    @Slot(int, str)
    def _on_engine_failed(self, scene_number: int, error_message: str):
        self.control_bar.set_running_state(is_running=False)
        self.progress_card.update_substep("Execution", "FAILED")

        # Failure Dialog with [ Retry Scene ] [ Resume ] [ Open Project Folder ]
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Scene Processing Halted")
        msg_box.setText(f"<b>SCENE {scene_number} FAILED</b>\nPROCESS PAUSED")
        msg_box.setInformativeText(f"<b>Reason:</b> {error_message}")

        btn_retry = msg_box.addButton("Retry Scene", QMessageBox.ActionRole)
        btn_open = msg_box.addButton("Open Project Folder", QMessageBox.ActionRole)
        btn_close = msg_box.addButton("Close", QMessageBox.RejectRole)

        msg_box.exec()

        if msg_box.clickedButton() == btn_retry:
            self._start_execution()
        elif msg_box.clickedButton() == btn_open:
            if self.project_state and sys.platform == "win32":
                os.startfile(str(self.project_state.project_root))

    @Slot()
    def _on_engine_stopped(self):
        self.control_bar.set_running_state(is_running=False)
        logger.info("Process stopped. State preserved on disk.")
