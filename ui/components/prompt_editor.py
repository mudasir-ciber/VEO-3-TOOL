"""Batch Scene Prompt Editor with continuity indicator and scene parser."""
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QFileDialog, QGroupBox, QFrame
)
from PySide6.QtCore import Qt, Signal

from core.prompt_parser import PromptParser, ScenePrompt
from core.logger import logger


class PromptEditorWidget(QGroupBox):
    sig_prompts_updated = Signal(list)  # list of ScenePrompt

    def __init__(self, parent=None):
        super().__init__("2. BATCH SCENE PROMPTS & CONTINUITY", parent)
        self.last_completed_scene = 0
        self.current_reference_str = "Master Image.png"
        self.next_scene_num = 1
        self.parsed_scenes: List[ScenePrompt] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 1. Continuity Status Banner
        self.frame_continuity = QFrame()
        self.frame_continuity.setStyleSheet("background-color: #161824; border: 1px solid #32384e; border-radius: 6px; padding: 6px;")
        h_cont = QHBoxLayout(self.frame_continuity)
        h_cont.setContentsMargins(6, 4, 6, 4)

        self.lbl_last_completed = QLabel("Last Completed: <b>None (Scene 0)</b>")
        self.lbl_current_ref = QLabel("Current Chain Reference: <b>Master Image.png</b>")
        self.lbl_next_scene = QLabel("Next Scene: <b>1</b>")
        self.lbl_scenes_count = QLabel("Scenes Loaded: <span style='color:#38bdf8; font-weight:bold;'>0</span>")

        h_cont.addWidget(self.lbl_last_completed)
        h_cont.addWidget(QLabel(" | "))
        h_cont.addWidget(self.lbl_current_ref)
        h_cont.addWidget(QLabel(" | "))
        h_cont.addWidget(self.lbl_next_scene)
        h_cont.addStretch()
        h_cont.addWidget(self.lbl_scenes_count)

        layout.addWidget(self.frame_continuity)

        # 2. Text Input Area
        self.txt_prompts = QPlainTextEdit()
        self.txt_prompts.setPlaceholderText(
            "Paste your batch of scene prompts here...\n\n"
            "Example Batch 1 (Scenes 1-10):\n"
            "SCENE 1: Master airplane on the runway preparing for takeoff\n"
            "SCENE 2: The airplane takes off into the stormy clouds\n"
            "SCENE 3: The wings expand with supersonic propulsion\n\n"
            "Or plain paragraphs separated by blank lines.\n"
            "When you run Batch 2 (Scenes 11-20), the project will automatically start from Scene 11 using Scene 10's final frame!"
        )
        self.txt_prompts.textChanged.connect(self._auto_parse)
        layout.addWidget(self.txt_prompts)

        # 3. Action Buttons
        h_actions = QHBoxLayout()
        btn_import = QPushButton("📄 Import Prompts File...")
        btn_import.clicked.connect(self._import_file)

        btn_parse = QPushButton("🔄 Refresh & Validate Prompts")
        btn_parse.clicked.connect(self._auto_parse)

        btn_sample = QPushButton("Load Sample Batch")
        btn_sample.clicked.connect(self._load_sample)

        h_actions.addWidget(btn_import)
        h_actions.addWidget(btn_sample)
        h_actions.addStretch()
        h_actions.addWidget(btn_parse)

        layout.addLayout(h_actions)

    def set_continuity_info(self, last_completed: int, current_reference_name: str, next_scene: int):
        """Update live status when project state changes or after scene completion."""
        self.last_completed_scene = last_completed
        self.current_reference_str = current_reference_name
        self.next_scene_num = next_scene

        completed_text = f"Scene {last_completed}" if last_completed > 0 else "None (Scene 0)"
        self.lbl_last_completed.setText(f"Last Completed: <b>{completed_text}</b>")
        self.lbl_current_ref.setText(f"Current Chain Reference: <b style='color:#10b981;'>{current_reference_name}</b>")
        self.lbl_next_scene.setText(f"Next Scene: <b style='color:#6366f1;'>{next_scene}</b>")

        # Re-parse to adapt default start scene numbering
        self._auto_parse()

    def _auto_parse(self):
        raw = self.txt_prompts.toPlainText().strip()
        default_start = self.next_scene_num if self.next_scene_num > 0 else 1
        self.parsed_scenes = PromptParser.parse_batch(raw, default_start_number=default_start)

        count = len(self.parsed_scenes)
        self.lbl_scenes_count.setText(f"Scenes Loaded: <span style='color:#38bdf8; font-weight:bold;'>{count}</span>")
        self.sig_prompts_updated.emit(self.parsed_scenes)

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Prompts File", "", "Text Files (*.txt *.md *.prompt)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.txt_prompts.setPlainText(content)
                logger.info(f"Imported prompt file: {Path(path).name}")
            except Exception as e:
                logger.error(f"Error reading file: {e}")

    def _load_sample(self):
        sample = (
            "SCENE 1: The master concept vehicle rests in a high-tech hangar, ambient lights reflecting off metallic surfaces.\n\n"
            "SCENE 2: The vehicle accelerates out into a neon-lit cyberpunk cityscape, tires gripping the rain-slicked asphalt.\n\n"
            "SCENE 3: Cybernetic wings deploy from the side panels as the vehicle lifts off gracefully over the skyscrapers."
        )
        self.txt_prompts.setPlainText(sample)

    def get_parsed_scenes(self) -> List[ScenePrompt]:
        return self.parsed_scenes
