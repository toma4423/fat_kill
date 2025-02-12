import pytest
from PyQt6.QtWidgets import QMessageBox
from ui import MainWindow

# ※ pytest-qt の qtbot フィクスチャを利用します


def test_build_tree_item(qtbot):
    # MainWindow のインスタンスを生成
    window = MainWindow()
    qtbot.addWidget(window)

    # テスト用のデータ（通常のディレクトリ）を作成
    data = {
        "name": "TestDir",
        "size": 2048,  # 2048 bytes → human_readable_size() で "2.00 KB" になるはず
        "children": [],
        "accessible": True,
        "hidden": False,
    }

    item = window.build_tree_item(data)
    # 列0 にはディレクトリ名、列1 には変換後のサイズが表示されることを確認
    assert item.text(0) == "TestDir"
    assert item.text(1) == "2.00 KB"


def test_on_scan_finished_error(monkeypatch, qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    # エラー情報付きのダミー tree_data を作成
    error_tree_data = {
        "name": "dummy",
        "size": 0,
        "children": [],
        "accessible": False,
        "hidden": False,
        "error": "Test error message",
    }

    captured = []

    def fake_warning(parent, title, message):
        captured.append((title, message))

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)

    window.on_scan_finished(error_tree_data)

    # 警告ダイアログが呼ばれたかを確認する
    assert len(captured) == 1
    title, message = captured[0]
    assert title == "スキャンエラー"
    assert "Test error message" in message
