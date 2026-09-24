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
    QRadioButton, QButtonGroup, QProgressBar
)
from PySide6.QtGui import QPixmap, QIcon, QColor, QFont
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from core.chrome_profile_manager import ChromeProfileManager, ChromeProfile
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
                    subprocess.run(["taskkill", "/IM", "chrome.exe", "/T"], capture_output=True)
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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(16)

        # Left Column: Profile Card & Link Button
        v_left = QVBoxLayout()
        v_left.setSpacing(8)

        # Header Title with badge 2
        h_title = QHBoxLayout()
        lbl_badge = QLabel("2")
        lbl_badge.setStyleSheet(
            "background-color: #2563eb; color: #ffffff; font-weight: bold; "
            "border-radius: 10px; min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; "
            "qproperty-alignment: AlignCenter;"
        )
        lbl_card_title = QLabel("Connect Chrome Account")
        lbl_card_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        h_title.addWidget(lbl_badge)
        h_title.addWidget(lbl_card_title)
        h_title.addStretch()
        v_left.addLayout(h_title)

        # Profile Pill (Avatar + Name + Status + Refresh)
        self.frame_profile = QFrame()
        self.frame_profile.setStyleSheet("background-color: #161c2b; border: 1px solid #252f44; border-radius: 8px; padding: 6px;")
        h_prof = QHBoxLayout(self.frame_profile)
        h_prof.setContentsMargins(8, 4, 8, 4)
        h_prof.setSpacing(10)

        self.lbl_avatar = QLabel()
        self.lbl_avatar.setFixedSize(36, 36)
        h_prof.addWidget(self.lbl_avatar)

        v_names = QVBoxLayout()
        v_names.setSpacing(1)
        self.lbl_profile_name = QLabel("No Chrome Account Linked")
        self.lbl_profile_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #f1f5f9;")
        self.lbl_profile_email = QLabel("Click Link Account to connect")
        self.lbl_profile_email.setStyleSheet("font-size: 11px; color: #94a3b8;")
        v_names.addWidget(self.lbl_profile_name)
        v_names.addWidget(self.lbl_profile_email)
        h_prof.addLayout(v_names)

        h_prof.addStretch()

        # Browser Open status indicator
        v_browser_stat = QVBoxLayout()
        v_browser_stat.setSpacing(1)
        v_browser_stat.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_browser_status = QLabel("● Browser Not Open")
        self.lbl_browser_status.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 11px;")
        v_browser_stat.addWidget(self.lbl_browser_status)
        h_prof.addLayout(v_browser_stat)

        v_left.addWidget(self.frame_profile)

        # Link / Change Account button
        self.btn_link = QPushButton("🔗  Link / Change Account")
        self.btn_link.setObjectName("linkBtn")
        self.btn_link.clicked.connect(self._open_selector_dialog)
        v_left.addWidget(self.btn_link)

        layout.addLayout(v_left, stretch=3)

        # Right Column: Google Flow Status & Action Buttons
        self.frame_flow_status = QFrame()
        self.frame_flow_status.setStyleSheet("background-color: #121824; border: 1px solid #1e293b; border-radius: 8px; padding: 10px;")
        v_status = QVBoxLayout(self.frame_flow_status)
        v_status.setContentsMargins(10, 8, 10, 8)
        v_status.setSpacing(6)

        h_stat_head = QHBoxLayout()
        self.lbl_flow_icon = QLabel("⚪")
        self.lbl_flow_title = QLabel("Google Flow")
        self.lbl_flow_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        self.lbl_flow_state = QLabel("● Disconnected")
        self.lbl_flow_state.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")

        h_stat_head.addWidget(self.lbl_flow_icon)
        h_stat_head.addWidget(self.lbl_flow_title)
        h_stat_head.addStretch()
        h_stat_head.addWidget(self.lbl_flow_state)
        v_status.addLayout(h_stat_head)

        self.lbl_flow_desc = QLabel("Connect to your open Chrome browser to automate Google Flow.")
        self.lbl_flow_desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.lbl_flow_desc.setWordWrap(True)
        v_status.addWidget(self.lbl_flow_desc)

        # Buttons
        h_actions = QHBoxLayout()
        self.btn_connect_chrome = QPushButton("🔗  Connect to Open Chrome")
        self.btn_connect_chrome.setObjectName("connectChromeBtn")
        self.btn_connect_chrome.clicked.connect(self.connect_to_open_chrome)

        self.btn_scan = QPushButton("🔄")
        self.btn_scan.setFixedSize(30, 30)
        self.btn_scan.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #cbd5e1;")
        self.btn_scan.setToolTip("Scan open Chrome tabs")
        self.btn_scan.clicked.connect(self.scan_flow_tabs)

        h_actions.addWidget(self.btn_connect_chrome)
        h_actions.addWidget(self.btn_scan)
        v_status.addLayout(h_actions)

        layout.addWidget(self.frame_flow_status, stretch=3)

    def _start_status_timer(self):
        """Poll Chrome process status periodically in background."""
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(4000)
        self.status_timer.timeout.connect(self._update_system_status)
        self.status_timer.start()
        self._update_system_status()

    def _update_system_status(self):
        """Update live status of Chrome and CDP endpoint."""
        chrome_running = ChromeProfileManager.is_chrome_running()
        if chrome_running:
            self.lbl_browser_status.setText("● Browser Open")
            self.lbl_browser_status.setStyleSheet("color: #10b981; font-weight: 600; font-size: 11px;")
        else:
            self.lbl_browser_status.setText("● Browser Closed")
            self.lbl_browser_status.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 11px;")

        # Check if flow tab is alive
        if self.connector.is_connected and self.connector.is_flow_tab_ready():
            self.lbl_flow_icon.setText("🟢")
            self.lbl_flow_state.setText("● Connected to Existing Tab")
            self.lbl_flow_state.setStyleSheet("color: #10b981; font-weight: 600; font-size: 11px;")
            tab_title = self.connector.connected_tab_info.get("title", "Google Flow")
            self.lbl_flow_desc.setText(f"Controlling active tab: '{tab_title}'")
            self.btn_connect_chrome.setText("🔌  Disconnect")
            self.btn_connect_chrome.setObjectName("disconnectBtn")
            self.sig_connection_status_changed.emit(True)
        elif self.connector.is_connected:
            self.lbl_flow_icon.setText("🟡")
            self.lbl_flow_state.setText("● Tab Lost")
            self.lbl_flow_state.setStyleSheet("color: #f59e0b; font-weight: 600; font-size: 11px;")
            self.lbl_flow_desc.setText("Google Flow tab was closed or redirected.")
            self.btn_connect_chrome.setText("🔗  Connect to Open Chrome")
            self.btn_connect_chrome.setObjectName("connectChromeBtn")
            self.sig_connection_status_changed.emit(False)
        else:
            # Check if CDP port has flow tabs waiting
            if ChromeProfileManager.is_cdp_available(9222):
                tabs = ChromeProfileManager.find_flow_tabs(9222)
                if tabs:
                    self.lbl_flow_icon.setText("🔵")
                    self.lbl_flow_state.setText("● Tab Detected")
                    self.lbl_flow_state.setStyleSheet("color: #60a5fa; font-weight: 600; font-size: 11px;")
                    self.lbl_flow_desc.setText(f"Found {len(tabs)} Google Flow tab(s). Click to connect.")
                else:
                    self.lbl_flow_icon.setText("⚪")
                    self.lbl_flow_state.setText("● Tab Not Found")
                    self.lbl_flow_state.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 11px;")
                    self.lbl_flow_desc.setText("Chrome is open, but no Google Flow tab found.")
            self.btn_connect_chrome.setText("🔗  Connect to Open Chrome")
            self.btn_connect_chrome.setObjectName("connectChromeBtn")
            self.sig_connection_status_changed.emit(False)

        # Refresh style
        self.btn_connect_chrome.style().unpolish(self.btn_connect_chrome)
        self.btn_connect_chrome.style().polish(self.btn_connect_chrome)

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

        pix = profile.get_avatar_pixmap(size=36)
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
        """Main connection workflow adhering to Mode A & Mode B requirements."""
        if not self.current_profile:
            QMessageBox.warning(self, "Profile Required", "Please link a Chrome profile first.")
            return

        # If already connected, clicking the button disconnects safely
        if self.connector.is_connected and self.connector.is_flow_tab_ready():
            self.connector.close()
            self._update_system_status()
            logger.info("Disconnected from Google Flow tab.")
            return

        logger.info(f"Checking existing browser connection for profile: {self.current_profile.display_name}...")

        # 1. Mode A: Try to connect to existing automation session
        ok, status, tabs = self.connector.connect_to_existing_chrome(port=9222)

        if ok and status == "CONNECTED_TO_FLOW":
            self._update_system_status()
            tab_name = tabs[0].get("title", "Google Flow") if tabs else "Google Flow"
            QMessageBox.information(
                self,
                "Google Flow Connected",
                f"✓ Connected to Google Flow tab successfully!\n\n"
                f"Chrome Profile: {self.current_profile.display_name}\n"
                f"Active Tab: {tab_name}\n"
                f"Status: Ready for chained automation"
            )
            return

        if status == "MULTIPLE_FLOW_TABS":
            # Prompt user to choose which Flow tab to connect to
            dlg = FlowTabSelectionDialog(tabs, parent=self)
            if dlg.exec() == QDialog.Accepted:
                sel_idx = dlg.selected_tab_index
                chosen_tab = tabs[sel_idx]
                self.connector.connect_to_existing_chrome(port=9222, target_tab_id=str(chosen_tab.get("index", 0)))
                self._update_system_status()
            return

        if status == "FLOW_TAB_NOT_FOUND":
            # Chrome is connected via CDP, but Flow is not open
            dlg = FlowNotFoundDialog(parent=self)
            dlg.sig_open_flow.connect(self._open_flow_in_session)
            dlg.sig_scan_again.connect(self.connect_to_open_chrome)
            dlg.exec()
            return

        # 2. Mode B: Chrome is running normally without CDP
        if status == "CHROME_RUNNING_WITHOUT_CDP":
            dlg = ModeBAutomationDialog(self.current_profile, parent=self)
            dlg.sig_launch_requested.connect(self._launch_connected_chrome)
            dlg.exec()
            return

        # 3. Chrome is not running at all
        if status == "CHROME_NOT_RUNNING":
            ret = QMessageBox.question(
                self,
                "Launch Chrome",
                f"Google Chrome is not currently open.\n\n"
                f"Would you like to launch Chrome with profile '{self.current_profile.display_name}' "
                "and open Google Flow now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret == QMessageBox.Yes:
                self._launch_connected_chrome()
            return

        QMessageBox.warning(self, "Connection Failed", f"Could not connect to Chrome session: {status}")

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
        ok, msg = ChromeProfileManager.launch_chrome_with_cdp(
            profile_dir_name=prof_dir,
            port=9222,
            url="https://flow.google.com/"
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
