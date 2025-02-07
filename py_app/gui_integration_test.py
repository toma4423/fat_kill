import os
import sys
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QTreeView,
    QHeaderView,
    QProgressBar,
    QMessageBox,
)
from PyQt6.QtGui import QFileSystemModel, QStandardItemModel, QStandardItem
from PyQt6.QtCore import (
    QSize,
    QDir,
    Qt,
    QThread,
    pyqtSignal,
    QObject,
    pyqtSlot,
    QTimer,
    QRunnable,
    QThreadPool,
)  # QObject, pyqtSlot を追加

# from PyQt6.QtCore import QTimer

import rust_lib

print("Rust lib imported successfully")


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str, str)
    result = pyqtSignal(str, int)
    progress = pyqtSignal(int, int)
    current_file = pyqtSignal(str)


class DirSizeWorker(QRunnable):
    def __init__(self, path, depth=1):
        super().__init__()
        self.path = path
        self.signals = WorkerSignals()
        self.is_cancelled = False
        self.depth = depth  # 走査する深さ

    def run(self):
        try:
            total_files = 0
            # 指定された深さまでのディレクトリを取得
            base_depth = self.path.count(os.sep)
            print(f"Processing directory: {self.path} at depth {self.depth}")
            # 直接の子ディレクトリのみを処理
            try:
                with os.scandir(self.path) as it:
                    entries = list(it)
                    total_files = len([e for e in entries if e.is_file()])
                    # まずルートディレクトリのサイズを計算
                    root_size = rust_lib.get_dir_size_py(self.path)
                    self.signals.result.emit(self.path, root_size)

                    # 子ディレクトリのみを処理
                    for entry in entries:
                        if self.is_cancelled:
                            return
                        if entry.is_dir():
                            dir_path = entry.path
                            dir_size = rust_lib.get_dir_size_py(dir_path)
                            self.signals.result.emit(dir_path, dir_size)
            except PermissionError:
                print(f"Permission denied: {self.path}")
                return
            except Exception as e:
                print(f"Error scanning directory: {e}")
                return

            self.signals.progress.emit(total_files, total_files)
        finally:
            self.signals.finished.emit()

    def cancel(self):
        self.is_cancelled = True


class DirectorySizeViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        print(f"Maximum thread count: {self.threadpool.maxThreadCount()}")
        self.last_directory = os.getcwd()
        self.init_ui()

    def init_ui(self):
        print("DirectorySizeViewer.init_ui() called")
        # レイアウト
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # ウィンドウサイズ設定
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle("Directory Size Viewer")

        # パス入力欄と参照ボタン
        path_layout = QHBoxLayout()
        self.path_label = QLabel("Path:")
        self.path_entry = QLineEdit()
        self.path_entry.setText(os.getcwd())
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_directory)
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_entry)
        path_layout.addWidget(self.browse_button)
        main_layout.addLayout(path_layout)

        # ボタン
        button_layout = QHBoxLayout()
        self.scan_button = QPushButton("Scan Directory")
        self.scan_button.clicked.connect(self.scan_directory)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_scan)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.scan_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        # 状態表示
        self.status_label = QLabel("Ready")
        self.result_label = QLabel("")
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.result_label)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        # ツリービュー
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(False)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.expanded.connect(self.on_item_expanded)  # 展開時のイベント

        # モデルの初期化
        self.model = QStandardItemModel()
        self.model.setColumnCount(2)
        self.model.setHorizontalHeaderLabels(["Name", "Size"])
        self.tree_view.setModel(self.model)

        # ヘッダー設定
        self.tree_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_view.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )
        self.tree_view.header().resizeSection(1, 150)

        main_layout.addWidget(self.tree_view)

    def browse_directory(self):
        directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        if directory:
            self.path_entry.setText(directory)

    def scan_directory(self):
        path = self.path_entry.text().strip()
        if not path:
            self.status_label.setText("Error: No path specified")
            return

        if not os.path.exists(path):
            self.status_label.setText("Error: Path does not exist")
            return

        if not os.path.isdir(path):
            self.status_label.setText("Error: Not a directory")
            return

        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.show()
        self.status_label.setText("Scanning...")
        self.result_label.setText("")

        # モデルをクリア
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Name", "Size"])

        # ルートディレクトリの直下のみを走査
        worker = DirSizeWorker(path, depth=1)
        worker.signals.result.connect(self.handle_result)
        worker.signals.error.connect(self.handle_error)
        worker.signals.finished.connect(self.scan_complete)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.current_file.connect(self.update_current_file)

        self.current_worker = worker
        self.threadpool.start(worker)

    @pyqtSlot(str, int)
    def handle_result(self, path, size):
        print("DirectorySizeViewer.handle_result() called")
        print(f"Processing path: {path} with size: {size}")

        # ファイルの場合は表示しない
        if not os.path.isdir(path):
            print(f"Skipping file: {path}")
            return

        # モデルが未初期化の場合は初期化
        if self.model is None:
            self.model = QStandardItemModel()
            self.model.setColumnCount(2)
            self.model.setHorizontalHeaderLabels(["Name", "Size"])
            self.tree_view.setModel(self.model)

        # 既存のアイテムを探す（更新のため）
        existing_item = None

        def find_existing_item(start_item):
            if not start_item:
                return None
            if start_item.data(Qt.ItemDataRole.UserRole + 1) == path:
                return start_item
            for row in range(start_item.rowCount()):
                child = start_item.child(row, 0)
                result = find_existing_item(child)
                if result:
                    return result
            return None

        # ルートから既存アイテムを探す
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            existing_item = find_existing_item(item)
            if existing_item:
                break

        # パスの階層を分解
        parent_path = os.path.dirname(path)
        name = os.path.basename(path)
        print(f"Parent path: {parent_path}, Name: {name}")

        # 選択されたルートパス
        root_path = self.path_entry.text().strip()
        print(f"Root path: {root_path}")

        # 親アイテムを探す
        parent_item = None
        if parent_path != os.path.dirname(root_path):
            # 親パスを持つアイテムを再帰的に探す
            def find_parent_item(start_item):
                if not start_item:
                    return None
                # まず現在のアイテムをチェック
                if start_item.data(Qt.ItemDataRole.UserRole + 1) == parent_path:
                    return start_item
                for row in range(start_item.rowCount()):
                    child = start_item.child(row, 0)
                    if child.data(Qt.ItemDataRole.UserRole + 1) == parent_path:
                        return child
                    if child.hasChildren():
                        result = find_parent_item(child)
                        if result:
                            return result
                return None

            # ルートから親アイテムを探す
            for row in range(self.model.rowCount()):
                item = self.model.item(row, 0)
                if item.data(Qt.ItemDataRole.UserRole + 1) == parent_path:
                    parent_item = item
                    break
                if item.hasChildren():
                    parent_item = find_parent_item(item)
                    if parent_item:
                        break

        print(f"Found parent item: {parent_item.text() if parent_item else 'None'}")

        # 既存アイテムがある場合は更新
        if existing_item:
            # ルートアイテムの場合は親がないので直接モデルから更新
            if existing_item.parent() is None:
                self.model.setItem(
                    existing_item.row(), 1, QStandardItem(self.format_size(size))
                )
            else:
                existing_item.parent().setChild(
                    existing_item.row(), 1, QStandardItem(self.format_size(size))
                )
            # 子ディレクトリがある場合はダミーアイテムを追加
            if not existing_item.hasChildren():
                has_subdirs = False
                # 直接の子ディレクトリのみをチェック
                try:
                    with os.scandir(path) as it:
                        for entry in it:
                            if entry.is_dir():
                                has_subdirs = True
                                break
                except PermissionError:
                    print(f"Permission denied: {path}")
                except Exception as e:
                    print(f"Error checking subdirs: {e}")

                if has_subdirs:
                    # ダミーアイテムを追加して展開可能なことを示す
                    dummy = QStandardItem("")
                    existing_item.appendRow([dummy, QStandardItem("")])
            return

        item = QStandardItem(name)
        size_item = QStandardItem(self.format_size(size))
        item.setData(path, Qt.ItemDataRole.UserRole + 1)
        item.setData(True, Qt.ItemDataRole.UserRole + 2)
        # 子ディレクトリがあるかチェック
        has_subdirs = False
        # 直接の子ディレクトリのみをチェック
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_dir():
                        has_subdirs = True
                        break
        except PermissionError:
            print(f"Permission denied: {path}")
        except Exception as e:
            print(f"Error checking subdirs: {e}")

        if has_subdirs:
            # ダミーアイテムを追加して展開可能なことを示す
            dummy = QStandardItem("")
            item.appendRow([dummy, QStandardItem("")])
        print(f"Adding directory: {path}")

        if parent_item:
            parent_item.appendRow([item, size_item])
            print(f"Added to parent: {parent_item.text()}")
        else:
            self.model.appendRow([item, size_item])
            print("Added to root")

    @pyqtSlot(str)
    def handle_error(self, error_message):
        # エラー処理 (QMessageBox などを使うと良い)
        QMessageBox.critical(self, "Error", error_message)
        self.progress_bar.hide()
        self.scan_button.setEnabled(True)

    @pyqtSlot()
    def scan_complete(self):
        print("DirectorySizeViewer.scan_complete() called")
        self.progress_bar.hide()
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if hasattr(self, "current_worker"):
            delattr(self, "current_worker")

    def format_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def update_progress(self, current, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)

    def update_current_file(self, file):
        self.status_label.setText(f"Scanning: {file}")

    def cancel_scan(self):
        """スキャンをキャンセルする"""
        if hasattr(self, "current_worker"):
            self.current_worker.cancel()
            self.status_label.setText("Cancelling...")
            self.cancel_button.setEnabled(False)

    def on_item_expanded(self, index):
        """ツリーアイテムが展開されたときの処理"""
        item = self.model.itemFromIndex(index)
        if not item:
            print("No item found for index")
            return

        # アイテムが既に子を持っている場合はダミーアイテムかどうかをチェック
        if item.hasChildren() and item.child(0, 0).text() != "":
            print(f"Item {item.text()} already has children")
            return

        # ダミーアイテムを削除
        if item.hasChildren():
            item.removeRow(0)

        # パスを取得して子ディレクトリを走査
        path = item.data(Qt.ItemDataRole.UserRole + 1)
        print(f"Expanding directory: {path}")
        if path and os.path.isdir(path):
            self.progress_bar.show()
            worker = DirSizeWorker(path, depth=1)
            worker.signals.result.connect(self.handle_result)
            worker.signals.error.connect(self.handle_error)
            worker.signals.finished.connect(self.scan_complete)
            worker.signals.progress.connect(self.update_progress)
            worker.signals.current_file.connect(self.update_current_file)
            self.current_worker = worker  # 現在のワーカーを保持
            self.threadpool.start(worker)
        else:
            print(f"Path not valid or not a directory: {path}")


if __name__ == "__main__":
    print("__main__ block started")
    try:
        app = QApplication(sys.argv)
        print("QApplication object created")  # 追加
        viewer = DirectorySizeViewer()
        print("DirectorySizeViewer object created")  # 追加
        viewer.show()
        print("Window shown")  # 追加
        print(f"Window visible: {viewer.isVisible()}")  # 追加
        exit_code = app.exec()
        print(f"Exiting with code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        print(f"An error occurred: {e}")
    except SystemExit as e:
        print(f"SystemExit occurred: {e}")
    except KeyboardInterrupt:
        print("KeyboardInterrupt: Program terminated by user")
        sys.exit(1)
