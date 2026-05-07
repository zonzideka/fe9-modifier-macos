#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QCloseEvent, QPixmap
from PySide6.QtWidgets import QMainWindow, QMessageBox, QPushButton, QTabWidget, QHBoxLayout, QVBoxLayout
from dolphin_memory_engine import un_hook, is_hooked

from parameter import DataSetting
from structure import dme_tracking
from widget import SlotList, BackgroundFrame
from . import Status, Ability, Skill, Item, Support, Other, ItemTemplate
from .export_codes import writes_to_ar_codes
from .export_dialog import ExportDialog


class Window(QMainWindow):
    # noinspection PyTypeChecker,PyUnresolvedReferences
    def __init__(self):
        super(Window, self).__init__(parent=None, flags=Qt.WindowCloseButtonHint)
        self.slot_list = SlotList(None, PID=DataSetting()['人物'], JID=DataSetting()['职业'])
        self.slot_list.setIconSize(QSize(50, 50))
        self.slot_list.setFixedWidth(300)
        refresh_button = QPushButton('刷新列表')
        refresh_button.setFixedHeight(40)
        slot_layout = QVBoxLayout()
        slot_layout.addWidget(self.slot_list)
        slot_layout.addWidget(refresh_button)

        refresh_button.clicked.connect(self.refresh)

        status_frame = Status(self.slot_list)
        ability_frame = Ability(self.slot_list)
        skill_frame = Skill(self.slot_list)
        item_frame = Item(self.slot_list)
        support_frame = Support(self.slot_list)
        other_frame = Other(None)
        item_template_frame = ItemTemplate(None)

        self.slot_list.add_child(status_frame)
        self.slot_list.add_child(ability_frame)
        self.slot_list.add_child(skill_frame)
        self.slot_list.add_child(item_frame)
        self.slot_list.add_child(support_frame)
        self.slot_list.add_child(other_frame)
        # item_template_frame is independent of slot selection (item is global, not per-character)

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(status_frame, '状态')
        self.tab_widget.addTab(ability_frame, '能力')
        self.tab_widget.addTab(skill_frame, '技能')
        self.tab_widget.addTab(item_frame, '装备')
        self.tab_widget.addTab(support_frame, '支援')
        self.tab_widget.addTab(other_frame, '其他')
        self.tab_widget.addTab(item_template_frame, '物品模板')

        main_frame = BackgroundFrame()
        main_layout = QHBoxLayout()
        main_layout.addLayout(slot_layout)
        main_layout.addWidget(self.tab_widget)
        main_frame.setLayout(main_layout)

        self.setCentralWidget(main_frame)
        self.setWindowTitle('苍炎的轨迹 动态修改器 V1.2')
        self.setWindowIcon(QIcon(':/ICON/icon.ico'))
        self.setMinimumHeight(480)

        self._build_menu()
        self.refresh()

        # noinspection SpellCheckingInspection
        skill_frame['SID_EQUIPLIGHT'].stateChanged.connect(self.charge_light)

    def _build_menu(self):
        m = self.menuBar()
        tools = m.addMenu('工具(&T)')
        a = QAction('导出 Dolphin 代码…', self)
        a.triggered.connect(self.act_export_codes)
        tools.addAction(a)
        a = QAction('清空本次会话日志', self)
        a.triggered.connect(self.act_reset_log)
        tools.addAction(a)

    def act_export_codes(self):
        writes = dme_tracking.snapshot()
        if not writes:
            QMessageBox.information(
                self, '无可导出的修改',
                '本次会话还没有任何 RAM 写入,或所有修改都已被还原回初始值。\n\n'
                '操作流程:\n'
                '  1) 在修改器各 tab 中改字段\n'
                '  2) 再来这里导出'
            )
            return
        lines = writes_to_ar_codes(writes)
        ExportDialog(lines, len(writes), self).exec()

    def act_reset_log(self):
        res = QMessageBox.question(
            self, '清空会话日志',
            '清空目前已记录的所有 RAM 写入日志? 这不影响 RAM 中已写入的实际值,\n'
            '只是让"导出代码"重新从此刻起算。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        dme_tracking.reset()

    def refresh(self):
        self.slot_list.refresh()
        self.tab_widget.setEnabled(bool(self.slot_list.SLOT_MAPPING()))

    def charge_light(self):
        label = self.centralWidget().layout().itemAt(1).widget().widget(1).layout().itemAtPosition(8, 3).widget()
        light = 'LIGHT' if self.sender().isChecked() else 'STAFF'
        label.setPixmap(QPixmap(f':WP/WP_{light}.png'))

    def closeEvent(self, event: QCloseEvent) -> None:
        if is_hooked():
            un_hook()
        event.accept()
