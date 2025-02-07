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
    QMessageBox,
    QProgressBar,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import (
    QSize,
    QDir,
    Qt,
    QThread,
    pyqtSignal,
    QObject,
    pyqtSlot,
)
import errno

import rust_lib  # Rust ライブラリをインポート

print("Rust lib imported successfully")


class SizeItem(QStandardItem):
    def __init__(self, size_str, raw_size):
        super().__init__(size_str)
        self.raw_size = raw_size

    def __lt__(self, other):
        # サイズでソートする際に生の値を使用
        return self.raw_size < other.raw_size


class Worker(QObject):
    scan_complete = pyqtSignal(str, int, str)  # シグナル (名前, サイズ, パス)
    scan_error = pyqtSignal(str, str)  # エラーシグナル (エラー種別, メッセージ)
    finished = pyqtSignal()

    def __init__(self, path):
        super().__init__()
        self.path = path
        print(f"Worker initialized with path: {path}")

    @pyqtSlot()
    def run(self):
        print("Worker.run() started")
        try:
            size = rust_lib.get_dir_size_py(self.path)
            self.scan_complete.emit(os.path.basename(self.path), size, self.path)
        except OSError as e:
            if e.errno == errno.EACCES:
                self.scan_error.emit("Permission Error", f"Access denied: {e.strerror}")
            elif e.errno == errno.ENOENT:
                self.scan_error.emit("Path Error", f"Path not found: {e.strerror}")
            else:
                self.scan_error.emit("Error", f"An error occurred: {e.strerror}")
        finally:
            self.finished.emit()
        print("Worker.run() finished")


class DirectorySizeViewer(QWidget):
    def __init__(self):
        super().__init__()
        print("DirectorySizeViewer.__init__ called")
        self.setWindowTitle("Directory Size Viewer")
        self.setGeometry(100, 100, 800, 600)
        self.worker = None
        self.worker_thread = None
        self.last_directory = os.getcwd()  # 最後に選択したディレクトリ
        self.init_ui()

    def init_ui(self):
        print("DirectorySizeViewer.init_ui() called")
        # レイアウト
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # パス入力欄と参照ボタン
        path_layout = QHBoxLayout()
        self.path_label = QLabel("Path:")
        self.path_entry = QLineEdit()
        self.path_entry.setText(self.last_directory)
        self.path_entry.returnPressed.connect(self.scan_directory)  # Enterキーで実行
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_directory)
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_entry)
        path_layout.addWidget(self.browse_button)
        main_layout.addLayout(path_layout)

        # 実行ボタン
        self.execute_button = QPushButton("Get Size")
        self.execute_button.clicked.connect(self.scan_directory)
        main_layout.addWidget(self.execute_button)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # くるくる回る indeterminate モード
        self.progress_bar.hide()  # 最初は隠しておく
        main_layout.addWidget(self.progress_bar)

        # ツリービュー
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(False)  # ヘッダーを表示
        self.tree_view.setSortingEnabled(True)
        # self.tree_view.clicked.connect(self.on_tree_clicked)  # 一旦コメントアウト

        # ファイルシステムモデル (QFileSystemModel は使わない)
        self.model = None  # 後で設定
        # self.tree_view.setModel(self.model)

        # ヘッダー設定
        self.tree_view.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )  # 名前列を自動でリサイズ
        self.tree_view.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )  # サイズ列は手動でリサイズ可
        self.tree_view.header().resizeSection(1, 150)  # サイズ列の初期幅

        main_layout.addWidget(self.tree_view)

    def browse_directory(self):
        directory = str(
            QFileDialog.getExistingDirectory(
                self,
                "Select Directory",
                self.last_directory,  # 前回のディレクトリを開く
            )
        )
        if directory:
            self.last_directory = directory
            self.path_entry.setText(directory)

    def scan_directory(self):
        print("DirectorySizeViewer.scan_directory() called")
        path = self.path_entry.text().strip()  # 空白を除去

        # パスの検証
        if not path:
            QMessageBox.warning(self, "Warning", "Please enter a directory path")
            return

        if not os.path.exists(path):
            QMessageBox.critical(self, "Error", f"Path does not exist: {path}")
            return

        if not os.path.isdir(path):
            QMessageBox.critical(self, "Error", f"Not a directory: {path}")
            return

        self.progress_bar.show()
        self.execute_button.setEnabled(False)

        # 既存のモデルがあれば削除
        if self.model:
            self.tree_view.setModel(None)
            self.model = None

        # 新しいモデルを作成
        self.model = QStandardItemModel()
        self.model.setColumnCount(2)
        self.model.setHorizontalHeaderLabels(["Name", "Size"])
        self.tree_view.setModel(self.model)

        # ワーカーオブジェクトとスレッドを作成
        self.worker = Worker(path)
        self.worker_thread = QThread()

        # ワーカーをスレッドに移動
        self.worker.moveToThread(self.worker_thread)

        # シグナルとスロットを接続
        self.worker_thread.started.connect(self.worker.run)
        self.worker.scan_complete.connect(self.add_item_to_tree)
        self.worker.scan_error.connect(self.handle_error)
        self.worker.finished.connect(self.scan_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        # スレッドを開始
        self.worker_thread.start()

    def add_item_to_tree(self, name, size, path):
        item = QStandardItem(name)
        size_item = SizeItem(self.format_size(size), size)  # 生のサイズも保持
        item.setData(path, Qt.ItemDataRole.UserRole + 1)
        self.model.appendRow([item, size_item])

    def format_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def handle_error(self, error_type, error_message):
        QMessageBox.critical(self, "Error", f"{error_type}: {error_message}")
        self.progress_bar.hide()
        self.execute_button.setEnabled(True)

    def scan_finished(self):
        print("DirectorySizeViewer.scan_finished() called")
        self.progress_bar.hide()
        self.execute_button.setEnabled(True)


if __name__ == "__main__":
    print("__main__ block started")
    try:
        app = QApplication(sys.argv)
        print("QApplication object created")
        viewer = DirectorySizeViewer()
        print("DirectorySizeViewer object created")
        viewer.show()
        print("Window shown")
        print(f"Window visible: {viewer.isVisible()}")
        sys.exit(app.exec())
    except Exception as e:
        print(f"An error occurred: {e}")
        raise  # エラーの詳細を表示
    except KeyboardInterrupt:
        print("KeyboardInterrupt: Program terminated by user")
        sys.exit(1)
