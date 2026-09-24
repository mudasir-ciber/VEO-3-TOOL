"""
VEO 3 Multi-Profile Selection & Live Extension Discovery Widget
Displays all actively connected Chrome extension instances dynamically.
Allows selecting a specific profile to bind automation execution.
"""
from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QFont

from core.extension_bridge import ExtensionBridgeServer, ExtensionProfile
from connector.flow_extension import ExtensionFlowConnector
from core.logger import logger


class ProfileItemWidget(QFrame):
    sig_clicked = Signal(str)  # emits profile_name

    def __init__(self, profile: ExtensionProfile, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("profileItem")
        bg_col = "#172554" if self.is_selected else "#111625"
        border_col = "#3b82f6" if self.is_selected else "#232d42"

        self.setStyleSheet(f"""
            #profileItem {{
                background-color: {bg_col};
                border: 1.5px solid {border_col};
                border-radius: 8px;
                padding: 6px;
            }}
            #profileItem:hover {{
                background-color: #1a2238;
                border-color: #60a5fa;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        # Status Dot
        dot = QLabel("●")
        is_online = self.profile.is_online()
        if not is_online:
            dot_col = "#94a3b8"  # Gray
            status_text = "OFFLINE"
        elif self.profile.flow_status == "FLOW_READY":
            dot_col = "#10b981"  # Bright Green
            status_text = "FLOW READY"
        elif self.profile.flow_status == "FLOW_PROJECT_MISMATCH":
            dot_col = "#ef4444"  # Red
            status_text = "PROJECT MISMATCH"
        elif self.profile.flow_status == "FLOW_AUTH_REQUIRED":
            dot_col = "#f59e0b"  # Amber
            status_text = "SIGN-IN REQUIRED"
        else:
            dot_col = "#3b82f6"  # Blue
            status_text = "CONNECTED"

        dot.setStyleSheet(f"color: {dot_col}; font-size: 14px;")
        layout.addWidget(dot)

        # Profile Name
        lbl_name = QLabel(self.profile.profile_name)
        lbl_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(lbl_name)

        layout.addStretch()

        # Flow Status Badge
        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(f"color: {dot_col}; font-size: 11px; font-weight: 600;")
        layout.addWidget(lbl_status)

        # Active checkmark indicator
        if self.is_selected:
            lbl_active = QLabel("✓ Selected")
            lbl_active.setStyleSheet("color: #60a5fa; font-weight: 700; font-size: 11px; margin-left: 6px;")
            layout.addWidget(lbl_active)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.sig_clicked.emit(self.profile.profile_name)
        super().mousePressEvent(event)


class MultiProfileWidget(QFrame):
    sig_profile_selected = Signal(str)  # profileName

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bridge = ExtensionBridgeServer.get_instance()
        self.connector = ExtensionFlowConnector()
        self.selected_profile_name: Optional[str] = None

        self._init_ui()
        self._start_poll_timer()

    def _init_ui(self):
        self.setObjectName("cardMultiProfile")
        self.setStyleSheet("""
            #cardMultiProfile {
                background-color: #0d111a;
                border: 1px solid #1f2738;
                border-radius: 10px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Title Row
        h_title = QHBoxLayout()
        lbl_title = QLabel("CONNECTED CHROME PROFILES")
        lbl_title.setStyleSheet("font-size: 12px; font-weight: 800; color: #94a3b8; letter-spacing: 0.5px;")
        h_title.addWidget(lbl_title)

        self.lbl_count = QLabel("0 Connected")
        self.lbl_count.setStyleSheet("font-size: 11px; font-weight: 600; color: #60a5fa;")
        h_title.addStretch()
        h_title.addWidget(self.lbl_count)
        layout.addLayout(h_title)

        # Scroll Area for Profiles List
        self.scroll_area = QScrollArea()
        self.scroll_area.setFixedHeight(120)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #1e2538; border-radius: 6px; background-color: #090c14; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll_layout.setSpacing(4)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        # Selected Profile Card
        self.card_selected = QFrame()
        self.card_selected.setStyleSheet("background-color: #131926; border: 1px solid #232d42; border-radius: 8px; padding: 10px;")
        sel_layout = QVBoxLayout(self.card_selected)
        sel_layout.setContentsMargins(10, 8, 10, 8)
        sel_layout.setSpacing(6)

        h_sel_head = QHBoxLayout()
        self.lbl_sel_title = QLabel("Selected Profile: None")
        self.lbl_sel_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        h_sel_head.addWidget(self.lbl_sel_title)
        h_sel_head.addStretch()

        self.lbl_sel_instance = QLabel("ID: --")
        self.lbl_sel_instance.setStyleSheet("font-size: 11px; color: #94a3b8;")
        h_sel_head.addWidget(self.lbl_sel_instance)
        sel_layout.addLayout(h_sel_head)

        # Detail Indicators Row
        h_indicators = QHBoxLayout()
        self.lbl_ext_status = QLabel("Extension: Disconnected ○")
        self.lbl_ext_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")

        self.lbl_flow_tab_status = QLabel("Flow Tab: Not Found ○")
        self.lbl_flow_tab_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")

        self.lbl_project_status = QLabel("Project: Not Verified ○")
        self.lbl_project_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")

        h_indicators.addWidget(self.lbl_ext_status)
        h_indicators.addStretch()
        h_indicators.addWidget(self.lbl_flow_tab_status)
        h_indicators.addStretch()
        h_indicators.addWidget(self.lbl_project_status)
        sel_layout.addLayout(h_indicators)

        layout.addWidget(self.card_selected)

        # Help / Instructions button
        h_foot = QHBoxLayout()
        lbl_hint = QLabel("💡 Open Chrome profiles & Flow manually. Extensions appear automatically.")
        lbl_hint.setStyleSheet("font-size: 11px; color: #64748b;")
        h_foot.addWidget(lbl_hint)
        h_foot.addStretch()

        btn_help = QPushButton("📖 Setup Guide")
        btn_help.setStyleSheet("background-color: #1e2638; border: 1px solid #334155; color: #cbd5e1; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
        btn_help.clicked.connect(self._show_setup_guide)
        h_foot.addWidget(btn_help)
        layout.addLayout(h_foot)

    def _start_poll_timer(self):
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1200)
        self.poll_timer.timeout.connect(self.refresh_profiles_list)
        self.poll_timer.start()

    def select_profile(self, profile_name: str):
        self.selected_profile_name = profile_name
        self.connector.set_profile_name(profile_name)
        self.sig_profile_selected.emit(profile_name)
        logger.info(f"Target Chrome profile selected: '{profile_name}'")
        self.refresh_profiles_list()

    def refresh_profiles_list(self):
        """Update live list of profiles from bridge."""
        profiles = self.bridge.get_all_registered_profiles()
        active_profiles = self.bridge.get_active_profiles()

        self.lbl_count.setText(f"{len(active_profiles)} Active")

        # Auto-select first profile if none selected
        if not self.selected_profile_name and active_profiles:
            self.selected_profile_name = active_profiles[0].profile_name
            self.connector.set_profile_name(self.selected_profile_name)
            self.sig_profile_selected.emit(self.selected_profile_name)

        # Clear existing items in scroll layout
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not profiles:
            lbl_empty = QLabel("No Chrome extensions connected yet.\nOpen your Chrome profile with the VEO 3 Bridge extension installed.")
            lbl_empty.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic; padding: 12px; text-align: center;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(lbl_empty)
        else:
            for prof in profiles:
                is_sel = (self.selected_profile_name and self.selected_profile_name.lower() == prof.profile_name.lower())
                row = ProfileItemWidget(prof, is_selected=is_sel)
                row.sig_clicked.connect(self.select_profile)
                self.scroll_layout.addWidget(row)

        # Update Selected Profile Details
        if self.selected_profile_name:
            curr_prof = self.bridge.get_profile_by_name(self.selected_profile_name)
            if curr_prof:
                self.lbl_sel_title.setText(f"Selected Profile: {curr_prof.profile_name}")
                self.lbl_sel_instance.setText(f"ID: {curr_prof.instance_id}")

                if curr_prof.is_online():
                    self.lbl_ext_status.setText("Extension: Connected ✓")
                    self.lbl_ext_status.setStyleSheet("color: #10b981; font-weight: 600; font-size: 11px;")
                else:
                    self.lbl_ext_status.setText("Extension: Offline ○")
                    self.lbl_ext_status.setStyleSheet("color: #ef4444; font-weight: 600; font-size: 11px;")

                if curr_prof.flow_status == "FLOW_READY" or curr_prof.flow_tab_id is not None:
                    self.lbl_flow_tab_status.setText(f"Flow Tab: Connected (#{curr_prof.flow_tab_id or '✓'})")
                    self.lbl_flow_tab_status.setStyleSheet("color: #10b981; font-weight: 600; font-size: 11px;")
                elif curr_prof.flow_status == "FLOW_PROJECT_MISMATCH":
                    self.lbl_flow_tab_status.setText("Flow Tab: Project Mismatch ⚠")
                    self.lbl_flow_tab_status.setStyleSheet("color: #ef4444; font-weight: 600; font-size: 11px;")
                else:
                    self.lbl_flow_tab_status.setText("Flow Tab: Not Found ○")
                    self.lbl_flow_tab_status.setStyleSheet("color: #f59e0b; font-weight: 600; font-size: 11px;")

                if curr_prof.project_verified or curr_prof.flow_status == "FLOW_READY":
                    self.lbl_project_status.setText("Project: Verified ✓")
                    self.lbl_project_status.setStyleSheet("color: #10b981; font-weight: 600; font-size: 11px;")
                else:
                    self.lbl_project_status.setText("Project: Not Verified ○")
                    self.lbl_project_status.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 11px;")
            else:
                self.lbl_sel_title.setText(f"Selected Profile: {self.selected_profile_name} (Waiting...)")
        else:
            self.lbl_sel_title.setText("Selected Profile: None")
            self.lbl_sel_instance.setText("ID: --")
            self.lbl_ext_status.setText("Extension: Disconnected ○")
            self.lbl_flow_tab_status.setText("Flow Tab: Not Found ○")
            self.lbl_project_status.setText("Project: Not Verified ○")

    def _show_setup_guide(self):
        msg = (
            "<h3>VEO 3 Multi-Profile Setup Guide</h3>"
            "<p><b>1. Open Google Chrome</b> with your desired profile (e.g. YOUTUBE, MUZAMIL, HISTORY).</p>"
            "<p><b>2. Install the Extension</b>:</p>"
            "<ul>"
            "<li>Open <code>chrome://extensions</code> in Chrome.</li>"
            "<li>Enable <b>Developer mode</b> (top-right).</li>"
            "<li>Click <b>Load unpacked</b> and select the <code>Chrome Extension</code> folder.</li>"
            "<li>Click the extension icon in Chrome and set the Profile name (e.g. YOUTUBE).</li>"
            "</ul>"
            "<p><b>3. Open Google Flow</b> in that profile with your exact project.</p>"
            "<p><b>4. That's it!</b> The profile will immediately appear in the list above.</p>"
            "<p>Repeat for as many Chrome profiles as you want (1, 3, 10+ profiles supported concurrently!).</p>"
        )
        QMessageBox.information(self, "Setup Guide", msg)
