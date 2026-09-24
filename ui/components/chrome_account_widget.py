"""Chrome Account connector widget and Profile Selector modal matching UX reference."""
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QLineEdit, QScrollArea, QFrame, QMessageBox,
    QRadioButton, QButtonGroup, QProgressBar, QApplication
)
from PySide6.QtGui import QPixmap, QIcon, QColor, QFont
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from core.config import get_flow_project_url, set_flow_project_url, DEFAULT_FLOW_PROJECT_URL, BASE_DIR
from core.chrome_profile_manager import ChromeProfileManager, ChromeProfile
from core.extension_bridge import ExtensionBridgeServer
from connector.flow_browser import PlaywrightFlowConnector
from core.logger import logger


class ProfileRowWidget(QFrame):
    sig_clicked = Signal(object)  # emits ChromeProfile

    def __init__(self, profile: ChromeProfile, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("profileRow")
        self.setStyleSheet(
            "#profileRow { background-color: #141824; border: 1px solid #232a3d; border-radius: 8px; padding: 6px; }"
            "#profileRow:hover { background-color: #1e2436; border-color: #3b82f6; }"
        )
        if self.is_selected:
            self.setStyleSheet(
                "#profileRow { background-color: #172554; border: 1.5px solid #3b82f6; border-radius: 8px; padding: 6px; }"
            )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # Avatar
        lbl_avatar = QLabel()
        lbl_avatar.setFixedSize(36, 36)
        pix = self.profile.get_avatar_pixmap(size=36)
        lbl_avatar.setPixmap(pix)
        layout.addWidget(lbl_avatar)

        # Details
        v_details = QVBoxLayout()
        v_details.setSpacing(2)

        lbl_name = QLabel(self.profile.display_name)
        lbl_name.setStyleSheet("font-size: 13px; font-weight: 600; color: #f1f5f9;")

        email_str = self.profile.email or self.profile.directory_name
        lbl_email = QLabel(email_str)
        lbl_email.setStyleSheet("font-size: 11px; color: #94a3b8;")

        v_details.addWidget(lbl_name)
        v_details.addWidget(lbl_email)
        layout.addLayout(v_details)
        layout.addStretch()

        if self.is_selected:
            lbl_check = QLabel("● Active")
            lbl_check.setStyleSheet("color: #10b981; font-weight: 600; font-size: 11px;")
            layout.addWidget(lbl_check)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_clicked.emit(self.profile)
        super().mousePressEvent(event)


class ChromeProfileSelectorDialog(QDialog):
    sig_profile_chosen = Signal(object)

    def __init__(self, current_profile: Optional[ChromeProfile] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Link Chrome Account")
        self.resize(460, 560)
        self.current_profile = current_profile
        self.all_profiles: List[ChromeProfile] = []
        self.filtered_profiles: List[ChromeProfile] = []
        self._init_ui()
        self.refresh_profiles()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #0d111a; color: #f1f5f9; }
            QLineEdit { background-color: #161c2a; border: 1px solid #2b354d; border-radius: 8px; color: #ffffff; padding: 8px 12px; font-size: 13px; }
            QLineEdit:focus { border: 1px solid #3b82f6; }
            QPushButton { background-color: #1e2638; border: 1px solid #334155; border-radius: 6px; color: #f8fafc; padding: 7px 14px; font-weight: 600; }
            QPushButton:hover { background-color: #2b354d; }
            QScrollArea { border: none; background: transparent; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header
        lbl_title = QLabel("Link Chrome Account")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        layout.addWidget(lbl_title)

        # Search Bar
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍  Search profiles...")
        self.txt_search.textChanged.connect(self._filter_profiles)
        layout.addWidget(self.txt_search)

        # Subtitle / Count
        self.lbl_count = QLabel("Your Chrome Profiles")
        self.lbl_count.setStyleSheet("font-size: 12px; font-weight: 600; color: #94a3b8;")
        layout.addWidget(self.lbl_count)

        # Scroll Area for Profiles
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(8)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        # Bottom Actions
        h_bottom = QHBoxLayout()
        btn_refresh = QPushButton("🔄  Refresh Profiles")
        btn_refresh.clicked.connect(self.refresh_profiles)

        btn_add = QPushButton("+ Add Another Profile")
        btn_add.setToolTip("Open Google Chrome to create a new profile")
        btn_add.clicked.connect(self._open_chrome_add_profile)

        h_bottom.addWidget(btn_refresh)
        h_bottom.addStretch()
        h_bottom.addWidget(btn_add)
        layout.addLayout(h_bottom)

    def refresh_profiles(self):
        self.all_profiles = ChromeProfileManager.detect_all_profiles()
        self._filter_profiles(self.txt_search.text())

    def _filter_profiles(self, query: str):
        q = query.strip().lower()
        if not q:
            self.filtered_profiles = list(self.all_profiles)
        else:
            self.filtered_profiles = [
                p for p in self.all_profiles
                if q in p.display_name.lower() or q in p.email.lower() or q in p.directory_name.lower()
            ]

        self.lbl_count.setText(f"Your Chrome Profiles ({len(self.filtered_profiles)} available)")

        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.filtered_profiles:
            lbl_empty = QLabel("No Chrome profiles match your search.")
            lbl_empty.setStyleSheet("color: #64748b; padding: 20px; font-size: 13px;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(lbl_empty)
            return

        for prof in self.filtered_profiles:
            is_curr = False
            if self.current_profile and self.current_profile.directory_name == prof.directory_name:
                is_curr = True
            row = ProfileRowWidget(prof, is_selected=is_curr)
            row.sig_clicked.connect(self._on_profile_selected)
            self.scroll_layout.addWidget(row)

        self.scroll_layout.addStretch()

    def _on_profile_selected(self, profile: ChromeProfile):
        self.sig_profile_chosen.emit(profile)
        self.accept()

    def _open_chrome_add_profile(self):
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.isfile(chrome_exe):
            subprocess.Popen([chrome_exe, "--profile-directory=Default"])
        self.refresh_profiles()


class ModeBAutomationDialog(QDialog):
    """Dialog shown when Chrome is already running without an automation debugging port."""
    sig_launch_requested = Signal()

    def __init__(self, profile: ChromeProfile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.setWindowTitle("Chrome Profile Needs Automation Connection")
        self.resize(520, 360)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #0b0f19; color: #f1f5f9; }
            QLabel { color: #cbd5e1; font-size: 13px; line-height: 1.5; }
            QPushButton#btnLaunch { background-color: #2563eb; color: #ffffff; font-weight: 700; padding: 9px 18px; border-radius: 6px; border: none; font-size: 13px; }
            QPushButton#btnLaunch:hover { background-color: #1d4ed8; }
            QPushButton#btnCancel { background-color: #1e293b; color: #94a3b8; font-weight: 600; padding: 9px 16px; border-radius: 6px; border: 1px solid #334155; }
            QPushButton#btnCancel:hover { background-color: #334155; color: #f8fafc; }
            QPushButton#btnCloseChrome { background-color: #7f1d1d; color: #fca5a5; font-weight: 600; padding: 7px 14px; border-radius: 6px; border: 1px solid #991b1b; }
            QPushButton#btnCloseChrome:hover { background-color: #991b1b; color: #ffffff; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        # Header Title
        lbl_title = QLabel("Chrome Profile Needs Automation Connection")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc;")
        layout.addWidget(lbl_title)

        # Body Message matching requirement
        lbl_body = QLabel(
            f"The selected Chrome profile (<b>{self.profile.display_name}</b>) is already open in Chrome, "
            "but this session was started without an automation endpoint.<br><br>"
            "<b>To safely connect this profile:</b><br>"
            "1. Save any important work in your open Chrome tabs.<br>"
            "2. Close your open Chrome windows.<br>"
            "3. Click <b>'Launch Connected Chrome'</b> below.<br><br>"
            "The application will reopen the <i>SAME</i> selected Chrome profile with the required automation connection."
        )
        lbl_body.setWordWrap(True)
        layout.addWidget(lbl_body)

        layout.addStretch()

        # Action Buttons
        h_btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(self.reject)

        btn_launch = QPushButton("Launch Connected Chrome")
        btn_launch.setObjectName("btnLaunch")
        btn_launch.clicked.connect(self._on_launch_clicked)

        h_btns.addWidget(btn_cancel)
        h_btns.addStretch()
        h_btns.addWidget(btn_launch)
        layout.addLayout(h_btns)

    def _on_launch_clicked(self):
        # Verify if Chrome is still running
        if ChromeProfileManager.is_chrome_running():
            ret = QMessageBox.question(
                self,
                "Close Chrome First",
                "Chrome is still open on your computer.<br><br>"
                "Would you like Chained Evolution Studio to gently close Chrome so it can reopen with automation enabled?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret == QMessageBox.Yes:
                try:
                    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
                    time.sleep(1.5)
                except Exception as e:
                    logger.error(f"Error terminating Chrome: {e}")
            else:
                return

        self.sig_launch_requested.emit()
        self.accept()


class FlowTabSelectionDialog(QDialog):
    """Dialog shown when multiple Google Flow tabs exist in the connected Chrome window."""
    def __init__(self, tabs: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Google Flow Tab")
        self.resize(480, 320)
        self.tabs = tabs
        self.selected_tab_index = 0
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #0d111a; color: #f1f5f9; }
            QLabel { color: #cbd5e1; font-size: 13px; }
            QRadioButton { color: #f1f5f9; font-size: 13px; padding: 4px; }
            QPushButton { background-color: #2563eb; color: #ffffff; font-weight: 700; padding: 8px 16px; border-radius: 6px; border: none; }
            QPushButton:hover { background-color: #1d4ed8; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_head = QLabel("Select Google Flow Tab")
        lbl_head.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Multiple Google Flow tabs were detected. Select the tab you want to automate:")
        layout.addWidget(lbl_desc)

        self.btn_group = QButtonGroup(self)
        for i, tab in enumerate(self.tabs):
            rb = QRadioButton(f"Google Flow — Tab {i + 1} ({tab.get('title', 'Flow')})")
            if i == 0:
                rb.setChecked(True)
            self.btn_group.addButton(rb, i)
            layout.addWidget(rb)

        layout.addStretch()

        h_btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #1e293b; color: #94a3b8;")
        btn_cancel.clicked.connect(self.reject)

        btn_connect = QPushButton("Connect to Tab")
        btn_connect.clicked.connect(self._on_connect)

        h_btns.addWidget(btn_cancel)
        h_btns.addStretch()
        h_btns.addWidget(btn_connect)
        layout.addLayout(h_btns)

    def _on_connect(self):
        self.selected_tab_index = self.btn_group.checkedId()
        self.accept()


class FlowNotFoundDialog(QDialog):
    """Dialog shown when Chrome is connected via CDP, but no Google Flow tab exists."""
    sig_open_flow = Signal()
    sig_scan_again = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google Flow Tab Not Found")
        self.resize(460, 260)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #0d111a; color: #f1f5f9; }
            QLabel { color: #cbd5e1; font-size: 13px; line-height: 1.4; }
            QPushButton#btnOpen { background-color: #2563eb; color: #ffffff; font-weight: 700; padding: 8px 16px; border-radius: 6px; border: none; }
            QPushButton#btnOpen:hover { background-color: #1d4ed8; }
            QPushButton#btnScan { background-color: #1e293b; color: #f8fafc; font-weight: 600; padding: 8px 14px; border-radius: 6px; border: 1px solid #334155; }
            QPushButton#btnScan:hover { background-color: #334155; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_head = QLabel("Google Flow Tab Not Found")
        lbl_head.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        layout.addWidget(lbl_head)

        lbl_body = QLabel(
            "No Google Flow tab was detected in the connected Chrome profile.<br><br>"
            "Please open Google Flow in your Chrome window, or click <b>'Open Google Flow'</b> below."
        )
        lbl_body.setWordWrap(True)
        layout.addWidget(lbl_body)

        layout.addStretch()

        h_btns = QHBoxLayout()
        btn_scan = QPushButton("Scan Again")
        btn_scan.setObjectName("btnScan")
        btn_scan.clicked.connect(self._on_scan)

        btn_open = QPushButton("Open Google Flow")
        btn_open.setObjectName("btnOpen")
        btn_open.clicked.connect(self._on_open)

        h_btns.addWidget(btn_scan)
        h_btns.addStretch()
        h_btns.addWidget(btn_open)
        layout.addLayout(h_btns)

    def _on_scan(self):
        self.sig_scan_again.emit()
        self.accept()

    def _on_open(self):
        self.sig_open_flow.emit()
        self.accept()


class ChromeExtensionSetupDialog(QDialog):
    """Dialog guiding user through 10-second setup of the Chrome Bridge Extension."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google Chrome Extension Setup (Zero Restart)")
        self.resize(580, 430)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #0b0f19; color: #f1f5f9; }
            QLabel { color: #cbd5e1; font-size: 13px; line-height: 1.5; }
            QLineEdit { background-color: #161c2a; border: 1px solid #2b354d; border-radius: 6px; color: #ffffff; padding: 7px 10px; font-size: 12px; }
            QPushButton#btnAction { background-color: #2563eb; color: #ffffff; font-weight: 700; padding: 8px 16px; border-radius: 6px; border: none; font-size: 12px; }
            QPushButton#btnAction:hover { background-color: #1d4ed8; }
            QPushButton#btnSecondary { background-color: #1e293b; color: #f8fafc; font-weight: 600; padding: 7px 14px; border-radius: 6px; border: 1px solid #334155; }
            QPushButton#btnSecondary:hover { background-color: #334155; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        lbl_title = QLabel("🧩 Chrome Extension Setup (Zero-Restart Connection)")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc;")
        layout.addWidget(lbl_title)

        lbl_intro = QLabel(
            "The Chained Evolution Studio bridge extension allows connecting directly to your "
            "open Chrome profile <b>without closing or restarting your browser</b>:"
        )
        lbl_intro.setWordWrap(True)
        layout.addWidget(lbl_intro)

        # Extension Folder path box
        v_path = QVBoxLayout()
        v_path.setSpacing(4)
        lbl_p = QLabel("Extension Folder Location:")
        lbl_p.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")
        v_path.addWidget(lbl_p)

        h_path = QHBoxLayout()
        ext_folder = str(BASE_DIR / "extension")
        self.txt_path = QLineEdit(ext_folder)
        self.txt_path.setReadOnly(True)
        h_path.addWidget(self.txt_path)

        btn_copy = QPushButton("📋 Copy Path")
        btn_copy.setObjectName("btnSecondary")
        btn_copy.clicked.connect(self._copy_path)
        h_path.addWidget(btn_copy)

        btn_open_folder = QPushButton("📁 Open Folder")
        btn_open_folder.setObjectName("btnSecondary")
        btn_open_folder.clicked.connect(self._open_folder)
        h_path.addWidget(btn_open_folder)
        v_path.addLayout(h_path)
        layout.addLayout(v_path)

        # 4 Step Instructions
        lbl_steps = QLabel(
            "<b>Quick Steps (15 Seconds):</b><br>"
            "1. In your Google Chrome, open <b>chrome://extensions</b> in a new tab.<br>"
            "2. Turn ON <b>'Developer mode'</b> toggle in the top-right corner.<br>"
            "3. Click <b>'Load unpacked'</b> button in the top-left, and select the folder above.<br>"
            "4. The extension connects automatically! You can now control your exact Flow project."
        )
        lbl_steps.setWordWrap(True)
        lbl_steps.setStyleSheet("background-color: #141b2d; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; color: #e2e8f0;")
        layout.addWidget(lbl_steps)

        layout.addStretch()

        h_bottom = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("btnAction")
        btn_close.clicked.connect(self.accept)
        h_bottom.addStretch()
        h_bottom.addWidget(btn_close)
        layout.addLayout(h_bottom)

    def _copy_path(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self.txt_path.text())
            QMessageBox.information(self, "Copied", "Extension folder path copied to clipboard!")

    def _open_folder(self):
        ext_folder = Path(self.txt_path.text())
        if ext_folder.is_dir() and sys.platform == "win32":
            os.startfile(str(ext_folder))


class ChromeAccountWidget(QFrame):
    sig_profile_changed = Signal(object)  # ChromeProfile
    sig_connection_status_changed = Signal(bool)  # is_flow_connected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile: Optional[ChromeProfile] = None
        self.connector = PlaywrightFlowConnector()
        self._init_ui()
        self._load_initial_profile()
        self._start_status_timer()

    def _init_ui(self):
        self.setObjectName("chromeAccountCard")
        self.setStyleSheet("""
            #chromeAccountCard {
                background-color: #10141f;
                border: 1px solid #1e2638;
                border-radius: 12px;
                padding: 12px;
            }
            QPushButton#linkBtn {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 12px;
            }
            QPushButton#linkBtn:hover {
                background-color: #2e3a52;
                border-color: #3b82f6;
            }
            QPushButton#connectChromeBtn {
                background-color: #1d4ed8;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                padding: 7px 14px;
            }
            QPushButton#connectChromeBtn:hover {
                background-color: #2563eb;
            }
            QPushButton#disconnectBtn {
                background-color: #334155;
                border: 1px solid #475569;
                border-radius: 6px;
                color: #f1f5f9;
                font-size: 12px;
                font-weight: 600;
                padding: 7px 14px;
            }
            QPushButton#disconnectBtn:hover {
                background-color: #475569;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header Title with badge 2
        h_title = QHBoxLayout()
        lbl_badge = QLabel("2")
        lbl_badge.setStyleSheet(
            "background-color: #2563eb; color: #ffffff; font-weight: bold; "
            "border-radius: 10px; min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; "
            "qproperty-alignment: AlignCenter;"
        )
        lbl_card_title = QLabel("Connect Google Flow Account & Project")
        lbl_card_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        h_title.addWidget(lbl_badge)
        h_title.addWidget(lbl_card_title)
        h_title.addStretch()
        layout.addLayout(h_title)

        # Row 1: Google Flow Account & Profile
        h_acc_row = QHBoxLayout()
        h_acc_row.setSpacing(10)

        self.lbl_avatar = QLabel()
        self.lbl_avatar.setFixedSize(32, 32)
        h_acc_row.addWidget(self.lbl_avatar)

        v_acc_info = QVBoxLayout()
        v_acc_info.setSpacing(2)
        h_acc_label_line = QHBoxLayout()
        lbl_acc_title = QLabel("Google Flow Account:")
        lbl_acc_title.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 600;")
        self.lbl_profile_name = QLabel("No Account Linked")
        self.lbl_profile_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #f1f5f9;")
        self.lbl_account_status = QLabel("● Disconnected")
        self.lbl_account_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8;")
        h_acc_label_line.addWidget(lbl_acc_title)
        h_acc_label_line.addWidget(self.lbl_profile_name)
        h_acc_label_line.addWidget(self.lbl_account_status)
        h_acc_label_line.addStretch()
        v_acc_info.addLayout(h_acc_label_line)

        self.lbl_profile_email = QLabel("")
        self.lbl_profile_email.setStyleSheet("font-size: 11px; color: #64748b;")
        v_acc_info.addWidget(self.lbl_profile_email)
        h_acc_row.addLayout(v_acc_info)
        h_acc_row.addStretch()

        self.btn_link = QPushButton("🔄 Change Account")
        self.btn_link.setObjectName("linkBtn")
        self.btn_link.clicked.connect(self._open_selector_dialog)
        h_acc_row.addWidget(self.btn_link)
        layout.addLayout(h_acc_row)

        # Row 2: Google Flow Project status line
        h_proj_status_row = QHBoxLayout()
        lbl_proj_title = QLabel("Google Flow Project:")
        lbl_proj_title.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 600;")
        self.lbl_project_status = QLabel("● Ready")
        self.lbl_project_status.setStyleSheet("font-size: 12px; font-weight: 700; color: #10b981;")
        self.lbl_flow_desc = QLabel("Flow project linked.")
        self.lbl_flow_desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        h_proj_status_row.addWidget(lbl_proj_title)
        h_proj_status_row.addWidget(self.lbl_project_status)
        h_proj_status_row.addSpacing(10)
        h_proj_status_row.addWidget(self.lbl_flow_desc)
        h_proj_status_row.addStretch()
        layout.addLayout(h_proj_status_row)

        # Row 3: Google Flow Project URL with Save button
        v_url = QVBoxLayout()
        v_url.setSpacing(4)
        lbl_url_title = QLabel("Google Flow Project URL:")
        lbl_url_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")
        v_url.addWidget(lbl_url_title)

        h_url = QHBoxLayout()
        self.txt_project_url = QLineEdit(get_flow_project_url())
        self.txt_project_url.setStyleSheet(
            "background-color: #141a29; border: 1px solid #28354d; border-radius: 6px; "
            "color: #f8fafc; padding: 6px 10px; font-size: 12px; font-family: Consolas, monospace;"
        )
        self.txt_project_url.setPlaceholderText("https://flow.google.com/project/...")
        h_url.addWidget(self.txt_project_url)

        self.btn_save_url = QPushButton("💾 Save")
        self.btn_save_url.setObjectName("linkBtn")
        self.btn_save_url.clicked.connect(self._save_project_url)
        h_url.addWidget(self.btn_save_url)
        v_url.addLayout(h_url)
        layout.addLayout(v_url)

        # Row 4: Action Buttons
        h_actions = QHBoxLayout()
        h_actions.setSpacing(8)

        self.btn_connect_flow = QPushButton("🔗  Connect to Flow Project")
        self.btn_connect_flow.setObjectName("connectChromeBtn")
        self.btn_connect_flow.clicked.connect(self.connect_to_open_chrome)
        h_actions.addWidget(self.btn_connect_flow)

        self.btn_extension_setup = QPushButton("🧩 Chrome Extension Setup")
        self.btn_extension_setup.setObjectName("linkBtn")
        self.btn_extension_setup.clicked.connect(self._open_extension_setup)
        h_actions.addWidget(self.btn_extension_setup)

        self.btn_scan = QPushButton("🔄")
        self.btn_scan.setFixedSize(32, 32)
        self.btn_scan.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #cbd5e1;")
        self.btn_scan.setToolTip("Scan open Chrome tabs & extension bridge")
        self.btn_scan.clicked.connect(self.scan_flow_tabs)
        h_actions.addWidget(self.btn_scan)

        layout.addLayout(h_actions)

    def _start_status_timer(self):
        """Poll Chrome process status and extension bridge periodically in background."""
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(3000)
        self.status_timer.timeout.connect(self._update_system_status)
        self.status_timer.start()
        self._update_system_status()

    def _update_system_status(self):
        """Update live status of Chrome, Extension bridge, and Flow project tab."""
        chrome_running = ChromeProfileManager.is_chrome_running()
        prof_name = self.current_profile.display_name if self.current_profile else "Default"
        bridge = ExtensionBridgeServer.get_instance()
        ext_connected = bridge.is_profile_connected(prof_name)

        if chrome_running or ext_connected:
            self.lbl_account_status.setText("● Connected")
            self.lbl_account_status.setStyleSheet("color: #10b981; font-weight: 700; font-size: 11px;")
        else:
            self.lbl_account_status.setText("● Browser Closed")
            self.lbl_account_status.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 11px;")

        # Flow project status
        if self.connector.is_connected and self.connector.is_flow_tab_ready():
            self.lbl_project_status.setText("● Ready")
            self.lbl_project_status.setStyleSheet("color: #10b981; font-weight: 700; font-size: 12px;")
            tab_title = self.connector.connected_tab_info.get("title", "Google Flow")
            self.lbl_flow_desc.setText(f"Active tab: '{tab_title}'")
            self.btn_connect_flow.setText("🔌  Disconnect")
            self.sig_connection_status_changed.emit(True)
        elif ext_connected:
            self.lbl_project_status.setText("● Ready (via Extension)")
            self.lbl_project_status.setStyleSheet("color: #10b981; font-weight: 700; font-size: 12px;")
            self.lbl_flow_desc.setText("Chrome extension active in selected profile.")
            self.btn_connect_flow.setText("🔗  Open / Verify Flow Project")
            self.sig_connection_status_changed.emit(True)
        else:
            if ChromeProfileManager.is_cdp_available(9222):
                tabs = ChromeProfileManager.find_flow_tabs(9222)
                if tabs:
                    self.lbl_project_status.setText("● Tab Detected")
                    self.lbl_project_status.setStyleSheet("color: #60a5fa; font-weight: 700; font-size: 12px;")
                    self.lbl_flow_desc.setText(f"Found {len(tabs)} Flow tab(s). Click Connect.")
                else:
                    self.lbl_project_status.setText("● Tab Not Found")
                    self.lbl_project_status.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 12px;")
                    self.lbl_flow_desc.setText("Chrome open. Open Flow or click Connect.")
            else:
                self.lbl_project_status.setText("● Disconnected")
                self.lbl_project_status.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 12px;")
                self.lbl_flow_desc.setText("Click 'Connect to Flow Project' to link.")
            self.btn_connect_flow.setText("🔗  Connect to Flow Project")
            self.sig_connection_status_changed.emit(False)

        self.btn_connect_flow.style().unpolish(self.btn_connect_flow)
        self.btn_connect_flow.style().polish(self.btn_connect_flow)

    def _save_project_url(self):
        url = self.txt_project_url.text().strip()
        if not url:
            url = DEFAULT_FLOW_PROJECT_URL
            self.txt_project_url.setText(url)
        set_flow_project_url(url)
        logger.info(f"Saved Google Flow project URL: {url}")
        QMessageBox.information(self, "Project URL Saved", f"✓ Saved Google Flow Project URL:\n{url}")

    def _open_extension_setup(self):
        dlg = ChromeExtensionSetupDialog(self)
        dlg.exec()

    def _load_initial_profile(self):
        saved = ChromeProfileManager.get_saved_profile()
        if saved:
            self.set_profile(saved)
        else:
            profiles = ChromeProfileManager.detect_all_profiles()
            if profiles:
                preferred = profiles[0]
                for p in profiles:
                    if "youtube" in p.display_name.lower():
                        preferred = p
                        break
                self.set_profile(preferred)

    def set_profile(self, profile: ChromeProfile):
        self.current_profile = profile
        ChromeProfileManager.save_linked_profile(profile)

        pix = profile.get_avatar_pixmap(size=32)
        self.lbl_avatar.setPixmap(pix)
        self.lbl_profile_name.setText(profile.display_name)
        self.lbl_profile_email.setText(profile.email or profile.directory_name)

        self.sig_profile_changed.emit(profile)
        logger.info(f"Selected Chrome Profile: {profile.display_name} ({profile.directory_name})")
        self._update_system_status()

    def _open_selector_dialog(self):
        dlg = ChromeProfileSelectorDialog(current_profile=self.current_profile, parent=self)
        dlg.sig_profile_chosen.connect(self.set_profile)
        dlg.exec()

    def scan_flow_tabs(self):
        """Manually trigger scan of tabs and update UI."""
        logger.info("Scanning open Chrome tabs for Google Flow...")
        self._update_system_status()

    def connect_to_open_chrome(self):
        """Connect to exact Flow project in selected Chrome profile without extra Chrome."""
        if not self.current_profile:
            QMessageBox.warning(self, "Profile Required", "Please link a Chrome profile first.")
            return

        proj_url = self.txt_project_url.text().strip()
        if not proj_url:
            proj_url = DEFAULT_FLOW_PROJECT_URL
            self.txt_project_url.setText(proj_url)
        set_flow_project_url(proj_url)

        prof_name = self.current_profile.display_name

        # If already connected, clicking disconnects safely
        if self.connector.is_connected and self.connector.is_flow_tab_ready():
            self.connector.close()
            self._update_system_status()
            logger.info("Disconnected from Google Flow tab.")
            return

        logger.info(f"Connecting to Google Flow project ({proj_url}) for profile: {prof_name}...")

        # 1. Try CDP session
        ok, status, tabs = self.connector.connect_to_existing_chrome(port=9222)
        if ok and (status == "CONNECTED_TO_FLOW" or status == "MULTIPLE_FLOW_TABS"):
            if status == "MULTIPLE_FLOW_TABS":
                dlg = FlowTabSelectionDialog(tabs, parent=self)
                if dlg.exec() == QDialog.Accepted:
                    sel_idx = dlg.selected_tab_index
                    chosen_tab = tabs[sel_idx]
                    self.connector.connect_to_existing_chrome(port=9222, target_tab_id=str(chosen_tab.get("index", 0)))

            nav_ok, nav_msg = self.connector.navigate_to_exact_project(proj_url)
            ver_ok, ver_msg = self.connector.verify_exact_project(proj_url, timeout_sec=20.0)
            self._update_system_status()

            if ver_ok:
                QMessageBox.information(
                    self,
                    "Google Flow Connected",
                    f"✓ Connected to Google Flow project successfully!\n\n"
                    f"Chrome Profile: {prof_name}\n"
                    f"Project URL: {proj_url}\n"
                    f"Status: Ready for chained automation"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Loading Flow Project",
                    f"Google Flow tab navigated, but still loading or requires attention:\n{ver_msg}"
                )
            return

        # 2. Check Extension Bridge
        bridge = ExtensionBridgeServer.get_instance()
        if bridge.is_profile_connected(prof_name):
            logger.info(f"Extension bridge active for profile '{prof_name}'. Opening project...")
            nav_ok, nav_msg = self.connector.navigate_to_exact_project(proj_url)
            ver_ok, ver_msg = self.connector.verify_exact_project(proj_url, timeout_sec=15.0)
            self._update_system_status()
            if ver_ok or nav_ok:
                QMessageBox.information(
                    self,
                    "Connected via Extension",
                    f"✓ Google Flow project opened via Chrome Extension!\n\n"
                    f"Profile: {prof_name}\n"
                    f"Project: {proj_url}\n"
                    f"Status: Ready"
                )
                return

        # 3. Chrome running without CDP or Extension
        if status == "CHROME_RUNNING_WITHOUT_CDP":
            ret = QMessageBox.question(
                self,
                "Connect Chrome Profile",
                f"Chrome profile '<b>{prof_name}</b>' is open.<br><br>"
                "<b>Choose your preferred connection method:</b><br><br>"
                "• <b>Click 'Yes'</b> to open Extension Setup (no Chrome restart required!)<br>"
                "• <b>Click 'No'</b> to restart Chrome with CDP automation enabled",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if ret == QMessageBox.Yes:
                self._open_extension_setup()
            elif ret == QMessageBox.No:
                dlg = ModeBAutomationDialog(self.current_profile, parent=self)
                dlg.sig_launch_requested.connect(self._launch_connected_chrome)
                dlg.exec()
            return

        # 4. Chrome not running
        if status == "CHROME_NOT_RUNNING":
            ret = QMessageBox.question(
                self,
                "Launch Chrome",
                f"Google Chrome is not open.\n\n"
                f"Launch Chrome with profile '{prof_name}' and open the project now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret == QMessageBox.Yes:
                self._launch_connected_chrome()
            return

        QMessageBox.warning(self, "Connection Issue", f"Could not connect to Chrome session: {status}")

    def _open_flow_in_session(self):
        """Open Google Flow tab in the connected Chrome session."""
        ok, msg = self.connector.open_flow_tab_in_existing_chrome()
        if ok:
            self._update_system_status()
            QMessageBox.information(self, "Google Flow Opened", "Google Flow was opened in a new tab and connected!")
        else:
            QMessageBox.warning(self, "Failed", f"Could not open Google Flow tab: {msg}")

    def _launch_connected_chrome(self):
        """Launch the user's Chrome with CDP enabled on port 9222."""
        prof_dir = self.current_profile.directory_name if self.current_profile else "Default"
        proj_url = self.txt_project_url.text().strip() or get_flow_project_url()
        ok, msg = ChromeProfileManager.launch_chrome_with_cdp(
            profile_dir_name=prof_dir,
            port=9222,
            url=proj_url
        )
        if not ok:
            QMessageBox.critical(self, "Launch Error", f"Could not launch Chrome: {msg}")
            return

        # Wait a few moments and connect
        QTimer.singleShot(2500, self._connect_after_launch)

    def _connect_after_launch(self):
        ok, status, tabs = self.connector.connect_to_existing_chrome(port=9222)
        if ok and status == "CONNECTED_TO_FLOW":
            self._update_system_status()
            QMessageBox.information(
                self,
                "Connected",
                f"✓ Connected to Google Flow in profile '{self.current_profile.display_name}'!"
            )
        else:
            self._update_system_status()
            logger.info(f"Initial connect check: {status}. Will re-check tabs.")
