"""
Rustライブラリの動作確認スクリプト
"""

import sys
import os

print(f"Python バージョン: {sys.version}")
print(f"実行パス: {sys.executable}")
print(f"現在のディレクトリ: {os.getcwd()}")
print(f"sys.path: {sys.path}")

try:
    import rust_lib

    print("\nRustライブラリが正常にインポートされました")

    # 基本機能のテスト
    test_dir = os.path.dirname(os.path.abspath(__file__))
    size = rust_lib.get_dir_size_py(test_dir)
    print(f"現在のディレクトリサイズ: {size} バイト")

    # アクセス拒否値の取得
    access_denied = rust_lib.get_access_denied_value()
    print(f"アクセス拒否値: {access_denied}")

    # キャンセルフラグのテスト
    cancel_ptr = rust_lib.create_cancel_flag()
    print(f"キャンセルフラグポインタ: {cancel_ptr}")
    rust_lib.release_cancel_flag(cancel_ptr)
    print("キャンセルフラグを解放しました")

except ImportError as e:
    print(f"\n警告: Rustライブラリのインポートに失敗しました: {e}")

    # モジュール検索パスの確認
    print("\nモジュール検索パスの確認:")
    for path in sys.path:
        if os.path.exists(path):
            print(f"  存在: {path}")
            # .pyファイルとPythonパッケージの検索
            if os.path.isdir(path):
                for item in os.listdir(path):
                    if item.endswith(".py") or (
                        os.path.isdir(os.path.join(path, item))
                        and os.path.exists(os.path.join(path, item, "__init__.py"))
                    ):
                        print(f"    - {item}")
        else:
            print(f"  存在しない: {path}")
