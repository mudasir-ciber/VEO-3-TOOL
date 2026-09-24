"""Sidebar component matching the mockup UI."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, Signal

from core.config import APP_NAME


class SidebarWidget(QFrame):
    sig_nav_create_project = Signal()
    sig_nav_my_projects = Signal()
    sig_nav_settings = Signal()
    sig_nav_help = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(230)
        self.setObjectName("sidebarFrame")
        self.setStyleSheet("""
            #sidebarFrame {
                background-color: #0c0f18;
                border-right: 1px solid #1a2233;
            }
            QPushButton.navBtn {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                color: #94a3b8;
                text-align: left;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton.navBtn:hover {
                background-color: #161e2e;
                color: #f1f5f9;
            }
            QPushButton.navBtnActive {
                background-color: #1e3a8a;
                border: 1px solid #2563eb;
                border-radius: 8px;
                color: #ffffff;
                text-align: left;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 700;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.setSpacing(14)

        # App Logo & Branding
        v_brand = QVBoxLayout()
        v_brand.setSpacing(4)

        lbl_logo = QLabel("▶")
        lbl_logo.setFixedSize(36, 36)
        lbl_logo.setAlignment(Qt.AlignCenter)
        lbl_logo.setStyleSheet("""
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3b82f6, stop:1 #6366f1);
            color: #ffffff;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
        """)

        lbl_app_name = QLabel("Chained\nEvolution Studio")
        lbl_app_name.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff; line-height: 1.2;")

        lbl_tagline = QLabel("Turn One Image Into a Complete Video Story")
        lbl_tagline.setStyleSheet("font-size: 10px; color: #64748b;")
        lbl_tagline.setWordWrap(True)

        v_brand.addWidget(lbl_logo)
        v_brand.addSpacing(4)
        v_brand.addWidget(lbl_app_name)
        v_brand.addWidget(lbl_tagline)
        layout.addLayout(v_brand)

        layout.addSpacing(12)

        # Nav Buttons
        self.btn_create = QPushButton("🏠  Create Project")
        self.btn_create.setProperty("class", "navBtnActive")
        self.btn_create.setStyleSheet("background-color: #172554; border: 1px solid #2563eb; border-radius: 8px; color: #ffffff; text-align: left; padding: 10px 14px; font-weight: 700;")
        self.btn_create.clicked.connect(self.sig_nav_create_project.emit)
        layout.addWidget(self.btn_create)

        self.btn_projects = QPushButton("📁  My Projects")
        self.btn_projects.setProperty("class", "navBtn")
        self.btn_projects.setStyleSheet("background-color: transparent; border: none; border-radius: 8px; color: #94a3b8; text-align: left; padding: 10px 14px; font-weight: 600;")
        self.btn_projects.clicked.connect(self.sig_nav_my_projects.emit)
        layout.addWidget(self.btn_projects)

        self.btn_settings = QPushButton("⚙  Settings")
        self.btn_settings.setProperty("class", "navBtn")
        self.btn_settings.setStyleSheet("background-color: transparent; border: none; border-radius: 8px; color: #94a3b8; text-align: left; padding: 10px 14px; font-weight: 600;")
        self.btn_settings.clicked.connect(self.sig_nav_settings.emit)
        layout.addWidget(self.btn_settings)

        self.btn_help = QPushButton("❓  Help")
        self.btn_help.setProperty("class", "navBtn")
        self.btn_help.setStyleSheet("background-color: transparent; border: none; border-radius: 8px; color: #94a3b8; text-align: left; padding: 10px 14px; font-weight: 600;")
        self.btn_help.clicked.connect(self.sig_nav_help.emit)
        layout.addWidget(self.btn_help)

        layout.addStretch()

        # Version tag at bottom
        lbl_version = QLabel("v1.0.0 (Windows Native)")
        lbl_version.setStyleSheet("font-size: 10px; color: #475569;")
        layout.addWidget(lbl_version)
