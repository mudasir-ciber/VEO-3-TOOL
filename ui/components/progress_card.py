"""Progress Card component displaying real-time sub-step badges and scene progress."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QProgressBar, QGroupBox, QFrame
)
from PySide6.QtCore import Qt


class StepPill(QFrame):
    """Visual badge for individual sub-step lifecycle."""
    def __init__(self, step_name: str, parent=None):
        super().__init__(parent)
        self.step_name = step_name
        self.setStyleSheet("background-color: #141620; border: 1px solid #2d3348; border-radius: 6px; padding: 6px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.lbl_name = QLabel(step_name)
        self.lbl_name.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")
        self.lbl_name.setAlignment(Qt.AlignCenter)

        self.lbl_status = QLabel("WAITING")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b;")
        self.lbl_status.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_status)

    def set_status(self, status: str):
        """
        Status: WAITING, ACTIVE, COMPLETE, FAILED
        """
        status_upper = status.upper()
        self.lbl_status.setText(status_upper)

        if status_upper in ("ACTIVE", "GENERATING", "DOWNLOADING", "EXTRACTING", "UPLOADING"):
            self.setStyleSheet("background-color: #1e1b4b; border: 1px solid #6366f1; border-radius: 6px; padding: 6px;")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #818cf8;")
        elif status_upper in ("COMPLETE", "READY", "VERIFIED"):
            self.setStyleSheet("background-color: #064e3b; border: 1px solid #10b981; border-radius: 6px; padding: 6px;")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #34d399;")
        elif status_upper in ("FAILED", "ERROR"):
            self.setStyleSheet("background-color: #450a0a; border: 1px solid #ef4444; border-radius: 6px; padding: 6px;")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #f87171;")
        else:
            self.setStyleSheet("background-color: #141620; border: 1px solid #2d3348; border-radius: 6px; padding: 6px;")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b;")


class ProgressCardWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("3. CURRENT SCENE & STEP PROGRESSION", parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header: Current Scene Counter
        h_head = QHBoxLayout()
        self.lbl_current_scene = QLabel("CURRENT SCENE: <b>IDLE (Ready to run)</b>")
        self.lbl_current_scene.setStyleSheet("font-size: 14px; color: #f1f5f9;")
        h_head.addWidget(self.lbl_current_scene)
        h_head.addStretch()

        self.lbl_batch_counter = QLabel("Batch Progress: 0 / 0")
        self.lbl_batch_counter.setStyleSheet("font-size: 13px; font-weight: 600; color: #38bdf8;")
        h_head.addWidget(self.lbl_batch_counter)
        layout.addLayout(h_head)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v% Completed")
        layout.addWidget(self.progress_bar)

        # 5 Sub-step Lifecycle Pills
        h_pills = QHBoxLayout()
        h_pills.setSpacing(8)

        self.pill_ref = StepPill("Reference Upload")
        self.pill_gen = StepPill("Video Generation")
        self.pill_dl = StepPill("Video Download")
        self.pill_verify = StepPill("Video Verification")
        self.pill_frame = StepPill("Last Frame Extract")

        h_pills.addWidget(self.pill_ref)
        h_pills.addWidget(self.pill_gen)
        h_pills.addWidget(self.pill_dl)
        h_pills.addWidget(self.pill_verify)
        h_pills.addWidget(self.pill_frame)

        layout.addLayout(h_pills)

    def set_current_scene(self, scene_num: int, total_scenes: int, completed_so_far: int):
        self.lbl_current_scene.setText(f"CURRENT SCENE: <b style='color:#a5b4fc;'>Scene {scene_num}</b> (Step {completed_so_far + 1} of {total_scenes})")
        self.lbl_batch_counter.setText(f"Batch Progress: {completed_so_far} / {total_scenes}")
        if total_scenes > 0:
            pct = int((completed_so_far / total_scenes) * 100)
            self.progress_bar.setValue(pct)

        # Reset pills to waiting
        self.reset_pills()

    def update_substep(self, step_name: str, status: str):
        name_lower = step_name.lower()
        if "reference" in name_lower:
            self.pill_ref.set_status(status)
        elif "generation" in name_lower:
            self.pill_gen.set_status(status)
        elif "download" in name_lower:
            self.pill_dl.set_status(status)
        elif "verification" in name_lower:
            self.pill_verify.set_status(status)
        elif "frame" in name_lower:
            self.pill_frame.set_status(status)

    def reset_pills(self):
        for pill in [self.pill_ref, self.pill_gen, self.pill_dl, self.pill_verify, self.pill_frame]:
            pill.set_status("WAITING")

    def mark_completed_all(self, total: int):
        self.lbl_current_scene.setText(f"CURRENT SCENE: <b style='color:#34d399;'>BATCH FINISHED ({total}/{total})</b>")
        self.lbl_batch_counter.setText(f"Batch Progress: {total} / {total}")
        self.progress_bar.setValue(100)
        for pill in [self.pill_ref, self.pill_gen, self.pill_dl, self.pill_verify, self.pill_frame]:
            pill.set_status("COMPLETE")
