#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Dialog showing AR codes derived from this session's RAM writes, with
options to write them to Dolphin's GameSettings INI or copy them to the
clipboard."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout,
)

from . import export_codes


class ExportDialog(QDialog):
    def __init__(self, ar_lines: list, write_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle('导出 Dolphin 代码')
        self.resize(720, 520)
        self.ar_lines = ar_lines

        layout = QVBoxLayout(self)

        info = QLabel(
            f'本次会话累计 {write_count} 处写入,生成 {len(ar_lines)} 行 AR 代码。\n'
            '写入 Dolphin GameSettings INI 后,需:\n'
            '  1) 在 Dolphin → Config → General 启用 "Enable Cheats"\n'
            '  2) 重启游戏 (重新加载 GCM)\n'
            '代码会自动应用,无需每次都打开修改器。'
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        font = QFont('Menlo')
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(font)
        self.text.setPlainText('\n'.join(ar_lines))
        layout.addWidget(self.text)

        bar = QHBoxLayout()
        b_ini = QPushButton('写入 Dolphin INI')
        b_ini.clicked.connect(self.act_write_ini)
        b_copy = QPushButton('复制到剪贴板')
        b_copy.clicked.connect(self.act_copy)
        b_close = QPushButton('关闭')
        b_close.clicked.connect(self.accept)
        bar.addWidget(b_ini)
        bar.addWidget(b_copy)
        bar.addStretch()
        bar.addWidget(b_close)
        layout.addLayout(bar)

    def act_write_ini(self):
        try:
            path = export_codes.write_to_dolphin_ini(self.ar_lines)
        except Exception as e:
            QMessageBox.critical(self, '写入失败', f'{type(e).__name__}: {e}')
            return
        QMessageBox.information(
            self, '已写入',
            f'已写入:\n{path}\n\n下次启动游戏时,代码会自动应用 (需在 Dolphin 设置中启用 Cheats)。'
        )

    def act_copy(self):
        QApplication.clipboard().setText('\n'.join(self.ar_lines))
        QMessageBox.information(self, '已复制', f'{len(self.ar_lines)} 行 AR 代码已复制到剪贴板。')
