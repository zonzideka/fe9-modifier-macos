#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List, Dict

from parameter import DataSetting
from structure import Value


class Customize:
    def __init__(self, parent=None, **kwargs):
        # Tolerate cooperative-MRO calls from PySide6 6.x base classes that may invoke
        # super().__init__() without forwarding `parent` *during* the C++ QWidget init.
        # We run the meaningful setup only when called explicitly with the kwargs payload.
        if not hasattr(self, '_offset'):
            self._offset = 0x0
        if parent is not None or not hasattr(self, '_parent'):
            self._parent = parent
        if kwargs:
            self.structure: Dict[str, Value] = {key: Value(self, *setting) for key, setting in kwargs.items()}
        elif not hasattr(self, 'structure'):
            self.structure = {}
        # Only call Qt widget methods when this is the explicit user-initiated call
        # (kwargs present), and the C++ side is initialised. Skip during cooperative
        # super-chain calls from QWidget.__init__.
        if kwargs and hasattr(self, 'setMinimumHeight'):
            try:
                self.setMinimumHeight(30)
            except (RuntimeError, TypeError):
                pass

    def sequence(self, name: str) -> List[int]:
        return [self.structure[name].get(self.offset + DataSetting.STEP * idx) for idx in range(DataSetting.COUNT)]

    def set_parent(self, parent):
        self._parent = parent

    @property
    def offset(self) -> int:
        if isinstance(self._parent, Customize):
            return self._offset + self._parent.offset
        return self._offset

    @offset.setter
    def offset(self, offset: int):
        self._offset = offset
        self.refresh()

    def refresh(self):
        pass

    def rewrite(self):
        pass
