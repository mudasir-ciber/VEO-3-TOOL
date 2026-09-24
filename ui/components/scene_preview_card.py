"""Scene Preview and Stepper Card matching the provided mockup layout."""
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QProgressBar, QFrame
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt


class VerticalStepItem(QWidget):
    def __init__(self, step_name: str, parent=None):
        super().__init__(parent)
        self.step_name = step_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.lbl_dot = QLabel("○")
        self.lbl_dot.setFixedSize(16, 16)
        self.lbl_dot.setAlignment(Qt.AlignCenter)
        self.lbl_dot.setStyleSheet("color: #475569; font-size: 13px; font-weight: bold;")

        self.lbl_name = QLabel(step_name)
        self.lbl_name.setStyleSheet("font-size: 12px; font-weight: 500; color: #94a3b8;")

        self.lbl_status = QLabel("Pending")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #64748b;")

        layout.addWidget(self.lbl_dot)
        layout.addWidget(self.lbl_name)
        layout.addStretch()
        layout.addWidget(self.lbl_status)

    def set_state(self, state: str):
        # state: WAITING, ACTIVE, COMPLETE, FAILED
        st = state.upper()
        if st in ("COMPLETE", "DONE", "READY", "VERIFIED"):
            self.lbl_dot.setText("✔")
            self.lbl_dot.setStyleSheet("color: #10b981; font-size: 12px; font-weight: bold;")
            self.lbl_name.setStyleSheet("font-size: 12px; font-weight: 600; color: #f1f5f9;")
            self.lbl_status.setText("Completed")
            self.lbl_status.setStyleSheet("font-size: 11px; color: #10b981; font-weight: 600;")
        elif st in ("ACTIVE", "GENERATING", "DOWNLOADING", "EXTRACTING", "UPLOADING"):
            self.lbl_dot.setText("✦")
            self.lbl_dot.setStyleSheet("color: #3b82f6; font-size: 13px; font-weight: bold;")
            self.lbl_name.setStyleSheet("font-size: 12px; font-weight: 700; color: #ffffff;")
            self.lbl_status.setText("In Progress...")
            self.lbl_status.setStyleSheet("font-size: 11px; color: #3b82f6; font-weight: 600;")
        elif st in ("FAILED", "ERROR"):
            self.lbl_dot.setText("✖")
            self.lbl_dot.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: bold;")
            self.lbl_status.setText("Failed")
            self.lbl_status.setStyleSheet("font-size: 11px; color: #ef4444; font-weight: 600;")
        else:
            self.lbl_dot.setText("○")
            self.lbl_dot.setStyleSheet("color: #475569; font-size: 13px; font-weight: bold;")
            self.lbl_name.setStyleSheet("font-size: 12px; font-weight: 500; color: #94a3b8;")
            self.lbl_status.setText("Pending")
            self.lbl_status.setStyleSheet("font-size: 11px; color: #64748b;")


class ScenePreviewCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("scenePreviewCard")
        self.setStyleSheet("""
            #scenePreviewCard {
                background-color: #10141f;
                border: 1px solid #1e2638;
                border-radius: 12px;
                padding: 14px;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # 1. Preview Container (Display + Vertical Stepper overlay)
        self.frame_stage = QFrame()
        self.frame_stage.setStyleSheet("background-color: #0b0e17; border: 1px solid #1e2638; border-radius: 10px;")
        h_stage = QHBoxLayout(self.frame_stage)
        h_stage.setContentsMargins(10, 10, 10, 10)
        h_stage.setSpacing(14)

        # Main Media Display
        self.lbl_main_preview = QLabel()
        self.lbl_main_preview.setMinimumSize(320, 210)
        self.lbl_main_preview.setAlignment(Qt.AlignCenter)
        self.lbl_main_preview.setStyleSheet("background-color: #080a10; border-radius: 8px; border: 1px dashed #242c40;")
        self.lbl_main_preview.setText("🎬 Video Generation Preview Stage\n(Upload Master Image to Begin)")
        h_stage.addWidget(self.lbl_main_preview, stretch=3)

        # Right Stepper Column
        v_stepper = QVBoxLayout()
        v_stepper.setContentsMargins(4, 0, 4, 0)
        v_stepper.setSpacing(6)

        # Scene Counter Header e.g. "Scene 3 / 10"
        self.lbl_scene_counter = QLabel("Scene 0 / 0")
        self.lbl_scene_counter.setAlignment(Qt.AlignRight)
        self.lbl_scene_counter.setStyleSheet("font-size: 15px; font-weight: 800; color: #3b82f6;")
        v_stepper.addWidget(self.lbl_scene_counter)

        # Stepper items
        self.step_ref = VerticalStepItem("Reference Uploaded")
        self.step_prompt = VerticalStepItem("Prompt Submitted")
        self.step_gen = VerticalStepItem("Generating Video")
        self.step_dl = VerticalStepItem("Downloading Video")
        self.step_frame = VerticalStepItem("Extracting Last Frame")
        self.step_next = VerticalStepItem("Preparing Next Scene")

        v_stepper.addWidget(self.step_ref)
        v_stepper.addWidget(self.step_prompt)
        v_stepper.addWidget(self.step_gen)
        v_stepper.addWidget(self.step_dl)
        v_stepper.addWidget(self.step_frame)
        v_stepper.addWidget(self.step_next)
        v_stepper.addStretch()

        h_stage.addLayout(v_stepper, stretch=2)
        layout.addWidget(self.frame_stage)

        # 2. Scene Progress Bar Section
        v_prog = QVBoxLayout()
        v_prog.setSpacing(4)
        h_prog_header = QHBoxLayout()
        lbl_prog_title = QLabel("Scene Progress")
        lbl_prog_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #f1f5f9;")
        self.lbl_pct = QLabel("0%")
        self.lbl_pct.setStyleSheet("font-size: 12px; font-weight: 700; color: #3b82f6;")
        h_prog_header.addWidget(lbl_prog_title)
        h_prog_header.addStretch()
        h_prog_header.addWidget(self.lbl_pct)
        v_prog.addLayout(h_prog_header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #161c2a;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
        """)
        v_prog.addWidget(self.progress_bar)

        self.lbl_status_desc = QLabel("Ready to run batch evolution.")
        self.lbl_status_desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        v_prog.addWidget(self.lbl_status_desc)
        layout.addLayout(v_prog)

        # 3. Bottom Mini Cards (Last Completed Scene & Next Reference)
        h_cards = QHBoxLayout()
        h_cards.setSpacing(12)

        # Mini Card 1: Last Completed Scene
        self.card_last_comp = QFrame()
        self.card_last_comp.setStyleSheet("background-color: #121826; border: 1px solid #1e2638; border-radius: 8px; padding: 6px;")
        h_c1 = QHBoxLayout(self.card_last_comp)
        h_c1.setContentsMargins(6, 6, 6, 6)
        h_c1.setSpacing(10)

        self.lbl_thumb_last = QLabel()
        self.lbl_thumb_last.setFixedSize(56, 42)
        self.lbl_thumb_last.setStyleSheet("background-color: #0b0e14; border-radius: 4px;")
        self.lbl_thumb_last.setAlignment(Qt.AlignCenter)
        self.lbl_thumb_last.setText("None")

        v_c1_info = QVBoxLayout()
        v_c1_info.setSpacing(2)
        lbl_c1_title = QLabel("Last Completed Scene")
        lbl_c1_title.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.lbl_last_scene_name = QLabel("None")
        self.lbl_last_scene_name.setStyleSheet("font-size: 12px; font-weight: 700; color: #ffffff;")
        self.pill_completed = QLabel("Pending")
        self.pill_completed.setStyleSheet("background-color: #1e293b; color: #94a3b8; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        self.pill_completed.setFixedWidth(75)
        self.pill_completed.setAlignment(Qt.AlignCenter)

        v_c1_info.addWidget(lbl_c1_title)
        v_c1_info.addWidget(self.lbl_last_scene_name)
        v_c1_info.addWidget(self.pill_completed)

        h_c1.addWidget(self.lbl_thumb_last)
        h_c1.addLayout(v_c1_info)
        h_cards.addWidget(self.card_last_comp)

        # Mini Card 2: Next Reference
        self.card_next_ref = QFrame()
        self.card_next_ref.setStyleSheet("background-color: #121826; border: 1px solid #1e2638; border-radius: 8px; padding: 6px;")
        h_c2 = QHBoxLayout(self.card_next_ref)
        h_c2.setContentsMargins(6, 6, 6, 6)
        h_c2.setSpacing(10)

        self.lbl_thumb_ref = QLabel()
        self.lbl_thumb_ref.setFixedSize(56, 42)
        self.lbl_thumb_ref.setStyleSheet("background-color: #0b0e14; border-radius: 4px;")
        self.lbl_thumb_ref.setAlignment(Qt.AlignCenter)
        self.lbl_thumb_ref.setText("None")

        v_c2_info = QVBoxLayout()
        v_c2_info.setSpacing(2)
        lbl_c2_title = QLabel("Next Reference")
        lbl_c2_title.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.lbl_next_ref_name = QLabel("Master Image")
        self.lbl_next_ref_name.setStyleSheet("font-size: 12px; font-weight: 700; color: #ffffff;")
        self.pill_ready = QLabel("Ready")
        self.pill_ready.setStyleSheet("background-color: #172554; color: #60a5fa; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        self.pill_ready.setFixedWidth(60)
        self.pill_ready.setAlignment(Qt.AlignCenter)

        v_c2_info.addWidget(lbl_c2_title)
        v_c2_info.addWidget(self.lbl_next_ref_name)
        v_c2_info.addWidget(self.pill_ready)

        h_c2.addWidget(self.lbl_thumb_ref)
        h_c2.addLayout(v_c2_info)
        h_cards.addWidget(self.card_next_ref)

        layout.addLayout(h_cards)

    def set_preview_image(self, img_path: Path):
        p = Path(img_path).resolve()
        if p.is_file():
            pix = QPixmap(str(p))
            if not pix.isNull():
                scaled = pix.scaled(self.lbl_main_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_main_preview.setPixmap(scaled)

    def set_scene_status(self, scene_num: int, total_scenes: int, completed: int):
        self.lbl_scene_counter.setText(f"Scene {scene_num} / {total_scenes}")
        if total_scenes > 0:
            pct = int((completed / total_scenes) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_pct.setText(f"{pct}%")
        self.reset_steps()

    def update_step(self, step_name: str, state: str):
        s_lower = step_name.lower()
        if "reference" in s_lower:
            self.step_ref.set_state(state)
        elif "prompt" in s_lower:
            self.step_prompt.set_state(state)
        elif "generation" in s_lower:
            self.step_gen.set_state(state)
            if state == "ACTIVE":
                self.lbl_status_desc.setText("Generating your video... this may take a few minutes.")
        elif "download" in s_lower:
            self.step_dl.set_state(state)
            if state == "ACTIVE":
                self.lbl_status_desc.setText("Downloading completed video...")
        elif "frame" in s_lower:
            self.step_frame.set_state(state)
            if state == "ACTIVE":
                self.lbl_status_desc.setText("Extracting exact final decoded video frame (FFmpeg)...")
        elif "next" in s_lower or "unlock" in s_lower:
            self.step_next.set_state(state)

    def reset_steps(self):
        for s in [self.step_ref, self.step_prompt, self.step_gen, self.step_dl, self.step_frame, self.step_next]:
            s.set_state("WAITING")

    def update_bottom_cards(self, last_completed_scene: int, last_completed_thumb: Optional[Path], current_ref_name: str, current_ref_thumb: Optional[Path]):
        if last_completed_scene > 0:
            self.lbl_last_scene_name.setText(f"Scene {last_completed_scene}")
            self.pill_completed.setText("✓ Completed")
            self.pill_completed.setStyleSheet("background-color: #064e3b; color: #34d399; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
            if last_completed_thumb and last_completed_thumb.is_file():
                pix = QPixmap(str(last_completed_thumb)).scaled(56, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_thumb_last.setPixmap(pix)
        else:
            self.lbl_last_scene_name.setText("None")
            self.pill_completed.setText("Pending")

        self.lbl_next_ref_name.setText(current_ref_name)
        if current_ref_thumb and current_ref_thumb.is_file():
            pix2 = QPixmap(str(current_ref_thumb)).scaled(56, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_thumb_ref.setPixmap(pix2)
            self.pill_ready.setText("Ready")
            self.pill_ready.setStyleSheet("background-color: #172554; color: #60a5fa; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
