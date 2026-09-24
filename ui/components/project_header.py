"""Project header component for project creation, folder selection, and Master Image."""
import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QGroupBox, QFrame
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, Signal

from core.config import DEFAULT_PROJECTS_DIR
from core.project_manager import ProjectManager
from core.logger import logger


class ProjectHeaderWidget(QGroupBox):
    sig_project_changed = Signal(str, str)  # project_name, project_path
    sig_master_image_set = Signal(str)      # master_image_path

    def __init__(self, parent=None):
        super().__init__("1. PROJECT & MASTER IMAGE SETUP", parent)
        self.project_dir: Optional[Path] = None
        self.master_image_path: Optional[Path] = None
        self._init_ui()

    def _init_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(10)

        # 1. Project Name
        lbl_proj = QLabel("Project Name:")
        self.txt_project_name = QLineEdit("Airplane Evolution")
        self.txt_project_name.textChanged.connect(self._on_name_or_dir_changed)

        # 2. Output / Projects Root Folder
        lbl_dir = QLabel("Project Workspace:")
        self.txt_workspace_path = QLineEdit(str(DEFAULT_PROJECTS_DIR / "Airplane Evolution"))
        self.txt_workspace_path.setReadOnly(True)

        btn_browse_dir = QPushButton("Browse Workspace...")
        btn_browse_dir.clicked.connect(self._browse_workspace)

        btn_open_folder = QPushButton("📂 Open Folder")
        btn_open_folder.clicked.connect(self._open_in_explorer)

        # 3. Master Image Selection & Preview
        lbl_master = QLabel("Master Image (Scene 1 Reference):")
        self.txt_master_path = QLineEdit()
        self.txt_master_path.setPlaceholderText("Select starting Master Image (PNG / JPG / WebP)...")
        self.txt_master_path.setReadOnly(True)

        btn_browse_master = QPushButton("Upload Master Image")
        btn_browse_master.clicked.connect(self._browse_master_image)

        # Thumbnail Preview Box
        self.lbl_thumbnail = QLabel()
        self.lbl_thumbnail.setFixedSize(90, 70)
        self.lbl_thumbnail.setAlignment(Qt.AlignCenter)
        self.lbl_thumbnail.setStyleSheet("border: 1px dashed #4b5563; border-radius: 4px; background: #0b0c10; color: #6b7280; font-size: 11px;")
        self.lbl_thumbnail.setText("No Preview")

        # Assemble Grid
        layout.addWidget(lbl_proj, 0, 0)
        layout.addWidget(self.txt_project_name, 0, 1, 1, 2)

        layout.addWidget(lbl_dir, 1, 0)
        layout.addWidget(self.txt_workspace_path, 1, 1)
        h_dir_btns = QHBoxLayout()
        h_dir_btns.addWidget(btn_browse_dir)
        h_dir_btns.addWidget(btn_open_folder)
        layout.addLayout(h_dir_btns, 1, 2)

        layout.addWidget(lbl_master, 2, 0)
        layout.addWidget(self.txt_master_path, 2, 1)
        layout.addWidget(btn_browse_master, 2, 2)

        layout.addWidget(self.lbl_thumbnail, 0, 3, 3, 1)

    def _on_name_or_dir_changed(self):
        name = self.txt_project_name.text().strip() or "Untitled Project"
        base = DEFAULT_PROJECTS_DIR
        new_dir = base / name
        self.txt_workspace_path.setText(str(new_dir))
        self.project_dir = new_dir
        self.sig_project_changed.emit(name, str(new_dir))

    def _browse_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Parent Directory", str(DEFAULT_PROJECTS_DIR))
        if folder:
            name = self.txt_project_name.text().strip() or "Untitled Project"
            new_dir = Path(folder) / name
            self.txt_workspace_path.setText(str(new_dir))
            self.project_dir = new_dir
            self.sig_project_changed.emit(name, str(new_dir))

    def _open_in_explorer(self):
        target = self.get_project_path()
        target.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(target))
        else:
            subprocess.run(["xdg-open", str(target)])

    def _browse_master_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Master Starting Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if file_path:
            self.set_master_image(file_path)

    def set_master_image(self, file_path: str):
        p = Path(file_path).resolve()
        if p.is_file():
            self.master_image_path = p
            self.txt_master_path.setText(str(p))

            # Render thumbnail
            pix = QPixmap(str(p))
            if not pix.isNull():
                scaled = pix.scaled(self.lbl_thumbnail.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_thumbnail.setPixmap(scaled)
            else:
                self.lbl_thumbnail.setText("Invalid Image")

            self.sig_master_image_set.emit(str(p))

    def get_project_path(self) -> Path:
        return Path(self.txt_workspace_path.text().strip()).resolve()

    def get_project_name(self) -> str:
        return self.txt_project_name.text().strip() or "Untitled Project"
