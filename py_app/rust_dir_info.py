"""
このモジュールは、Rust で実装されたディレクトリ情報取得機能
(get_directory_tree, get_directory_info) を提供するラッパーです。

※ 本モジュールは、既存の directory_info.py を変更せずに、
    Rust 製の高速処理へ切り替えるために利用します。

参考: [PythonとRustで爆速ファイルシステム操作！初心者向け環境構築ガイド](https://kogetsuki.2-d.jp/?p=71)
"""

import rust_lib  # maturin でビルドした拡張モジュール
from typing import Optional, Dict, Any


def get_directory_tree(path: str, cancel: bool = False) -> Optional[Dict[str, Any]]:
    # Rust 側の関数は dict または None を返す設計とする
    return rust_lib.get_directory_tree(path, cancel)


def get_directory_info(path: str) -> Dict[str, Any]:
    return rust_lib.get_directory_info(path)
