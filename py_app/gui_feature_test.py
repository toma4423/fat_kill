"""
Rustライブラリ機能テストスクリプト

このスクリプトは、rust_libの機能をテストするためのものです。
基本的なディレクトリサイズ計算、進捗報告、キャンセル機能をテストします。
"""

import rust_lib
import os
import time
import sys
from pathlib import Path


def test_basic_function():
    """基本的なディレクトリサイズ計算のテスト"""
    print("===== 基本機能のテスト =====")
    path = os.path.expanduser("~")  # ホームディレクトリ
    print(f"ディレクトリ: {path}")

    try:
        start_time = time.time()
        size = rust_lib.get_dir_size_py(path)
        elapsed = time.time() - start_time

        if size == rust_lib.get_access_denied_value():
            print(f"結果: 一部のサブディレクトリにアクセスできませんでした")
        else:
            print(f"結果: {size} バイト ({size / (1024*1024):.2f} MB)")

        print(f"処理時間: {elapsed:.2f} 秒")
    except Exception as e:
        print(f"エラー: {e}")


def progress_callback(path, size):
    """進捗報告用コールバック関数"""
    # パスを短縮して表示
    short_path = Path(path).name
    print(f"処理中: {short_path} - {size / 1024:.1f} KB")


def test_progress_reporting():
    """進捗報告機能のテスト"""
    print("\n===== 進捗報告機能のテスト =====")

    # テスト用のディレクトリ（小さめのディレクトリを選択）
    if sys.platform == "win32":
        path = os.path.join(os.environ["USERPROFILE"], "Documents")
    else:
        path = os.path.join(os.path.expanduser("~"), "Documents")

    print(f"ディレクトリ: {path}")

    # キャンセルフラグの作成
    cancel_ptr = rust_lib.create_cancel_flag()

    try:
        start_time = time.time()
        size = rust_lib.get_dir_size_with_cancel_py(path, cancel_ptr, progress_callback)
        elapsed = time.time() - start_time

        if size == rust_lib.get_access_denied_value():
            print(f"結果: 一部のサブディレクトリにアクセスできませんでした")
        else:
            print(f"結果: {size} バイト ({size / (1024*1024):.2f} MB)")

        print(f"処理時間: {elapsed:.2f} 秒")
    except Exception as e:
        print(f"エラー: {e}")
    finally:
        # キャンセルフラグの解放
        rust_lib.release_cancel_flag(cancel_ptr)


def test_cancellation():
    """キャンセル機能のテスト"""
    print("\n===== キャンセル機能のテスト =====")

    # テスト用のディレクトリ（大きめのディレクトリを選択）
    path = os.path.expanduser("~")  # ホームディレクトリ
    print(f"ディレクトリ: {path}")

    # キャンセルフラグの作成
    cancel_ptr = rust_lib.create_cancel_flag()

    # 別スレッドで少し待ってからキャンセル
    import threading

    def cancel_after_delay():
        time.sleep(0.5)  # 0.5秒後にキャンセル
        print("\n処理をキャンセルします...")
        rust_lib.set_cancel_flag(cancel_ptr, True)

    threading.Thread(target=cancel_after_delay).start()

    try:
        start_time = time.time()
        size = rust_lib.get_dir_size_with_cancel_py(path, cancel_ptr, progress_callback)
        elapsed = time.time() - start_time

        print(f"結果: {size} バイト ({size / (1024*1024):.2f} MB)")
        print(f"処理時間: {elapsed:.2f} 秒")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"エラー: {e}")
        print(f"キャンセルまでの時間: {elapsed:.2f} 秒")
    finally:
        # キャンセルフラグの解放
        rust_lib.release_cancel_flag(cancel_ptr)


def test_error_handling():
    """エラーハンドリングのテスト"""
    print("\n===== エラーハンドリングのテスト =====")

    # 存在しないディレクトリ
    path = "/path/to/nonexistent/directory"
    print(f"存在しないディレクトリ: {path}")

    try:
        size = rust_lib.get_dir_size_py(path)
        print(f"結果: {size} バイト")
    except Exception as e:
        print(f"エラー: {e}")

    # アクセス権限のないディレクトリ
    if sys.platform == "win32":
        path = "C:\\Windows\\System32\\config"
    else:
        path = "/root"

    print(f"\nアクセス権限のないディレクトリ: {path}")

    try:
        size = rust_lib.get_dir_size_py(path)
        if size == rust_lib.get_access_denied_value():
            print(f"結果: アクセス拒否 (u64::MAX)")
        else:
            print(f"結果: {size} バイト")
    except Exception as e:
        print(f"エラー: {e}")


if __name__ == "__main__":
    print("Rustライブラリ機能テスト\n")

    try:
        test_basic_function()
        test_progress_reporting()
        test_cancellation()
        test_error_handling()

        print("\nすべてのテストが完了しました。")
    except Exception as e:
        print(f"\n予期しないエラーが発生しました: {e}")
