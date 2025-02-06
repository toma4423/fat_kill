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
    QTreeView,
    QHeaderView,
    QProgressBar,
    QFileDialog,
)
from PyQt6.QtGui import QFileSystemModel, QStandardItemModel, QStandardItem
from PyQt6.QtCore import QSize, QDir, Qt, QThread, pyqtSignal
import rust_lib  # Rust ライブラリをインポート

print("Rust lib imported successfully")  # デバッグ出力


class DirectoryScanner(QThread):
    scan_complete = pyqtSignal(str, int, str)  # シグナル (名前, サイズ, パス)
    scan_error = pyqtSignal(str)  # エラーシグナル
    finished = pyqtSignal()

    def __init__(self, path):
        super().__init__()
        self.path = path
        print(f"DirectoryScanner initialized with path: {path}")  # デバッグ出力

    def run(self):
        print("DirectoryScanner.run() started")  # デバッグ出力
        try:
            size = rust_lib.get_dir_size_py(self.path)
            self.scan_complete.emit(os.path.basename(self.path), size, self.path)
        except OSError as e:
            self.scan_error.emit(str(e))
        finally:
            self.finished.emit()
        print("DirectoryScanner.run() finished")  # デバッグ出力


class DirectorySizeViewer(QWidget):
    def __init__(self):
        super().__init__()
        print("DirectorySizeViewer.__init__ called")  # デバッグ出力

        self.setWindowTitle("Directory Size Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.init_ui()

    def init_ui(self):
        print("DirectorySizeViewer.init_ui() called")  # デバッグ出力
        # レイアウト
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # パス入力欄と参照ボタン
        path_layout = QHBoxLayout()
        self.path_label = QLabel("Path:")
        self.path_entry = QLineEdit()
        self.path_entry.setText(os.getcwd())  # カレントディレクトリをデフォルトに
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_directory)
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_entry)
        path_layout.addWidget(self.browse_button)
        main_layout.addLayout(path_layout)

        # 実行ボタン
        self.execute_button = QPushButton("Execute")
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
        self.tree_view.clicked.connect(self.on_tree_clicked)  # クリックイベント

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
        directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        if directory:
            self.path_entry.setText(directory)

    def scan_directory(self):
        print("DirectorySizeViewer.scan_directory() called")  # デバッグ出力
        path = self.path_entry.text()
        if not os.path.exists(path):
            # エラー処理 (QMessageBox などを使うと良い)
            print(f"Error: Path does not exist - {path}")
            return

        self.progress_bar.show()
        self.execute_button.setEnabled(False)

        # 既存のモデルがあれば削除
        if self.model:
            self.tree_view.setModel(None)  # 接続解除
            self.model = None

        # 新しいモデルを作成
        self.model = QStandardItemModel()
        self.model.setColumnCount(2)
        self.model.setHorizontalHeaderLabels(["Name", "Size"])
        self.tree_view.setModel(self.model)

        self.scanner = DirectoryScanner(path)
        self.scanner.scan_complete.connect(self.add_item_to_tree)
        self.scanner.scan_error.connect(self.handle_error)
        self.scanner.finished.connect(self.scan_finished)
        self.scanner.start()

    def add_item_to_tree(self, name, size, path):
        print("DirectorySizeViewer.add_item_to_tree() called")  # デバッグ出力
        item = QStandardItem(name)
        size_item = QStandardItem(self.format_size(size))
        item.setData(path, Qt.ItemDataRole.UserRole + 1)  # パスをデータとして保持
        self.model.appendRow([item, size_item])

        # サブディレクトリをスキャン (必要に応じて)
        if os.path.isdir(path):
            # ここでさらにスレッドを作成してサブディレクトリをスキャン
            pass

    def on_tree_clicked(self, index):
        print("DirectorySizeViewer.on_tree_clicked() called")  # デバッグ出力
        item = self.model.itemFromIndex(index)
        if item:
            path = item.data(Qt.ItemDataRole.UserRole + 1)
            print(path)
            if os.path.isdir(path):
                sub_scanner = DirectoryScanner(path)
                sub_scanner.scan_complete.connect(self.add_item_to_tree)
                sub_scanner.scan_error.connect(self.handle_error)
                sub_scanner.finished.connect(self.scan_finished)
                sub_scanner.start()

    def handle_error(self, error_message):
        # エラー処理 (QMessageBox などを使うと良い)
        print(f"Error: {error_message}")
        self.progress_bar.hide()
        self.execute_button.setEnabled(True)

    def scan_finished(self):
        print("DirectorySizeViewer.scan_finished() called")  # デバッグ出力
        self.progress_bar.hide()
        self.execute_button.setEnabled(True)

    def format_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


if __name__ == "__main__":
    print("__main__ block started")  # デバッグ出力
    app = QApplication(sys.argv)
    viewer = DirectorySizeViewer()
    viewer.show()
    try:
        sys.exit(app.exec())
    except Exception as e:
        print(f"An error occurred: {e}")
