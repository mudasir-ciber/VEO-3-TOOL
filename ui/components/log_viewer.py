"""Real-time activity log viewer with color highlighting."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QGroupBox
)
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Qt, Slot


class LogViewerWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("4. REAL-TIME ACTIVITY LOG", parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Log Text Area
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(
            "background-color: #0b0c10; font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 12px; line-height: 1.4; border: 1px solid #232738; border-radius: 6px;"
        )
        layout.addWidget(self.txt_log)

        # Bottom Bar
        h_bar = QHBoxLayout()
        btn_clear = QPushButton("Clear Log")
        btn_clear.clicked.connect(self.txt_log.clear)

        self.lbl_log_count = QLabel("Log entries: 0")
        self.lbl_log_count.setStyleSheet("color: #64748b; font-size: 11px;")
        self.entry_count = 0

        h_bar.addWidget(self.lbl_log_count)
        h_bar.addStretch()
        h_bar.addWidget(btn_clear)
        layout.addLayout(h_bar)

    @Slot(str, str, str)
    def append_log(self, timestamp: str, level: str, message: str):
        color = "#94a3b8"  # default info
        lvl_upper = level.upper()

        if lvl_upper == "SUCCESS":
            color = "#34d399"  # emerald green
        elif lvl_upper == "WARNING":
            color = "#fbbf24"  # amber
        elif lvl_upper == "ERROR":
            color = "#f87171"  # red
        elif lvl_upper == "DEBUG":
            color = "#64748b"  # muted slate

        html_entry = f"<div style='margin-bottom:2px;'><span style='color:#64748b;'>[{timestamp}]</span> <b style='color:{color};'>[{lvl_upper}]</b> <span style='color:#e2e8f0;'>{message}</span></div>"

        self.txt_log.append(html_entry)
        self.txt_log.moveCursor(QTextCursor.End)

        self.entry_count += 1
        self.lbl_log_count.setText(f"Log entries: {self.entry_count}")
