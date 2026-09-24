"""Settings dialog for configuring retries, browser profiles, sounds, and paths."""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QSpinBox, QCheckBox, QLineEdit, QPushButton, QFileDialog,
    QComboBox, QGroupBox, QDialogButtonBox
)
from PySide6.QtCore import Qt

from core.config import (
    DEFAULT_MAX_RETRIES, DEFAULT_BROWSER_PROFILE_DIR, DEFAULT_PROJECTS_DIR,
    ENABLE_SOUNDS, DEFAULT_GENERATION_TIMEOUT_SEC, get_flow_project_url, set_flow_project_url
)
from core.system_checker import SystemChecker


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chained Evolution Studio - Settings")
        self.setMinimumWidth(520)
        self.resize(540, 480)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Execution & Retries
        grp_exec = QGroupBox("Execution & Failure Settings")
        grid_exec = QGridLayout(grp_exec)

        grid_exec.addWidget(QLabel("Max Retries Per Operation:"), 0, 0)
        self.spn_retries = QSpinBox()
        self.spn_retries.setRange(1, 10)
        self.spn_retries.setValue(DEFAULT_MAX_RETRIES)
        grid_exec.addWidget(self.spn_retries, 0, 1)

        grid_exec.addWidget(QLabel("Generation Timeout (sec):"), 1, 0)
        self.spn_timeout = QSpinBox()
        self.spn_timeout.setRange(60, 3600)
        self.spn_timeout.setValue(DEFAULT_GENERATION_TIMEOUT_SEC)
        grid_exec.addWidget(self.spn_timeout, 1, 1)

        layout.addWidget(grp_exec)

        # 2. Browser & Profile Settings
        grp_browser = QGroupBox("Google Flow Browser Settings")
        grid_browser = QGridLayout(grp_browser)

        grid_browser.addWidget(QLabel("Browser Channel:"), 0, 0)
        self.cmb_browser = QComboBox()
        self.cmb_browser.addItems(["Google Chrome (Installed)", "Microsoft Edge", "Chromium"])
        grid_browser.addWidget(self.cmb_browser, 0, 1, 1, 2)

        grid_browser.addWidget(QLabel("Persistent Profile Directory:"), 1, 0)
        self.txt_profile = QLineEdit(str(DEFAULT_BROWSER_PROFILE_DIR))
        btn_profile = QPushButton("Browse...")
        btn_profile.clicked.connect(self._browse_profile)
        grid_browser.addWidget(self.txt_profile, 1, 1)
        grid_browser.addWidget(btn_profile, 1, 2)

        grid_browser.addWidget(QLabel("Google Flow Project URL:"), 2, 0)
        self.txt_flow_url = QLineEdit(get_flow_project_url())
        self.txt_flow_url.setPlaceholderText("https://flow.google.com/project/...")
        grid_browser.addWidget(self.txt_flow_url, 2, 1, 1, 2)

        layout.addWidget(grp_browser)

        # 3. Audio & Notifications
        grp_audio = QGroupBox("Audio & Automation Notifications")
        v_audio = QVBoxLayout(grp_audio)

        self.chk_sound_success = QCheckBox("Play Success Chime on Batch Completion")
        self.chk_sound_success.setChecked(ENABLE_SOUNDS)

        self.chk_sound_fail = QCheckBox("Play Failure Alert Tone on Unrecoverable Failure")
        self.chk_sound_fail.setChecked(ENABLE_SOUNDS)

        self.chk_auto_open = QCheckBox("Automatically Open Output Folder when Batch Completes")
        self.chk_auto_open.setChecked(True)

        v_audio.addWidget(self.chk_sound_success)
        v_audio.addWidget(self.chk_sound_fail)
        v_audio.addWidget(self.chk_auto_open)

        layout.addWidget(grp_audio)

        # 4. Diagnostics & Paths
        grp_diag = QGroupBox("Detected Dependency Paths")
        v_diag = QVBoxLayout(grp_diag)

        sys_info = SystemChecker.get_system_info()
        ffmpeg_str = sys_info.get("ffmpeg_path") or "Not found"
        chrome_str = sys_info.get("chrome_path") or "Not found"

        lbl_f = QLabel(f"<b>FFmpeg:</b> <span style='color:#a5b4fc;'>{ffmpeg_str}</span>")
        lbl_f.setWordWrap(True)
        lbl_c = QLabel(f"<b>Chrome:</b> <span style='color:#a5b4fc;'>{chrome_str}</span>")
        lbl_c.setWordWrap(True)

        v_diag.addWidget(lbl_f)
        v_diag.addWidget(lbl_c)
        layout.addWidget(grp_diag)

        # Dialog Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse_profile(self):
        dir_selected = QFileDialog.getExistingDirectory(self, "Select Browser Profile Folder", self.txt_profile.text())
        if dir_selected:
            self.txt_profile.setText(dir_selected)

    def get_settings(self) -> dict:
        flow_url = self.txt_flow_url.text().strip()
        if flow_url:
            set_flow_project_url(flow_url)
        return {
            "max_retries": self.spn_retries.value(),
            "generation_timeout": self.spn_timeout.value(),
            "browser_profile": self.txt_profile.text(),
            "flow_project_url": flow_url,
            "play_success_sound": self.chk_sound_success.isChecked(),
            "play_failure_sound": self.chk_sound_fail.isChecked(),
            "auto_open_folder": self.chk_auto_open.isChecked()
        }
