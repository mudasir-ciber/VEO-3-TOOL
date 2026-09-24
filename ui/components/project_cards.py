"""Left column cards: Project Name, Master Image, and Scene Prompts matching mockup."""
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QPlainTextEdit, QFileDialog, QFrame, QApplication, QMessageBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal

from core.prompt_parser import PromptParser, ScenePrompt


class ProjectNameCard(QFrame):
    sig_name_changed = Signal(str)

    def __init__(self, initial_name: str = "Airplane Evolution", parent=None):
        super().__init__(parent)
        self.setObjectName("nameCard")
        self.setStyleSheet("""
            #nameCard {
                background-color: #10141f;
                border: 1px solid #1e2638;
                border-radius: 12px;
                padding: 12px;
            }
            QLineEdit {
                background-color: #0c0f18;
                border: 1px solid #232c40;
                border-radius: 8px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        self._init_ui(initial_name)

    def _init_ui(self, initial_name: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header Badge 1
        h_title = QHBoxLayout()
        lbl_badge = QLabel("1")
        lbl_badge.setStyleSheet(
            "background-color: #2563eb; color: #ffffff; font-weight: bold; "
            "border-radius: 10px; min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; "
            "qproperty-alignment: AlignCenter;"
        )
        lbl_card_title = QLabel("Project Name")
        lbl_card_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        h_title.addWidget(lbl_badge)
        h_title.addWidget(lbl_card_title)
        h_title.addStretch()
        layout.addLayout(h_title)

        self.txt_name = QLineEdit(initial_name)
        self.txt_name.textChanged.connect(self.sig_name_changed.emit)
        layout.addWidget(self.txt_name)

    def get_name(self) -> str:
        return self.txt_name.text().strip() or "Untitled Project"


class MasterImageCard(QFrame):
    sig_master_image_selected = Signal(str)
    sig_master_image_removed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_image_path: Optional[Path] = None
        self.setObjectName("masterCard")
        self.setStyleSheet("""
            #masterCard {
                background-color: #10141f;
                border: 1px solid #1e2638;
                border-radius: 12px;
                padding: 12px;
            }
            QPushButton {
                background-color: #1e2638;
                border: 1px solid #2e3a52;
                border-radius: 6px;
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #2b354d;
                border-color: #3b82f6;
            }
            QPushButton#removeBtn:hover {
                background-color: #450a0a;
                border-color: #ef4444;
                color: #fca5a5;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Header Badge 3
        h_title = QHBoxLayout()
        lbl_badge = QLabel("3")
        lbl_badge.setStyleSheet(
            "background-color: #2563eb; color: #ffffff; font-weight: bold; "
            "border-radius: 10px; min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; "
            "qproperty-alignment: AlignCenter;"
        )
        lbl_card_title = QLabel("Master Image")
        lbl_card_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        h_title.addWidget(lbl_badge)
        h_title.addWidget(lbl_card_title)
        h_title.addStretch()
        layout.addLayout(h_title)

        # Large Master Image Display
        self.lbl_preview = QLabel()
        self.lbl_preview.setMinimumHeight(150)
        self.lbl_preview.setMaximumHeight(200)
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #0b0e14; border: 1px dashed #242c40; border-radius: 8px;")
        self.lbl_preview.setText("🖼️ Click 'Change Image' to upload Master Image (Scene 1 Reference)")
        layout.addWidget(self.lbl_preview)

        # Action Buttons below image
        h_btns = QHBoxLayout()
        btn_change = QPushButton("🖼️ Change Image")
        btn_change.clicked.connect(self._browse_image)

        btn_remove = QPushButton("🗑️ Remove")
        btn_remove.setObjectName("removeBtn")
        btn_remove.clicked.connect(self._remove_image)

        h_btns.addWidget(btn_change)
        h_btns.addWidget(btn_remove)
        h_btns.addStretch()
        layout.addLayout(h_btns)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Master Starting Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.set_image(path)

    def set_image(self, file_path: str):
        p = Path(file_path).resolve()
        if p.is_file():
            self.current_image_path = p
            pix = QPixmap(str(p))
            if not pix.isNull():
                scaled = pix.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_preview.setPixmap(scaled)
                self.lbl_preview.setStyleSheet("background-color: #0b0e14; border: 1px solid #1e2638; border-radius: 8px;")
            self.sig_master_image_selected.emit(str(p))

    def _remove_image(self):
        self.current_image_path = None
        self.lbl_preview.clear()
        self.lbl_preview.setText("🖼️ Click 'Change Image' to upload Master Image (Scene 1 Reference)")
        self.lbl_preview.setStyleSheet("background-color: #0b0e14; border: 1px dashed #242c40; border-radius: 8px;")
        self.sig_master_image_removed.emit()


class ScenePromptsCard(QFrame):
    sig_prompts_changed = Signal(list)  # List[ScenePrompt]
    sig_run_clicked = Signal()
    sig_pause_clicked = Signal()
    sig_stop_clicked = Signal()
    sig_retry_clicked = Signal()
    sig_open_folder_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.next_scene_num = 1
        self.parsed_scenes: List[ScenePrompt] = []
        self.setObjectName("promptsCard")
        self.setStyleSheet("""
            #promptsCard {
                background-color: #10141f;
                border: 1px solid #1e2638;
                border-radius: 12px;
                padding: 12px;
            }
            QPlainTextEdit {
                background-color: #0c0f18;
                border: 1px solid #232c40;
                border-radius: 8px;
                padding: 8px 12px;
                color: #e2e8f0;
                font-size: 12px;
                line-height: 1.5;
            }
            QPlainTextEdit:focus {
                border: 1px solid #3b82f6;
            }
            QPushButton.secondaryBtn {
                background-color: #1a2233;
                border: 1px solid #28354f;
                border-radius: 6px;
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 600;
                padding: 5px 12px;
            }
            QPushButton.secondaryBtn:hover {
                background-color: #243048;
                border-color: #3b82f6;
            }
            QPushButton#btnRun {
                background-color: #10b981;
                border: 1px solid #34d399;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
                padding: 8px 24px;
            }
            QPushButton#btnRun:hover {
                background-color: #059669;
            }
            QPushButton#btnPause {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #f1f5f9;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 18px;
            }
            QPushButton#btnPause:hover {
                background-color: #334155;
            }
            QPushButton#btnStop {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #f87171;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 18px;
            }
            QPushButton#btnStop:hover {
                background-color: #450a0a;
                border-color: #ef4444;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Header Badge 4
        h_title = QHBoxLayout()
        lbl_badge = QLabel("4")
        lbl_badge.setStyleSheet(
            "background-color: #2563eb; color: #ffffff; font-weight: bold; "
            "border-radius: 10px; min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; "
            "qproperty-alignment: AlignCenter;"
        )
        lbl_card_title = QLabel("Scene Prompts")
        lbl_card_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        h_title.addWidget(lbl_badge)
        h_title.addWidget(lbl_card_title)
        h_title.addStretch()
        layout.addLayout(h_title)

        # Text Editor
        self.txt_prompts = QPlainTextEdit()
        self.txt_prompts.setMinimumHeight(150)
        self.txt_prompts.setPlaceholderText(
            "1. Airplane on runway ready for takeoff\n"
            "2. Airplane taking off from runway\n"
            "3. Airplane flying above clouds\n"
            "4. Airplane in stormy sky\n"
            "5. Airplane flying over mountains\n"
            "6. Airplane during sunset\n"
            "7. Airplane landing at airport\n"
            "8. Airplane parked at terminal\n"
            "9. Night view at airport\n"
            "10. Close up of airplane front"
        )
        self.txt_prompts.textChanged.connect(self._auto_parse)
        layout.addWidget(self.txt_prompts)

        # Action Buttons (Paste from Clipboard, Load from File)
        h_sub_btns = QHBoxLayout()
        btn_paste = QPushButton("📋 Paste from Clipboard")
        btn_paste.setProperty("class", "secondaryBtn")
        btn_paste.setStyleSheet("background-color: #1a2233; border: 1px solid #28354f; border-radius: 6px; color: #cbd5e1; font-size: 11px; font-weight: 600; padding: 5px 12px;")
        btn_paste.clicked.connect(self._paste_clipboard)

        btn_load = QPushButton("📄 Load from File")
        btn_load.setProperty("class", "secondaryBtn")
        btn_load.setStyleSheet("background-color: #1a2233; border: 1px solid #28354f; border-radius: 6px; color: #cbd5e1; font-size: 11px; font-weight: 600; padding: 5px 12px;")
        btn_load.clicked.connect(self._load_file)

        h_sub_btns.addWidget(btn_paste)
        h_sub_btns.addWidget(btn_load)
        h_sub_btns.addStretch()
        layout.addLayout(h_sub_btns)

        # Prompts counter text
        self.lbl_loaded_count = QLabel("0 prompts loaded")
        self.lbl_loaded_count.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(self.lbl_loaded_count)

        # Bottom Control Bar: Run, Pause, Stop
        h_controls = QHBoxLayout()
        h_controls.setSpacing(10)

        self.btn_run = QPushButton("▶   Run")
        self.btn_run.setObjectName("btnRun")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.clicked.connect(self.sig_run_clicked.emit)

        self.btn_pause = QPushButton("⏸  Pause")
        self.btn_pause.setObjectName("btnPause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.sig_pause_clicked.emit)

        self.btn_stop = QPushButton("⏹  Stop")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.sig_stop_clicked.emit)

        self.btn_retry = QPushButton("🔄  Retry Scene")
        self.btn_retry.setObjectName("btnPause")
        self.btn_retry.setToolTip("Retry the current active or failed scene")
        self.btn_retry.clicked.connect(self.sig_retry_clicked.emit)

        self.btn_open_folder = QPushButton("📁  Open Folder")
        self.btn_open_folder.setObjectName("btnPause")
        self.btn_open_folder.clicked.connect(self.sig_open_folder_clicked.emit)

        h_controls.addWidget(self.btn_run)
        h_controls.addWidget(self.btn_pause)
        h_controls.addWidget(self.btn_stop)
        h_controls.addWidget(self.btn_retry)
        h_controls.addStretch()
        h_controls.addWidget(self.btn_open_folder)

        layout.addLayout(h_controls)

    def set_next_scene_number(self, num: int):
        self.next_scene_num = num
        self._auto_parse()

    def _auto_parse(self):
        raw = self.txt_prompts.toPlainText().strip()
        start = self.next_scene_num if self.next_scene_num > 0 else 1
        self.parsed_scenes = PromptParser.parse_batch(raw, default_start_number=start)
        count = len(self.parsed_scenes)
        self.lbl_loaded_count.setText(f"{count} prompts loaded")
        self.sig_prompts_changed.emit(self.parsed_scenes)

    def _paste_clipboard(self):
        cb = QApplication.clipboard()
        text = cb.text()
        if text:
            self.txt_prompts.setPlainText(text)

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Prompts File", "", "Text Files (*.txt *.md *.prompt)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.txt_prompts.setPlainText(f.read())
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load file: {e}")

    def get_parsed_scenes(self) -> List[ScenePrompt]:
        return self.parsed_scenes

    def set_running_state(self, is_running: bool, is_paused: bool = False):
        if is_running:
            self.btn_run.setEnabled(False)
            self.btn_stop.setEnabled(True)
            if is_paused:
                self.btn_pause.setEnabled(False)
            else:
                self.btn_pause.setEnabled(True)
        else:
            self.btn_run.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
