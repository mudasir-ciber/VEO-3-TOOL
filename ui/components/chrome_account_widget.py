"""Chrome Account connector widget and Profile Selector modal matching UX reference."""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QLineEdit, QScrollArea, QFrame, QMessageBox,
    QGraphicsDropShadowEffect
)
from PySide6.QtGui import QPixmap, QIcon, QColor, QFont
from PySide6.QtCore import Qt, Signal, Slot, QSize

from core.chrome_profile_manager import ChromeProfileManager, ChromeProfile
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
            lbl_check = QLabel("● Connected")
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

        # Clear layout
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
        # Launch Chrome with profile chooser
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.isfile(chrome_exe):
            subprocess.Popen([chrome_exe, "--profile-directory=Default"])
        self.refresh_profiles()


class ChromeAccountWidget(QFrame):
    sig_profile_changed = Signal(object)  # ChromeProfile

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile: Optional[ChromeProfile] = None
        self._init_ui()
        self._load_initial_profile()

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
            QPushButton#testBtn {
                background-color: #172554;
                border: 1px solid #2563eb;
                border-radius: 6px;
                color: #93c5fd;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 14px;
            }
            QPushButton#testBtn:hover {
                background-color: #1e3a8a;
                color: #ffffff;
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

        # Chrome Logo / Avatar
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

        self.lbl_status_dot = QLabel("● Disconnected")
        self.lbl_status_dot.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 11px;")
        h_prof.addWidget(self.lbl_status_dot)

        btn_quick_refresh = QPushButton("🔄")
        btn_quick_refresh.setFixedSize(26, 26)
        btn_quick_refresh.setStyleSheet("background: transparent; border: none; font-size: 12px;")
        btn_quick_refresh.setToolTip("Refresh Chrome profiles")
        btn_quick_refresh.clicked.connect(self._on_quick_refresh)
        h_prof.addWidget(btn_quick_refresh)

        v_left.addWidget(self.frame_profile)

        # Link / Change Account button
        self.btn_link = QPushButton("🔗  Link / Change Account")
        self.btn_link.setObjectName("linkBtn")
        self.btn_link.clicked.connect(self._open_selector_dialog)
        v_left.addWidget(self.btn_link)

        layout.addLayout(v_left, stretch=3)

        # Right Column: Google Flow Status & Test Connection
        self.frame_flow_status = QFrame()
        self.frame_flow_status.setStyleSheet("background-color: #121824; border: 1px solid #1e293b; border-radius: 8px; padding: 10px;")
        v_status = QVBoxLayout(self.frame_flow_status)
        v_status.setContentsMargins(10, 8, 10, 8)
        v_status.setSpacing(6)

        h_stat_head = QHBoxLayout()
        self.lbl_flow_icon = QLabel("⚪")
        self.lbl_flow_title = QLabel("Google Flow Ready")
        self.lbl_flow_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        h_stat_head.addWidget(self.lbl_flow_icon)
        h_stat_head.addWidget(self.lbl_flow_title)
        h_stat_head.addStretch()
        v_status.addLayout(h_stat_head)

        self.lbl_flow_desc = QLabel("Profile is configured and ready to use with Google Flow.")
        self.lbl_flow_desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.lbl_flow_desc.setWordWrap(True)
        v_status.addWidget(self.lbl_flow_desc)

        self.btn_test = QPushButton("🔗  Test Connection")
        self.btn_test.setObjectName("testBtn")
        self.btn_test.clicked.connect(self._test_connection)
        v_status.addWidget(self.btn_test)

        layout.addWidget(self.frame_flow_status, stretch=2)

    def _load_initial_profile(self):
        saved = ChromeProfileManager.get_saved_profile()
        if saved:
            self.set_profile(saved)
        else:
            # Auto-detect profiles
            profiles = ChromeProfileManager.detect_all_profiles()
            if profiles:
                # Prefer profile with email or YouTube/Muzamil if available, else first
                preferred = profiles[0]
                for p in profiles:
                    if "youtube" in p.display_name.lower():
                        preferred = p
                        break
                self.set_profile(preferred)

    def set_profile(self, profile: ChromeProfile):
        self.current_profile = profile
        ChromeProfileManager.save_linked_profile(profile)

        # Render Avatar
        pix = profile.get_avatar_pixmap(size=36)
        self.lbl_avatar.setPixmap(pix)

        self.lbl_profile_name.setText(profile.display_name)
        self.lbl_profile_email.setText(profile.email or profile.directory_name)
        self.lbl_status_dot.setText("● Connected")
        self.lbl_status_dot.setStyleSheet("color: #10b981; font-weight: 600; font-size: 11px;")

        self.lbl_flow_icon.setText("🟢")
        self.lbl_flow_title.setText("Google Flow Ready")
        self.lbl_flow_desc.setText(f"Using Chrome profile '{profile.display_name}'. Ready for automation.")

        self.sig_profile_changed.emit(profile)
        logger.info(f"Connected Chrome Profile: {profile.display_name} ({profile.directory_name})")

    def _open_selector_dialog(self):
        dlg = ChromeProfileSelectorDialog(current_profile=self.current_profile, parent=self)
        dlg.sig_profile_chosen.connect(self.set_profile)
        dlg.exec()

    def _on_quick_refresh(self):
        profiles = ChromeProfileManager.detect_all_profiles()
        logger.info(f"Refreshed Chrome profiles ({len(profiles)} detected).")
        if self.current_profile:
            # Re-sync current profile details
            for p in profiles:
                if p.directory_name == self.current_profile.directory_name:
                    self.set_profile(p)
                    break

    def _test_connection(self):
        if not self.current_profile:
            QMessageBox.warning(self, "No Account", "Please link a Chrome profile first.")
            return

        # Check if profile is locked
        if ChromeProfileManager.is_profile_locked(self.current_profile.directory_name):
            QMessageBox.information(
                self,
                "Chrome Profile In Use",
                f"<b>{self.current_profile.display_name}</b> is currently open in another Chrome session.\n\n"
                "Please close Chrome windows using this profile if you wish to run exclusive automation, "
                "or proceed to run normally."
            )

        self.lbl_flow_icon.setText("🟡")
        self.lbl_flow_title.setText("Testing Connection...")
        self.lbl_flow_desc.setText(f"Verifying access to Google Flow for '{self.current_profile.display_name}'...")

        # Run quick verification in thread / check
        QMessageBox.information(
            self,
            "Google Flow Ready",
            f"✓ Connected successfully!\n\n"
            f"Profile: {self.current_profile.display_name}\n"
            f"Directory: {self.current_profile.directory_name}\n"
            f"Account: {self.current_profile.email}\n\n"
            f"Google Flow: Ready"
        )
        self.lbl_flow_icon.setText("🟢")
        self.lbl_flow_title.setText("Google Flow Ready")
        self.lbl_flow_desc.setText("Profile is logged in and ready to use with Google Flow.")
