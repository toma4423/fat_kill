"""
ディレクトリサイズ表示アプリケーション

このアプリケーションは、選択したディレクトリのサイズを計算し、
サブディレクトリごとのサイズをツリービュー形式で表示します。
Rustライブラリを使用して高速な計算を実現しています。
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable, Any

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFileDialog,
    QProgressBar,
    QTreeView,
    QMessageBox,
    QStatusBar,
)
from PyQt6.QtCore import (
    Qt,
    QObject,
    QRunnable,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
    QModelIndex,
    QSize,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem

# Rustライブラリのインポート
try:
    import rust_lib

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    print("警告: Rustライブラリが見つかりません。Pythonの実装を使用します。")


class WorkerSignals(QObject):
    """ワーカースレッドからのシグナルを定義するクラス"""

    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(str, int)


class DirectorySizeWorker(QRunnable):
    """ディレクトリサイズ計算を行うワーカークラス"""

    def __init__(self, directory: str):
        """ワーカーの初期化"""
        super().__init__()
        self.directory = directory
        self.signals = WorkerSignals()
        self.is_cancelled = False

        # キャンセルフラグの作成（Rust実装の場合）
        if RUST_AVAILABLE:
            self.cancel_ptr = rust_lib.create_cancel_flag()
        else:
            self.cancel_ptr = None

    def cancel(self):
        """処理のキャンセル"""
        self.is_cancelled = True
        if RUST_AVAILABLE and self.cancel_ptr is not None:
            rust_lib.set_cancel_flag(self.cancel_ptr, True)

    @pyqtSlot()
    def run(self):
        """ディレクトリサイズの計算を実行"""
        try:
            start_time = time.time()

            if RUST_AVAILABLE:
                # Rust実装を使用
                try:
                    # 進捗コールバック関数
                    def progress_callback(path, size):
                        self.signals.progress.emit(path, size)

                    # Rustライブラリを使用してディレクトリサイズを計算
                    total_size = rust_lib.get_dir_size_with_cancel_py(
                        self.directory, self.cancel_ptr, progress_callback
                    )

                    # ディレクトリ構造とサイズを取得
                    dir_structure = self.get_directory_structure(self.directory)

                except Exception as e:
                    if "キャンセルされました" in str(e):
                        self.signals.error.emit("処理がキャンセルされました")
                    else:
                        self.signals.error.emit(f"エラー: {e}")
                    return
            else:
                # Python実装を使用
                try:
                    total_size, dir_structure = self.get_directory_size_py(
                        self.directory
                    )
                except Exception as e:
                    self.signals.error.emit(f"エラー: {e}")
                    return

            elapsed_time = time.time() - start_time

            # 結果を返す
            result = {
                "total_size": total_size,
                "dir_structure": dir_structure,
                "elapsed_time": elapsed_time,
            }
            self.signals.result.emit(result)

        except Exception as e:
            self.signals.error.emit(f"予期せぬエラー: {e}")
        finally:
            # キャンセルフラグの解放（Rust実装の場合）
            if RUST_AVAILABLE and self.cancel_ptr is not None:
                rust_lib.release_cancel_flag(self.cancel_ptr)
                self.cancel_ptr = None

            self.signals.finished.emit()

    def get_directory_structure(self, directory):
        """ディレクトリ構造を再帰的に取得"""
        result = {"path": directory, "size": 0, "children": []}

        try:
            # ディレクトリ全体のサイズを取得
            if RUST_AVAILABLE:
                result["size"] = rust_lib.get_dir_size_py(directory)
            else:
                result["size"], _ = self.get_directory_size_py(directory, False)

            # サブディレクトリを取得
            with os.scandir(directory) as entries:
                for entry in entries:
                    if self.is_cancelled:
                        return result

                    if entry.is_dir():
                        # 再帰的にサブディレクトリの構造を取得
                        child = self.get_directory_structure(entry.path)
                        result["children"].append(child)
        except PermissionError:
            # アクセス拒否の場合
            if RUST_AVAILABLE:
                result["size"] = rust_lib.get_access_denied_value()
            else:
                result["size"] = 2**64 - 1  # u64::MAX
            result["access_denied"] = True
        except Exception as e:
            print(f"ディレクトリ構造の取得エラー: {directory} - {e}")

        return result

    def get_directory_size_py(self, directory, update_progress=True):
        """ディレクトリサイズの計算（Python実装）"""
        total_size = 0
        dir_structure = {"path": directory, "size": 0, "children": []}

        # アクセス拒否値の取得
        if RUST_AVAILABLE:
            access_denied_value = rust_lib.get_access_denied_value()
        else:
            access_denied_value = 2**64 - 1  # u64::MAX

        # サブディレクトリのサイズを計算
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if self.is_cancelled:
                        # キャンセルされた場合
                        return 0, dir_structure

                    if entry.is_dir():
                        subdir_path = entry.path
                        try:
                            subdir_size, subdir_structure = self.get_directory_size_py(
                                subdir_path, False
                            )
                            dir_structure["children"].append(subdir_structure)
                            total_size += subdir_size
                        except PermissionError:
                            child = {
                                "path": subdir_path,
                                "size": access_denied_value,
                                "children": [],
                                "access_denied": True,
                            }
                            dir_structure["children"].append(child)
                    elif entry.is_file():
                        try:
                            file_size = entry.stat().st_size
                            total_size += file_size

                            # 進捗状況の更新
                            if update_progress:
                                self.signals.progress.emit(entry.path, file_size)
                        except (PermissionError, OSError):
                            pass
        except PermissionError:
            dir_structure["size"] = access_denied_value
            dir_structure["access_denied"] = True
            return access_denied_value, dir_structure

        dir_structure["size"] = total_size
        return total_size, dir_structure


class SizeItem(QStandardItem):
    """サイズ表示用のカスタムアイテムクラス"""

    def __init__(self, size_bytes):
        """アイテムの初期化"""
        self.size_bytes = size_bytes
        size_str = self.format_size(size_bytes)
        super().__init__(size_str)

    def format_size(self, size_bytes):
        """バイト数を読みやすい形式に変換"""
        if size_bytes == 0:
            return "0 B"

        # アクセス拒否値の場合
        if RUST_AVAILABLE and size_bytes == rust_lib.get_access_denied_value():
            return "アクセス拒否"

        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1

        return f"{size:.2f} {units[i]}"

    def __lt__(self, other):
        """ソート用の比較演算子"""
        if isinstance(other, SizeItem):
            return self.size_bytes < other.size_bytes
        return super().__lt__(other)


class DirectorySizeViewer(QMainWindow):
    """ディレクトリサイズ表示アプリケーションのメインクラス"""

    def __init__(self):
        """アプリケーションの初期化"""
        super().__init__()

        # ウィンドウの設定
        self.setWindowTitle("ディレクトリサイズ表示")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(800, 600)

        # スレッドプールの設定
        self.thread_pool = QThreadPool()
        print(f"スレッド数: {self.thread_pool.maxThreadCount()}")

        # 現在のワーカー
        self.current_worker = None

        # アクセス拒否値の取得
        if RUST_AVAILABLE:
            self.access_denied_value = rust_lib.get_access_denied_value()
        else:
            self.access_denied_value = 2**64 - 1  # u64::MAX

        # UIの設定
        self.setup_ui()

    def setup_ui(self):
        """UIコンポーネントの設定"""
        # メインウィジェット
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # メインレイアウト
        main_layout = QVBoxLayout(main_widget)

        # 上部フレーム（ディレクトリ選択部分）
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # ディレクトリラベル
        dir_label = QLabel("ディレクトリ:")
        top_layout.addWidget(dir_label)

        # ディレクトリ入力欄
        self.dir_entry = QLineEdit()
        top_layout.addWidget(self.dir_entry)

        # 参照ボタン
        self.browse_button = QPushButton("参照")
        self.browse_button.clicked.connect(self.browse_directory)
        top_layout.addWidget(self.browse_button)

        # 解析ボタン
        self.analyze_button = QPushButton("解析")
        self.analyze_button.clicked.connect(self.analyze_directory)
        top_layout.addWidget(self.analyze_button)

        # キャンセルボタン
        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.cancel_button.setEnabled(False)
        top_layout.addWidget(self.cancel_button)

        # ツリービュー
        self.tree_view = QTreeView()
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.tree_view.setMinimumHeight(400)
        main_layout.addWidget(self.tree_view)

        # モデルの設定（パス列を削除）
        self.model = QStandardItemModel(0, 2)
        self.model.setHorizontalHeaderLabels(["名前", "サイズ"])
        self.tree_view.setModel(self.model)

        # 進捗バー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不確定モード
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了")

        # カラム幅の設定
        self.tree_view.setColumnWidth(0, 500)  # 名前
        self.tree_view.setColumnWidth(1, 150)  # サイズ

    def browse_directory(self):
        """ディレクトリ選択ダイアログを表示"""
        directory = QFileDialog.getExistingDirectory(self, "ディレクトリを選択")
        if directory:
            self.dir_entry.setText(directory)

    def analyze_directory(self):
        """ディレクトリの解析を開始"""
        directory = self.dir_entry.text()
        if not directory:
            QMessageBox.warning(self, "警告", "ディレクトリを選択してください")
            return

        if not os.path.isdir(directory):
            QMessageBox.warning(self, "警告", "有効なディレクトリを選択してください")
            return

        # UIの状態を更新
        self.analyze_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)

        # モデルをクリア
        self.model.removeRows(0, self.model.rowCount())

        # ワーカーの作成と実行
        self.current_worker = DirectorySizeWorker(directory)
        self.current_worker.signals.result.connect(self.update_tree)
        self.current_worker.signals.error.connect(self.show_error)
        self.current_worker.signals.finished.connect(self.on_worker_finished)
        self.current_worker.signals.progress.connect(self.update_progress)

        self.thread_pool.start(self.current_worker)
        self.status_bar.showMessage("解析中...")

    def cancel_analysis(self):
        """解析処理をキャンセル"""
        if self.current_worker:
            self.current_worker.cancel()
            self.status_bar.showMessage("キャンセル中...")

    def update_tree(self, result):
        """ツリービューの更新"""
        total_size = result["total_size"]
        dir_structure = result["dir_structure"]
        elapsed_time = result["elapsed_time"]

        # ルートアイテムの作成
        directory = self.dir_entry.text()
        root_name = os.path.basename(directory) or directory

        name_item = QStandardItem(root_name)
        size_item = SizeItem(total_size)

        root_items = [name_item, size_item]
        self.model.appendRow(root_items)

        # 再帰的にツリーを構築
        self.add_directory_to_tree(dir_structure, name_item)

        # ツリーを展開
        root_index = self.model.index(0, 0)
        self.tree_view.expand(root_index)

        # カラムのリサイズ
        self.tree_view.resizeColumnToContents(0)

        # ステータスバーの更新
        if total_size == self.access_denied_value:
            status = f"完了（一部アクセス不可） - {elapsed_time:.2f}秒"
        else:
            size_mb = total_size / (1024 * 1024)
            status = f"完了 - {size_mb:.2f} MB - {elapsed_time:.2f}秒"

        self.status_bar.showMessage(status)

    def add_directory_to_tree(self, dir_info, parent_item):
        """ディレクトリ情報をツリーに再帰的に追加"""
        # 子ディレクトリを追加
        for child in dir_info.get("children", []):
            dir_path = child["path"]
            dir_name = os.path.basename(dir_path)
            dir_size = child["size"]

            # アクセス拒否の場合は視覚的に区別
            if child.get("access_denied", False):
                dir_name = f"{dir_name} (アクセス拒否)"

            name_item = QStandardItem(dir_name)
            size_item = SizeItem(dir_size)

            # 親アイテムに追加
            parent_item.appendRow([name_item, size_item])

            # 子ディレクトリがある場合は再帰的に追加
            if child.get("children") and len(child["children"]) > 0:
                self.add_directory_to_tree(child, name_item)

    def update_progress(self, path, size):
        """進捗状況の更新"""
        # パスの短縮表示
        short_path = os.path.basename(path)
        size_kb = size / 1024

        # ステータスバーの更新
        self.status_bar.showMessage(f"処理中: {short_path} - {size_kb:.1f} KB")

    def show_error(self, error_message):
        """エラーメッセージの表示"""
        QMessageBox.critical(self, "エラー", error_message)

    def on_worker_finished(self):
        """ワーカー終了時の処理"""
        # UIの状態をリセット
        self.analyze_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.current_worker = None


def main():
    """アプリケーションのメイン関数"""
    app = QApplication(sys.argv)
    viewer = DirectorySizeViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
