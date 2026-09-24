"""Control bar containing RUN, PAUSE, RESUME, STOP, and simulation toggle."""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QCheckBox, QLabel, QFrame
)
from PySide6.QtCore import Signal


class ControlBarWidget(QFrame):
    sig_run_clicked = Signal()
    sig_pause_clicked = Signal()
    sig_resume_clicked = Signal()
    sig_stop_clicked = Signal()
    sig_settings_clicked = Signal()
    sig_sim_mode_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #161824; border: 1px solid #2d3348; border-radius: 8px; padding: 6px;")
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        # Primary RUN button
        self.btn_run = QPushButton("▶  RUN BATCH")
        self.btn_run.setObjectName("primaryButton")
        self.btn_run.setFixedHeight(38)
        self.btn_run.clicked.connect(self.sig_run_clicked.emit)

        # PAUSE
        self.btn_pause = QPushButton("⏸  PAUSE")
        self.btn_pause.setObjectName("pauseButton")
        self.btn_pause.setFixedHeight(38)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.sig_pause_clicked.emit)

        # RESUME
        self.btn_resume = QPushButton("⏯  RESUME")
        self.btn_resume.setFixedHeight(38)
        self.btn_resume.setEnabled(False)
        self.btn_resume.clicked.connect(self.sig_resume_clicked.emit)

        # STOP
        self.btn_stop = QPushButton("⏹  STOP")
        self.btn_stop.setObjectName("stopButton")
        self.btn_stop.setFixedHeight(38)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.sig_stop_clicked.emit)

        # Simulation Mode Toggle
        self.chk_simulation = QCheckBox("Simulation / Dry-Run Mode")
        self.chk_simulation.setToolTip("Test batch logic, FFmpeg, and frame handoffs with simulated video generator")
        self.chk_simulation.toggled.connect(self.sig_sim_mode_toggled.emit)

        # Settings Button
        self.btn_settings = QPushButton("⚙  Settings")
        self.btn_settings.setFixedHeight(38)
        self.btn_settings.clicked.connect(self.sig_settings_clicked.emit)

        layout.addWidget(self.btn_run)
        layout.addWidget(self.btn_pause)
        layout.addWidget(self.btn_resume)
        layout.addWidget(self.btn_stop)
        layout.addSpacing(16)
        layout.addWidget(self.chk_simulation)
        layout.addStretch()
        layout.addWidget(self.btn_settings)

    def set_running_state(self, is_running: bool, is_paused: bool = False):
        """Update button enabled states dynamically."""
        if is_running:
            self.btn_run.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.chk_simulation.setEnabled(False)
            if is_paused:
                self.btn_pause.setEnabled(False)
                self.btn_resume.setEnabled(True)
            else:
                self.btn_pause.setEnabled(True)
                self.btn_resume.setEnabled(False)
        else:
            self.btn_run.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_resume.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.chk_simulation.setEnabled(True)
