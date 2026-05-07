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
    """Show the codes derived from this session's annotated writes, with
    options to write them to Dolphin's GameSettings INI or copy them.

    Annotated writes are 4-tuples (addr, value_bytes, baseline_bytes, label)
    produced by parameter.address_decoder.annotate_writes()."""

    def __init__(self, annotated_writes: list, profile_name: str = '', parent=None):
        super().__init__(parent)
        title = '导出 Dolphin 代码'
        if profile_name:
            title += f' — {profile_name}'
        self.setWindowTitle(title)
        self.resize(760, 540)
        self.annotated_writes = annotated_writes

        preview_lines = export_codes.writes_to_ar_codes(annotated_writes, include_comments=True)
        self._copy_payload = '\n'.join(preview_lines)

        code_only = export_codes.writes_to_ar_codes(annotated_writes, include_comments=False)
        write_count = len(annotated_writes)

        layout = QVBoxLayout(self)

        info = QLabel(
            f'本次会话累计 {write_count} 处写入,生成 {len(code_only)} 行 AR 代码 (注释行不计入)。\n'
            '写入 Dolphin GameSettings INI 后:\n'
            '  1) 在 Dolphin → Config → General 启用 "Enable Cheats"\n'
            '  2) 重启游戏 (重新加载 GCM)\n'
            '代码会自动应用,无需每次都打开修改器。\n'
            '注释行 (# …) 仅供本预览阅读,不写入 INI;Dolphin 用 "*description" 行展示总结。'
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        font = QFont('Menlo')
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(font)
        self.text.setPlainText(self._copy_payload)
        layout.addWidget(self.text)

        bar = QHBoxLayout()
        b_ini = QPushButton('写入 Dolphin INI')
        b_ini.clicked.connect(self.act_write_ini)
        b_copy = QPushButton('复制 (含注释)')
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
            path = export_codes.write_to_dolphin_ini(self.annotated_writes)
        except Exception as e:
            QMessageBox.critical(self, '写入失败', f'{type(e).__name__}: {e}')
            return
        QMessageBox.information(
            self, '已写入',
            f'已写入:\n{path}\n\n下次启动游戏时,代码会自动应用 (需在 Dolphin 设置中启用 Cheats)。'
        )

    def act_copy(self):
        QApplication.clipboard().setText(self._copy_payload)
        QMessageBox.information(self, '已复制', f'代码 (含注释) 已复制到剪贴板。')
