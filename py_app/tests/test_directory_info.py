import os
import threading
from pathlib import Path
import pytest

from directory_info import get_directory_tree


def test_get_directory_tree_normal(tmp_path: Path):
    # 一時ディレクトリにテスト用のフォルダ構造を作成
    folder = tmp_path / "folder"
    folder.mkdir()
    subfolder = folder / "subdir"
    subfolder.mkdir()
    test_file = subfolder / "test.txt"
    test_file.write_text("Hello world!")

    # get_directory_tree を呼び出し
    tree = get_directory_tree(str(folder))

    # ルート名が 'folder' であることを確認
    assert tree["name"] == "folder"
    # 子ディレクトリが1件あることを確認
    assert len(tree["children"]) == 1
    child = tree["children"][0]
    # 子ディレクトリ名が "subdir" であることを確認
    assert child["name"] == "subdir"

    # サブディレクトリのサイズが、ファイルサイズと一致することを確認
    expected_size = os.path.getsize(str(test_file))
    assert child["size"] == expected_size


def test_get_directory_tree_cancel(tmp_path: Path):
    # キャンセルイベントがセットされた場合、get_directory_tree は None を返すはず
    folder = tmp_path / "folder"
    folder.mkdir()

    cancel_event = threading.Event()
    cancel_event.set()

    tree = get_directory_tree(str(folder), cancel_event)
    assert tree is None


def test_get_directory_tree_permission(monkeypatch, tmp_path: Path):
    # os.listdir を強制的に PermissionError を発生させることでテスト
    folder = tmp_path / "folder"
    folder.mkdir()

    def fake_listdir(path):
        raise PermissionError("No permission")

    monkeypatch.setattr(os, "listdir", fake_listdir)

    tree = get_directory_tree(str(folder))
    # PermissionError 発生時は accessible が False になっているはず
    assert tree["accessible"] is False
