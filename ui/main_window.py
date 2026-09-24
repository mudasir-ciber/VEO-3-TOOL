"""Main application window for Chained Evolution Studio matching UX reference mockup."""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List

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
from core.chrome_profile_manager import ChromeProfile, ChromeProfileManager
from connector.flow_browser import PlaywrightFlowConnector
from connector.flow_mock import SimulatedFlowConnector

from ui.components.sidebar import SidebarWidget
from ui.components.project_cards import ProjectNameCard, MasterImageCard, ScenePromptsCard
from ui.components.chrome_account_widget import ChromeAccountWidget
from ui.components.scene_preview_card import ScenePreviewCard
from ui.components.log_viewer import LogViewerWidget
from ui.components.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1240, 840)
        self.setMinimumSize(1080, 720)

        self.project_state: Optional[ProjectState] = None
        self.engine: Optional[ExecutionEngine] = None
        self.active_connector = None
        self.current_chrome_profile: Optional[ChromeProfile] = None
        self.is_simulation_mode = False
        self.max_retries = 3
        self.auto_open_folder = True

        self._init_ui()
        self._load_styles()
        self._setup_logging()
        self._init_default_project()

    def _init_ui(self):
        # Root widget
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

        # 2. Main Content Dashboard (Scrollable)
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

        # Card 3: Master Image
        self.card_master_image = MasterImageCard(self)
        self.card_master_image.sig_master_image_selected.connect(self._on_master_image_set)
        self.card_master_image.sig_master_image_removed.connect(self._on_master_image_removed)
        v_left_col.addWidget(self.card_master_image)

        # Card 4: Scene Prompts
        self.card_prompts = ScenePromptsCard(self)
        self.card_prompts.sig_run_clicked.connect(self._start_execution)
        self.card_prompts.sig_pause_clicked.connect(self._pause_execution)
        self.card_prompts.sig_stop_clicked.connect(self._stop_execution)
        v_left_col.addWidget(self.card_prompts)

        content_layout.addLayout(v_left_col, stretch=5)

        # --- RIGHT COLUMN ---
        v_right_col = QVBoxLayout()
        v_right_col.setSpacing(14)

        # Card 2: Connect Chrome Account
        self.card_chrome_account = ChromeAccountWidget(self)
        self.card_chrome_account.sig_profile_changed.connect(self._on_chrome_profile_changed)
        v_right_col.addWidget(self.card_chrome_account)

        # Scene Preview & Vertical Stepper Card
        self.card_preview = ScenePreviewCard(self)
        v_right_col.addWidget(self.card_preview)

        # Activity Log Box
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
        logger.info(f"{APP_NAME} started. System diagnostics initialized.")

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

        # Update preview cards
        last_thumb = None
        if last_comp > 0:
            last_thumb = ProjectManager.get_scene_last_frame_path(self.project_state.project_root, last_comp)

        self.card_preview.update_bottom_cards(
            last_completed_scene=last_comp,
            last_completed_thumb=last_thumb,
            current_ref_name=ref_display,
            current_ref_thumb=curr_ref
        )

    def _on_chrome_profile_changed(self, profile: ChromeProfile):
        self.current_chrome_profile = profile
        logger.info(f"Active automation profile set to: {profile.display_name} ({profile.directory_name})")

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
            "<h3>Chained Evolution Studio Workflow</h3>"
            "<ol>"
            "<li><b>Select Chrome Profile:</b> Link your Google Chrome profile logged into Google Flow.</li>"
            "<li><b>Upload Master Image:</b> This image acts as the base reference for Scene 1.</li>"
            "<li><b>Enter Scene Prompts:</b> Paste your numbered batch of scene evolution prompts.</li>"
            "<li><b>Click Run:</b> The tool automatically generates each video scene sequentially, extracts the exact final decoded frame via FFmpeg, and hands it over as the reference for the next scene.</li>"
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

        # Verify reference for starting scene
        first_scene = parsed_scenes[0].scene_number
        current_ref = self.project_state.current_chain_reference

        if first_scene == 1 and (not current_ref or not current_ref.is_file()):
            QMessageBox.warning(
                self,
                "Master Image Required",
                "Scene 1 requires a valid Master Image. Please upload a Master Image."
            )
            return

        # Check Chrome Profile selected
        if not self.current_chrome_profile:
            saved = ChromeProfileManager.get_saved_profile()
            if saved:
                self.current_chrome_profile = saved
            else:
                QMessageBox.warning(
                    self,
                    "Chrome Account Required",
                    "Please link your Google Chrome profile in '2 Connect Chrome Account'."
                )
                return

        # Register prompts batch in project state
        self.project_state.register_scene_batch(
            [(s.scene_number, s.prompt_text) for s in parsed_scenes]
        )

        # Connector - Connect to existing open session, NEVER launch conflicting instance
        if self.is_simulation_mode:
            self.active_connector = SimulatedFlowConnector(step_delay_sec=1.0)
        else:
            chrome_conn = self.card_chrome.connector
            if chrome_conn.is_connected and chrome_conn.is_flow_tab_ready():
                self.active_connector = chrome_conn
            else:
                # Attempt to attach to existing open Chrome session
                ok, status, tabs = chrome_conn.connect_to_existing_chrome(port=9222)
                if ok and status == "CONNECTED_TO_FLOW":
                    self.active_connector = chrome_conn
                    self.card_chrome._update_system_status()
                elif status == "MULTIPLE_FLOW_TABS":
                    # Prompt user to select which Flow tab
                    self.card_chrome.connect_to_open_chrome()
                    return
                elif status == "FLOW_TAB_NOT_FOUND":
                    QMessageBox.warning(
                        self,
                        "Google Flow Tab Not Found",
                        "No Google Flow tab was detected in your open Chrome browser.<br><br>"
                        "Please open <b>https://flow.google.com/</b> in Chrome, then click 'Connect to Open Chrome' or RUN again."
                    )
                    return
                elif status == "CHROME_RUNNING_WITHOUT_CDP":
                    # Chrome is running without automation endpoint - show Mode B dialog
                    self.card_chrome.connect_to_open_chrome()
                    return
                else:
                    QMessageBox.warning(
                        self,
                        "Browser Connection Required",
                        "Please connect your Chrome browser to Google Flow by clicking 'Connect to Open Chrome' in Card 2 before starting automation."
                    )
                    return

        # Create ExecutionEngine worker
        self.engine = ExecutionEngine(
            project_state=self.project_state,
            connector=self.active_connector,
            scenes_to_run=parsed_scenes,
            max_retries=self.max_retries,
            chrome_profile=self.current_chrome_profile,
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
        if "Browser Connection Lost" in reason:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Browser Connection Lost")
            msg_box.setText("<b>The Google Flow browser connection was lost.</b>")
            msg_box.setInformativeText(
                "The current scene has been paused safely.<br><br>"
                "No new scene will start until the browser connection is restored.<br><br>"
                "Please ensure Chrome and your Google Flow tab are open, then click <b>'Reconnect'</b>."
            )
            btn_reconn = msg_box.addButton("Reconnect", QMessageBox.ActionRole)
            btn_stop = msg_box.addButton("Stop", QMessageBox.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_reconn:
                self.card_chrome.connect_to_open_chrome()
                if self.card_chrome.connector.is_connected and self.card_chrome.connector.is_flow_tab_ready():
                    self.engine.request_resume()
            else:
                self._stop_execution()


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
