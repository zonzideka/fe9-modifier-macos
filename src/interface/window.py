#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox, QPushButton,
    QStatusBar, QTabWidget, QVBoxLayout,
)
from dolphin_memory_engine import un_hook, is_hooked

from parameter import DataSetting
from parameter.address_decoder import annotate_writes
from structure import dme_tracking
from widget import SlotList, BackgroundFrame
from . import Status, Ability, Skill, Item, Support, Other, ItemTemplate
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
        self.setWindowTitle('苍炎的轨迹 动态修改器 V1.5.2')
        self.setWindowIcon(QIcon(':/ICON/icon.ico'))
        self.setMinimumHeight(480)

        self._status_label = QLabel()
        self.setStatusBar(QStatusBar())
        self.statusBar().addPermanentWidget(self._status_label, 1)

        self._build_menu()
        self.refresh()
        self._refresh_status_bar()

        # noinspection SpellCheckingInspection
        skill_frame['SID_EQUIPLIGHT'].stateChanged.connect(self.charge_light)

    def _build_menu(self):
        # keep strong refs to QMenu objects — PySide6 sometimes drops Python
        # wrappers for menu hierarchy nodes if no reachable Python ref exists.
        m = self.menuBar()
        self._tools_menu = m.addMenu('工具(&T)')

        a = QAction('导出 Dolphin 代码…', self)
        a.triggered.connect(self.act_export_codes)
        self._tools_menu.addAction(a)
        a = QAction('清空当前 profile 日志', self)
        a.triggered.connect(self.act_reset_log)
        self._tools_menu.addAction(a)
        a = QAction('清空 Dolphin INI 中本工具的代码块…', self)
        a.triggered.connect(self.act_clear_ini)
        self._tools_menu.addAction(a)

        self._tools_menu.addSeparator()

        self._profile_menu = self._tools_menu.addMenu('切换 profile')
        a = QAction('新建 profile…', self)
        a.triggered.connect(self.act_new_profile)
        self._tools_menu.addAction(a)
        a = QAction('重命名当前 profile…', self)
        a.triggered.connect(self.act_rename_profile)
        self._tools_menu.addAction(a)
        a = QAction('删除当前 profile…', self)
        a.triggered.connect(self.act_delete_profile)
        self._tools_menu.addAction(a)

        self._refresh_profile_menu()

    def _refresh_profile_menu(self):
        self._profile_menu.clear()
        cur = dme_tracking.current_profile_name()
        for name in dme_tracking.list_profiles():
            a = QAction(name, self)
            a.setCheckable(True)
            a.setChecked(name == cur)
            a.triggered.connect(lambda _checked=False, n=name: self.act_switch_profile(n))
            self._profile_menu.addAction(a)
        self._refresh_status_bar()

    def _refresh_status_bar(self):
        if not hasattr(self, '_status_label'):
            return
        cur = dme_tracking.current_profile_name()
        persistable = dme_tracking.count(persistable_only=True)
        total = dme_tracking.count(persistable_only=False)
        transient = total - persistable
        if transient:
            self._status_label.setText(
                f'profile: {cur}  |  {persistable} 处可导出  |  {transient} 处临时(本会话)'
            )
        else:
            self._status_label.setText(f'profile: {cur}  |  {persistable} 处未导出修改')

    def act_export_codes(self):
        writes = dme_tracking.snapshot(persistable_only=True)
        if not writes:
            transient = dme_tracking.count(persistable_only=False)
            extra = ''
            if transient:
                extra = (
                    f'\n\n注: 本 profile 有 {transient} 处运行时修改(角色 HP / 装备 / 行动状态等),\n'
                    '这些是 session-specific 字段,不能通过 AR 代码持久化 \n'
                    '(强制每次启动写入会让游戏崩溃,或造成 "无限行动" 等异常),\n'
                    '所以被自动排除在导出之外。'
                )
            QMessageBox.information(
                self, '无可导出的修改',
                '当前 profile 还没有可持久化的物品模板修改,或所有改动都已被还原回初始值。\n\n'
                '可导出的范围: 只有 ItemData 模板(物品攻击/特性/特效等全局参数)。'
                + extra
            )
            return
        annotated = annotate_writes(writes)
        ExportDialog(annotated, profile_name=dme_tracking.current_profile_name(), parent=self).exec()
        self._refresh_status_bar()

    def act_clear_ini(self):
        from .export_codes import CHEAT_NAME, clear_dolphin_ini, gamesettings_dir, GAME_ID
        import os
        path = os.path.join(gamesettings_dir(), f'{GAME_ID}.ini')
        res = QMessageBox.question(
            self, '清空 Dolphin INI',
            f'从以下文件中删除本工具自动生成的 cheat 块({CHEAT_NAME!r}):\n{path}\n\n'
            '其他 cheat 不受影响。继续?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        try:
            cleared = clear_dolphin_ini()
        except Exception as e:
            QMessageBox.critical(self, '清空失败', f'{type(e).__name__}: {e}')
            return
        if not os.path.exists(cleared):
            QMessageBox.information(self, '无需清空', f'{cleared}\n该 INI 文件不存在,无需清理。')
        else:
            QMessageBox.information(
                self, '已清空',
                f'已从 {cleared} 中移除本工具的 cheat 块。\n\n'
                '重启 Dolphin / 重新加载游戏以让改动生效。'
            )

    def act_reset_log(self):
        res = QMessageBox.question(
            self, '清空当前 profile 日志',
            f'清空 profile {dme_tracking.current_profile_name()!r} 的所有 RAM 写入日志? \n'
            '这不影响 RAM 中已写入的实际值,只是让"导出代码"重新从此刻起算。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        dme_tracking.reset()
        self._refresh_status_bar()

    def act_switch_profile(self, name: str):
        try:
            dme_tracking.set_current_profile(name)
        except Exception as e:
            QMessageBox.critical(self, '切换失败', str(e))
            return
        self._refresh_profile_menu()

    def act_new_profile(self):
        name, ok = QInputDialog.getText(self, '新建 profile', '名称:')
        if not ok or not name.strip():
            return
        try:
            dme_tracking.new_profile(name.strip())
        except Exception as e:
            QMessageBox.critical(self, '新建失败', str(e))
            return
        self._refresh_profile_menu()

    def act_rename_profile(self):
        cur = dme_tracking.current_profile_name()
        new, ok = QInputDialog.getText(self, '重命名', f'重命名 profile {cur!r} 为:', text=cur)
        if not ok or not new.strip() or new.strip() == cur:
            return
        try:
            dme_tracking.rename_profile(cur, new.strip())
        except Exception as e:
            QMessageBox.critical(self, '重命名失败', str(e))
            return
        self._refresh_profile_menu()

    def act_delete_profile(self):
        cur = dme_tracking.current_profile_name()
        res = QMessageBox.question(
            self, '删除 profile',
            f'删除 profile {cur!r}? 该 profile 中所有未导出的修改记录将丢失。\n'
            '这不影响已写入 INI 的代码或 RAM 中已生效的值。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        try:
            dme_tracking.delete_profile(cur)
        except Exception as e:
            QMessageBox.critical(self, '删除失败', str(e))
            return
        self._refresh_profile_menu()

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
