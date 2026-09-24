"""
VEO 3 Chained Evolution Studio - Main Application Window
Full Native Messaging & Multi-Profile Architecture
"""
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QScrollArea, QDialog, QFrame, QSplitter
)
from PySide6.QtCore import Qt, Slot

from core.config import APP_NAME, APP_VERSION, DEFAULT_PROJECTS_DIR, BUNDLE_DIR
from core.state_manager import ProjectState
from core.project_manager import ProjectManager
from core.sound_player import SoundPlayer
from core.logger import logger, AppLogger
from core.execution_engine import ExecutionEngine
from core.extension_bridge import ExtensionBridgeServer, ExtensionProfile
from connector.flow_extension import ExtensionFlowConnector
from connector.flow_mock import SimulatedFlowConnector

from ui.components.sidebar import SidebarWidget
from ui.components.project_cards import ProjectNameCard, MasterImageCard, ScenePromptsCard
from ui.components.multi_profile_widget import MultiProfileWidget
from ui.components.scene_preview_card import ScenePreviewCard
from ui.components.log_viewer import LogViewerWidget
from ui.components.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — Multi-Profile Edition")
        self.resize(1260, 860)
        self.setMinimumSize(1080, 720)

        self.project_state: Optional[ProjectState] = None
        self.engine: Optional[ExecutionEngine] = None
        self.active_connector = None
        self.is_simulation_mode = False
        self.max_retries = 3
        self.auto_open_folder = True

        # 1. Start Multi-Profile Extension Bridge Server
        self.bridge = ExtensionBridgeServer.get_instance()
        self.bridge.start()
        self.bridge.add_event_listener(self._on_bridge_event)

        self._init_ui()
        self._load_styles()
        self._setup_logging()
        self._init_default_project()

    def _init_ui(self):
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root_layout = QHBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar = SidebarWidget(self)
        self.sidebar.sig_nav_settings.connect(self._open_settings)
        self.sidebar.sig_nav_my_projects.connect(self._open_projects_folder)
        self.sidebar.sig_nav_help.connect(self._show_help_dialog)
        root_layout.addWidget(self.sidebar)

        # 2. Main Dashboard (Scrollable)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #080b11; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #080b11;")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(16)

        # --- LEFT COLUMN ---
        v_left_col = QVBoxLayout()
        v_left_col.setSpacing(14)

        # Card 1: Project Name
        self.card_project_name = ProjectNameCard("Airplane Evolution", self)
        self.card_project_name.sig_name_changed.connect(self._on_project_name_changed)
        v_left_col.addWidget(self.card_project_name)

        # Card 2: Master Image
        self.card_master_image = MasterImageCard(self)
        self.card_master_image.sig_master_image_selected.connect(self._on_master_image_set)
        self.card_master_image.sig_master_image_removed.connect(self._on_master_image_removed)
        v_left_col.addWidget(self.card_master_image)

        # Card 3: Scene Prompts & Execution Controls
        self.card_prompts = ScenePromptsCard(self)
        self.card_prompts.sig_run_clicked.connect(self._start_execution)
        self.card_prompts.sig_pause_clicked.connect(self._pause_execution)
        self.card_prompts.sig_stop_clicked.connect(self._stop_execution)
        self.card_prompts.sig_retry_clicked.connect(self._retry_current_scene)
        self.card_prompts.sig_open_folder_clicked.connect(self._open_projects_folder)
        v_left_col.addWidget(self.card_prompts)

        content_layout.addLayout(v_left_col, stretch=5)

        # --- RIGHT COLUMN ---
        v_right_col = QVBoxLayout()
        v_right_col.setSpacing(14)

        # Card 4: Multi-Profile Discovery & Selection Widget
        self.card_multi_profile = MultiProfileWidget(self)
        v_right_col.addWidget(self.card_multi_profile)

        # Card 5: Scene Preview & Vertical Pipeline Card
        self.card_preview = ScenePreviewCard(self)
        v_right_col.addWidget(self.card_preview)

        # Card 6: Live Activity Log Box
        self.log_viewer = LogViewerWidget(self)
        self.log_viewer.setMaximumHeight(180)
        v_right_col.addWidget(self.log_viewer)

        content_layout.addLayout(v_right_col, stretch=6)

        scroll_area.setWidget(content_widget)
        root_layout.addWidget(scroll_area)

    def _load_styles(self):
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
        logger.info(f"{APP_NAME} started. Multi-Profile Native Bridge active.")

    def _on_bridge_event(self, ev: Dict[str, Any]):
        """Format and append live high-resolution timestamped events into the UI log."""
        ev_type = ev.get("type", "")
        p_name = ev.get("profileName", "Bridge")
        ts = ev.get("timestamp", "")
        if "T" in ts:
            ts = ts.split("T")[-1].replace("Z", "")[:12]
        else:
            ts = time.strftime("%H:%M:%S.000", time.localtime())

        msg = ev.get("message") or ev_type.replace("_", " ").title()
        sc = ev.get("scene")
        sc_str = f" [Scene {sc}]" if sc else ""

        level = "INFO"
        if "COMPLETE" in ev_type or "SUCCESS" in ev_type or "VERIFIED" in ev_type:
            level = "SUCCESS"
        elif "FAILED" in ev_type or "ERROR" in ev_type or "LOST" in ev_type:
            level = "ERROR"
        elif "STARTED" in ev_type or "UPLOADING" in ev_type or "PROGRESS" in ev_type:
            level = "INFO"

        self.log_viewer.append_log(ts, level, f"{p_name} → {msg}{sc_str}")

    def _init_default_project(self):
        name = self.card_project_name.get_name()
        proj_dir = DEFAULT_PROJECTS_DIR / name
        self._load_project(name, proj_dir)

    def _on_project_name_changed(self, new_name: str):
        proj_dir = DEFAULT_PROJECTS_DIR / new_name
        self._load_project(new_name, proj_dir)

    def _load_project(self, name: str, directory: Path):
        ProjectManager.setup_project_directories(directory)
        self.project_state = ProjectState(directory, name)

        # Hook project file logger
        log_file = directory / "Logs" / "activity.log"
        AppLogger.get_instance().set_project_log_file(log_file)

        # Check existing master image
        master_img = directory / "Master" / "Master Image.png"
        if master_img.is_file():
            self.card_master_image.set_image(str(master_img))
            self.card_preview.set_preview_image(master_img)

        # Sync continuity
        self._sync_continuity_ui()
        logger.info(f"Loaded project workspace: {name}")

    def _sync_continuity_ui(self):
        if not self.project_state:
            return

        last_comp = self.project_state.last_completed_scene
        curr_ref = self.project_state.current_chain_reference
        next_sc = self.project_state.next_scene

        ref_display = curr_ref.name if curr_ref and curr_ref.is_file() else "Master Image"
        self.card_prompts.set_next_scene_number(next_sc)

        last_thumb = None
        if last_comp > 0:
            last_thumb = ProjectManager.get_scene_last_frame_path(self.project_state.project_root, last_comp)

        self.card_preview.update_bottom_cards(
            last_completed_scene=last_comp,
            last_completed_thumb=last_thumb,
            current_ref_name=ref_display,
            current_ref_thumb=curr_ref
        )

    def _on_master_image_set(self, image_path: str):
        if not self.project_state:
            return

        ok, msg, dest = ProjectManager.set_master_image(self.project_state.project_root, image_path)
        if ok and dest:
            self.project_state.data["master_image_path"] = str(dest)
            if self.project_state.last_completed_scene == 0:
                self.project_state.data["current_chain_reference"] = str(dest)
            self.project_state.save()
            self.card_preview.set_preview_image(dest)
            self._sync_continuity_ui()
            logger.info("Master Image successfully saved into project workspace.")
        else:
            QMessageBox.warning(self, "Invalid Image", f"Could not set Master Image: {msg}")

    def _on_master_image_removed(self):
        if self.project_state:
            self.project_state.data["master_image_path"] = ""
            self.project_state.save()
            self._sync_continuity_ui()

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            settings = dlg.get_settings()
            self.max_retries = settings.get("max_retries", 3)
            self.auto_open_folder = settings.get("auto_open_folder", True)
            logger.info("Settings updated successfully.")

    def _open_projects_folder(self):
        if self.project_state and sys.platform == "win32":
            os.startfile(str(self.project_state.project_root))
        elif sys.platform == "win32":
            os.startfile(str(DEFAULT_PROJECTS_DIR))

    def _show_help_dialog(self):
        QMessageBox.information(
            self,
            "Chained Evolution Studio - Help",
            "<h3>VEO 3 Chained Evolution Studio</h3>"
            "<p><b>Multi-Profile Architecture:</b></p>"
            "<ol>"
            "<li>Open any of your existing Chrome profiles.</li>"
            "<li>Install the VEO 3 Bridge Chrome Extension.</li>"
            "<li>Keep Google Flow open to your project tab.</li>"
            "<li>The profile will immediately appear in <b>Connected Chrome Profiles</b>.</li>"
            "<li>Select your profile and click <b>Run</b>!</li>"
            "</ol>"
        )

    # ------------------ Execution Lifecycle ------------------

    def _start_execution(self):
        if not self.project_state:
            QMessageBox.critical(self, "Error", "Project state is not initialized.")
            return

        parsed_scenes = self.card_prompts.get_parsed_scenes()
        if not parsed_scenes:
            QMessageBox.warning(
                self,
                "No Prompts",
                "Please enter or load at least one scene prompt before running."
            )
            return

        first_scene = parsed_scenes[0].scene_number
        current_ref = self.project_state.current_chain_reference

        if first_scene == 1 and (not current_ref or not current_ref.is_file()):
            QMessageBox.warning(
                self,
                "Master Image Required",
                "Scene 1 requires a valid Master Image. Please upload a Master Image."
            )
            return

        # Select Connector based on Mode
        if self.is_simulation_mode:
            self.active_connector = SimulatedFlowConnector(step_delay_sec=1.0)
            logger.info("Running in SIMULATION MODE.")
        else:
            selected_prof = self.card_multi_profile.selected_profile_name
            if not selected_prof:
                QMessageBox.warning(
                    self,
                    "Profile Selection Required",
                    "Please select an active Chrome profile from 'Connected Chrome Profiles' above."
                )
                return

            if not self.bridge.is_profile_connected(selected_prof):
                QMessageBox.warning(
                    self,
                    "Profile Offline",
                    f"Selected profile '<b>{selected_prof}</b>' is offline.<br><br>"
                    "Please ensure Google Chrome is open with this profile and the VEO 3 Bridge extension is active."
                )
                return

            # Instantiate Extension connector bound strictly to the selected profile
            connector = ExtensionFlowConnector(target_profile_name=selected_prof)
            ok, msg = connector.initialize()
            if not ok:
                QMessageBox.warning(self, "Connection Error", msg)
                return
            self.active_connector = connector
            logger.info(f"Bound execution engine to target profile: '{selected_prof}'")

        # Register prompts batch in project state
        self.project_state.register_scene_batch(
            [(s.scene_number, s.prompt_text) for s in parsed_scenes]
        )

        # Create ExecutionEngine worker
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

        self.card_prompts.set_running_state(is_running=True, is_paused=False)
        self.engine.start()

    def _pause_execution(self):
        if self.engine and self.engine.isRunning():
            self.engine.request_pause()

    def _stop_execution(self):
        if self.engine and self.engine.isRunning():
            self.engine.request_stop()
            self.card_prompts.set_running_state(is_running=False)

    def _retry_current_scene(self):
        """Retry the currently active or failed scene."""
        if self.engine and self.engine.isRunning():
            QMessageBox.information(self, "Running", "A scene is currently running. Please Pause or Stop first.")
            return
        self._start_execution()

    # ------------------ Engine Signal Handlers ------------------

    @Slot(int, int)
    def _on_scene_started(self, scene_num: int, total: int):
        completed_so_far = self.project_state.last_completed_scene if self.project_state else 0
        self.card_preview.set_scene_status(scene_num, total, completed_so_far)

    @Slot(str, str)
    def _on_substep_changed(self, step_name: str, status: str):
        self.card_preview.update_step(step_name, status)

    @Slot(int)
    def _on_scene_completed(self, scene_num: int):
        self._sync_continuity_ui()
        if self.project_state:
            frame_path = ProjectManager.get_scene_last_frame_path(self.project_state.project_root, scene_num)
            if frame_path.is_file():
                self.card_preview.set_preview_image(frame_path)

    @Slot(int, int)
    def _on_batch_completed(self, completed: int, total: int):
        self.card_prompts.set_running_state(is_running=False)
        self._sync_continuity_ui()

        QMessageBox.information(
            self,
            "Batch Completed!",
            f"🎉 Success!\n\nAll {completed} / {total} scenes completed successfully!\n"
            f"The final frame is ready as the reference for your next batch."
        )

        if self.auto_open_folder and self.project_state:
            videos_dir = self.project_state.project_root / "Videos"
            if sys.platform == "win32":
                os.startfile(str(videos_dir))

    @Slot(str)
    def _on_engine_paused(self, reason: str):
        self.card_prompts.set_running_state(is_running=True, is_paused=True)
        QMessageBox.warning(
            self,
            "Execution Paused",
            f"<b>Automation has paused safely:</b><br><br>{reason}<br><br>"
            "Please check your Chrome tab and click <b>Resume</b> or <b>Run</b> when ready."
        )

    @Slot()
    def _on_engine_resumed(self):
        self.card_prompts.set_running_state(is_running=True, is_paused=False)

    @Slot(int, str)
    def _on_engine_failed(self, scene_number: int, error_message: str):
        self.card_prompts.set_running_state(is_running=False)
        self.card_preview.update_step("Execution", "FAILED")

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
        self.card_prompts.set_running_state(is_running=False)
        logger.info("Process stopped. State preserved on disk.")

    def closeEvent(self, event):
        try:
            self.bridge.stop()
        except Exception:
            pass
        super().closeEvent(event)
