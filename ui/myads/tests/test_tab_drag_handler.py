"""单元测试：tab_drag_handler 的 hit_test 与 execute_drop_action 正确性。"""

import sys
import os
from unittest.mock import Mock, MagicMock

import pytest
from pathlib import Path

root_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root_dir))

from PySide6.QtCore import QPoint, QRect, Qt

from ui.demo.tab_drag_handler import (
    DropZone,
    hit_test,
    execute_drop_action,
)
from ui.demo.pane_widget import MIME_TYPE_TAB


class TestHitTest:
    """hit_test(pane_rect, pos) 区域与边界。"""

    def test_invalid_rect_zero_size(self):
        """width 或 height <= 0 时返回 CENTER。"""
        rect_w0 = QRect(0, 0, 0, 100)
        rect_h0 = QRect(0, 0, 100, 0)
        rect_both = QRect(0, 0, 0, 0)
        pos = QPoint(50, 50)
        assert hit_test(rect_w0, pos) == DropZone.CENTER
        assert hit_test(rect_h0, pos) == DropZone.CENTER
        assert hit_test(rect_both, pos) == DropZone.CENTER

    def test_top_zone(self):
        """上 25% 返回 TOP（与中心 50%×50% 一致）。"""
        r = QRect(0, 0, 100, 100)
        assert hit_test(r, QPoint(10, 0)) == DropZone.TOP
        assert hit_test(r, QPoint(50, 24)) == DropZone.TOP

    def test_bottom_zone(self):
        """下 25% 返回 BOTTOM。"""
        r = QRect(0, 0, 100, 100)
        assert hit_test(r, QPoint(50, 75)) == DropZone.BOTTOM
        assert hit_test(r, QPoint(50, 99)) == DropZone.BOTTOM

    def test_left_zone(self):
        """左 25% 返回 LEFT。"""
        r = QRect(0, 0, 100, 100)
        assert hit_test(r, QPoint(0, 50)) == DropZone.LEFT
        assert hit_test(r, QPoint(24, 50)) == DropZone.LEFT

    def test_right_zone(self):
        """右 25% 返回 RIGHT。"""
        r = QRect(0, 0, 100, 100)
        assert hit_test(r, QPoint(75, 50)) == DropZone.RIGHT
        assert hit_test(r, QPoint(99, 50)) == DropZone.RIGHT

    def test_center_zone(self):
        """中间 50%×50% 返回 CENTER。"""
        r = QRect(0, 0, 100, 100)
        assert hit_test(r, QPoint(25, 25)) == DropZone.CENTER
        assert hit_test(r, QPoint(50, 50)) == DropZone.CENTER
        assert hit_test(r, QPoint(74, 74)) == DropZone.CENTER

    def test_boundary_edges(self):
        """恰好在 0.25/0.75 边界：x=25 或 y=25 为 CENTER，x=75 或 y=75 为 RIGHT/BOTTOM。"""
        r = QRect(0, 0, 100, 100)
        assert hit_test(r, QPoint(25, 50)) == DropZone.CENTER
        assert hit_test(r, QPoint(50, 25)) == DropZone.CENTER
        assert hit_test(r, QPoint(75, 50)) == DropZone.RIGHT
        assert hit_test(r, QPoint(50, 75)) == DropZone.BOTTOM


class TestExecuteDropAction:
    """execute_drop_action 的各类分支与合并/拆分行为。"""

    def _make_mock_event(self, has_mime=True, mime_payload=None):
        if mime_payload is None:
            mime_payload = "cid\nsource-pane\nTitle".encode("utf-8")
        mime = Mock()
        mime.hasFormat = Mock(return_value=has_mime)
        mime.data = Mock(return_value=mime_payload)
        event = Mock()
        event.mimeData = Mock(return_value=mime)
        event.acceptProposedAction = Mock()
        return event

    def _make_mock_pane(
        self, get_content_widget_result=MagicMock(), get_icon_result=None
    ):
        pane = Mock()
        pane.get_content_widget = Mock(return_value=get_content_widget_result)
        pane.get_icon_for_content = Mock(return_value=get_icon_result)
        return pane

    def test_pane_none_returns_false(self):
        """pane 为 None 时返回 False。"""
        layout_tree = Mock()
        event = self._make_mock_event()
        result = execute_drop_action(
            layout_tree, Mock(), Mock(), None, None, DropZone.CENTER, event
        )
        assert result is False

    def test_zone_none_returns_false(self):
        """zone 为 None 时返回 False。"""
        pane = self._make_mock_pane()
        event = self._make_mock_event()
        result = execute_drop_action(Mock(), Mock(), Mock(), None, pane, None, event)
        assert result is False

    def test_no_mime_returns_false(self):
        """无 MIME_TYPE_TAB 时返回 False。"""
        pane = self._make_mock_pane()
        event = self._make_mock_event(has_mime=False)
        result = execute_drop_action(
            Mock(), Mock(), Mock(), None, pane, DropZone.CENTER, event
        )
        assert result is False

    def test_mime_insufficient_returns_false(self):
        """MIME 不足 3 行返回 False。"""
        pane = self._make_mock_pane()
        payload = "id1\npane1".encode("utf-8")
        event = self._make_mock_event(mime_payload=payload)
        result = execute_drop_action(
            Mock(), Mock(), Mock(), None, pane, DropZone.CENTER, event
        )
        assert result is False

    def test_source_pane_not_found_returns_false(self):
        """find_pane_by_id 返回 None 则返回 False。"""
        find_pane = Mock(return_value=None)
        pane = self._make_mock_pane()
        event = self._make_mock_event()
        result = execute_drop_action(
            Mock(), Mock(), find_pane, None, pane, DropZone.CENTER, event
        )
        assert result is False

    def test_source_equals_target_center_returns_false(self):
        """CENTER 且 source_pane == pane（同窗格合并到自己）返回 False。"""
        pane = self._make_mock_pane()
        find_pane = Mock(return_value=pane)
        event = self._make_mock_event()
        result = execute_drop_action(
            Mock(), Mock(), find_pane, None, pane, DropZone.CENTER, event
        )
        assert result is False

    def test_widget_not_found_returns_false(self):
        """get_content_widget 返回 None 则返回 False。"""
        source_pane = self._make_mock_pane(get_content_widget_result=None)
        target_pane = self._make_mock_pane()
        find_pane = Mock(return_value=source_pane)
        event = self._make_mock_event()
        result = execute_drop_action(
            Mock(), Mock(), find_pane, None, target_pane, DropZone.CENTER, event
        )
        assert result is False

    def test_center_merge_calls_remove_and_add_no_split(self):
        """CENTER：source remove、pane add，不调用 new_pane_factory/split。"""
        widget = Mock()
        source_pane = self._make_mock_pane(get_content_widget_result=widget)
        target_pane = self._make_mock_pane()
        find_pane = Mock(return_value=source_pane)
        layout_tree = Mock()
        new_pane_factory = Mock()
        event = self._make_mock_event()
        result = execute_drop_action(
            layout_tree,
            new_pane_factory,
            find_pane,
            None,
            target_pane,
            DropZone.CENTER,
            event,
        )
        assert result is True
        source_pane.remove_content.assert_called_once_with("cid")
        target_pane.add_content.assert_called_once_with(
            "cid", "Title", widget, icon=None
        )
        new_pane_factory.assert_not_called()
        layout_tree.split.assert_not_called()

    def test_top_splits_vertical_insert_before(self):
        """TOP：new_pane、split(Vertical, insert_before=True)、add 到 new_pane、remove。"""
        widget = Mock()
        source_pane = self._make_mock_pane(get_content_widget_result=widget)
        target_pane = self._make_mock_pane()
        new_pane = self._make_mock_pane()
        find_pane = Mock(return_value=source_pane)
        new_pane_factory = Mock(return_value=new_pane)
        layout_tree = Mock()
        event = self._make_mock_event()
        result = execute_drop_action(
            layout_tree,
            new_pane_factory,
            find_pane,
            None,
            target_pane,
            DropZone.TOP,
            event,
        )
        assert result is True
        new_pane_factory.assert_called_once()
        source_pane.remove_content.assert_called_once_with("cid")
        new_pane.add_content.assert_called_once_with("cid", "Title", widget, icon=None)
        layout_tree.split.assert_called_once_with(
            target_pane, Qt.Vertical, True, new_pane
        )

    def test_bottom_splits_vertical_insert_after(self):
        """BOTTOM：split(Vertical, insert_before=False)。"""
        widget = Mock()
        source_pane = self._make_mock_pane(get_content_widget_result=widget)
        target_pane = self._make_mock_pane()
        new_pane = self._make_mock_pane()
        find_pane = Mock(return_value=source_pane)
        new_pane_factory = Mock(return_value=new_pane)
        layout_tree = Mock()
        event = self._make_mock_event()
        result = execute_drop_action(
            layout_tree,
            new_pane_factory,
            find_pane,
            None,
            target_pane,
            DropZone.BOTTOM,
            event,
        )
        assert result is True
        layout_tree.split.assert_called_once_with(
            target_pane, Qt.Vertical, False, new_pane
        )

    def test_left_splits_horizontal_insert_before(self):
        """LEFT：split(Horizontal, insert_before=True)。"""
        widget = Mock()
        source_pane = self._make_mock_pane(get_content_widget_result=widget)
        target_pane = self._make_mock_pane()
        new_pane = self._make_mock_pane()
        find_pane = Mock(return_value=source_pane)
        new_pane_factory = Mock(return_value=new_pane)
        layout_tree = Mock()
        event = self._make_mock_event()
        result = execute_drop_action(
            layout_tree,
            new_pane_factory,
            find_pane,
            None,
            target_pane,
            DropZone.LEFT,
            event,
        )
        assert result is True
        layout_tree.split.assert_called_once_with(
            target_pane, Qt.Horizontal, True, new_pane
        )

    def test_right_splits_horizontal_insert_after(self):
        """RIGHT：split(Horizontal, insert_before=False)。"""
        widget = Mock()
        source_pane = self._make_mock_pane(get_content_widget_result=widget)
        target_pane = self._make_mock_pane()
        new_pane = self._make_mock_pane()
        find_pane = Mock(return_value=source_pane)
        new_pane_factory = Mock(return_value=new_pane)
        layout_tree = Mock()
        event = self._make_mock_event()
        result = execute_drop_action(
            layout_tree,
            new_pane_factory,
            find_pane,
            None,
            target_pane,
            DropZone.RIGHT,
            event,
        )
        assert result is True
        layout_tree.split.assert_called_once_with(
            target_pane, Qt.Horizontal, False, new_pane
        )

    def test_split_calls_on_new_pane(self):
        """非 CENTER 且提供 on_new_pane 时，调用 on_new_pane(new_pane)。"""
        widget = Mock()
        source_pane = self._make_mock_pane(get_content_widget_result=widget)
        target_pane = self._make_mock_pane()
        new_pane = self._make_mock_pane()
        find_pane = Mock(return_value=source_pane)
        new_pane_factory = Mock(return_value=new_pane)
        layout_tree = Mock()
        on_new_pane = Mock()
        event = self._make_mock_event()
        execute_drop_action(
            layout_tree,
            new_pane_factory,
            find_pane,
            on_new_pane,
            target_pane,
            DropZone.TOP,
            event,
        )
        on_new_pane.assert_called_once_with(new_pane)

    def test_accept_proposed_action_called_on_success(self):
        """成功执行后 event.acceptProposedAction() 被调用。"""
        widget = Mock()
        source_pane = self._make_mock_pane(get_content_widget_result=widget)
        target_pane = self._make_mock_pane()
        find_pane = Mock(return_value=source_pane)
        event = self._make_mock_event()
        execute_drop_action(
            Mock(), Mock(), find_pane, None, target_pane, DropZone.CENTER, event
        )
        event.acceptProposedAction.assert_called_once()
