"""
Directory Size Viewerのテスト

このモジュールは、Directory Size Viewerアプリケーションの
機能をテストするためのPytestテストケースを提供します。
"""

import os
import sys
import time
import pytest
import tempfile
import shutil
from pathlib import Path

# Rustライブラリのインポート
try:
    import rust_lib

    RUST_AVAILABLE = True
    print("Rustライブラリが正常にインポートされました")
except ImportError as e:
    RUST_AVAILABLE = False
    print(f"警告: Rustライブラリのインポートに失敗しました: {e}")


# テスト用のディレクトリ構造を作成
@pytest.fixture
def test_directory():
    """テスト用のディレクトリ構造を作成して提供するフィクスチャ"""
    # 一時ディレクトリの作成
    temp_dir = tempfile.mkdtemp()

    try:
        # サブディレクトリの作成
        for i in range(5):
            subdir = os.path.join(temp_dir, f"subdir_{i}")
            os.makedirs(subdir)

            # ファイルの作成
            for j in range(3):
                file_path = os.path.join(subdir, f"file_{j}.txt")
                with open(file_path, "w") as f:
                    # 異なるサイズのファイルを作成
                    f.write("x" * (1024 * (i + 1) * (j + 1)))

        yield temp_dir
    finally:
        # テスト後にディレクトリを削除
        shutil.rmtree(temp_dir)


# Rustライブラリのテスト
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rustライブラリが利用できません")
def test_rust_dir_size(test_directory):
    """Rustライブラリのディレクトリサイズ計算をテスト"""
    # 基本的なサイズ計算
    size = rust_lib.get_dir_size_py(test_directory)
    assert size > 0, "ディレクトリサイズは0より大きいはずです"

    # サブディレクトリのサイズ計算
    subdirs = [
        os.path.join(test_directory, d)
        for d in os.listdir(test_directory)
        if os.path.isdir(os.path.join(test_directory, d))
    ]
    for subdir in subdirs:
        subdir_size = rust_lib.get_dir_size_py(subdir)
        assert (
            subdir_size > 0
        ), f"サブディレクトリ {subdir} のサイズは0より大きいはずです"


# キャンセル機能のテスト
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rustライブラリが利用できません")
def test_rust_cancellation(test_directory):
    """Rustライブラリのキャンセル機能をテスト"""
    # キャンセルフラグの作成
    cancel_ptr = rust_lib.create_cancel_flag()

    # 進捗コールバック
    progress_calls = []

    def progress_callback(path, size):
        progress_calls.append((path, size))
        # 数回呼び出された後にキャンセル
        if len(progress_calls) >= 5:
            rust_lib.set_cancel_flag(cancel_ptr, True)

    try:
        # キャンセルされることを期待
        with pytest.raises(Exception) as excinfo:
            rust_lib.get_dir_size_with_cancel_py(
                test_directory, cancel_ptr, progress_callback
            )

        # キャンセルエラーメッセージの確認
        assert "キャンセルされました" in str(excinfo.value)

        # 進捗コールバックが呼ばれたことを確認
        assert len(progress_calls) >= 5
    finally:
        # キャンセルフラグの解放
        rust_lib.release_cancel_flag(cancel_ptr)


# 進捗報告のテスト
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rustライブラリが利用できません")
def test_rust_progress_reporting(test_directory):
    """Rustライブラリの進捗報告機能をテスト"""
    # キャンセルフラグの作成
    cancel_ptr = rust_lib.create_cancel_flag()

    # 進捗コールバック
    progress_calls = []

    def progress_callback(path, size):
        progress_calls.append((path, size))

    try:
        # ディレクトリサイズの計算
        size = rust_lib.get_dir_size_with_cancel_py(
            test_directory, cancel_ptr, progress_callback
        )

        # サイズが正しく計算されたことを確認
        assert size > 0

        # 進捗コールバックが呼ばれたことを確認
        assert len(progress_calls) > 0

        # 進捗報告の内容を確認
        for path, size in progress_calls:
            assert isinstance(path, str)
            assert isinstance(size, int)
            assert size > 0
    finally:
        # キャンセルフラグの解放
        rust_lib.release_cancel_flag(cancel_ptr)


# エラーハンドリングのテスト
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rustライブラリが利用できません")
def test_rust_error_handling():
    """Rustライブラリのエラーハンドリングをテスト"""
    # 存在しないディレクトリ
    non_existent_dir = "/path/to/non/existent/directory"

    # エラーが発生することを期待
    with pytest.raises(Exception) as excinfo:
        rust_lib.get_dir_size_py(non_existent_dir)

    # エラーメッセージの確認
    assert "I/Oエラー" in str(excinfo.value)


# アクセス拒否値のテスト
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rustライブラリが利用できません")
def test_access_denied_value():
    """アクセス拒否値の取得をテスト"""
    value = rust_lib.get_access_denied_value()
    assert value == 2**64 - 1  # u64::MAX
