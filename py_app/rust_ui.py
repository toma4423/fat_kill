from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
    QTreeWidget,
    QTreeWidgetItem,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor
from rust_dir_info import get_directory_tree
import os
import threading
import time


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Directory Tree Viewer")
        self.resize(800, 600)
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout()

        # 上部：選択されたディレクトリパスと操作ボタン
        top_layout = QHBoxLayout()

        self.dir_line_edit = QLineEdit()
        self.dir_line_edit.setReadOnly(True)
        self.dir_line_edit.setPlaceholderText("選択されたディレクトリパス")
        top_layout.addWidget(self.dir_line_edit, 4)

        self.btn_select_directory = QPushButton("ディレクトリ選択")
        self.btn_select_directory.clicked.connect(self.on_select_directory)
        top_layout.addWidget(self.btn_select_directory, 1)

        self.btn_scan_start = QPushButton("スキャン実行")
        self.btn_scan_start.clicked.connect(self.on_scan_start)
        top_layout.addWidget(self.btn_scan_start, 1)

        self.btn_scan_stop = QPushButton("スキャン停止")
        self.btn_scan_stop.clicked.connect(self.on_scan_stop)
        top_layout.addWidget(self.btn_scan_stop, 1)

        layout.addLayout(top_layout)

        # スキャン中のステータス表示ラベル（初期状態は空）
        self.scan_status_label = QLabel("")
        layout.addWidget(self.scan_status_label)

        # ツリー表示用ウィジェット（名前, サイズ）
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["名前", "サイズ"])
        self.tree_widget.setSortingEnabled(True)
        layout.addWidget(self.tree_widget)

        # スキャン所要時間表示ラベル（初期状態は空）
        self.scan_duration_label = QLabel("")
        layout.addWidget(self.scan_duration_label)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def on_select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "ディレクトリを選択")
        if directory:
            self.dir_line_edit.setText(directory)

    def on_scan_start(self):
        directory = self.dir_line_edit.text()
        if directory:
            # スキャン開始時の時刻を記録
            self._start_time = time.perf_counter()
            # スキャン開始時のステータス表示
            self.scan_status_label.setText("スキャン中...")
            self._cancel_event = threading.Event()
            self._scanner_thread = QThread()
            self._scanner_worker = ScannerWorker(directory, self._cancel_event)
            self._scanner_worker.moveToThread(self._scanner_thread)
            self._scanner_thread.started.connect(self._scanner_worker.run)
            self._scanner_worker.finished.connect(self.on_scan_finished)
            self._scanner_worker.finished.connect(self._scanner_thread.quit)
            self._scanner_worker.finished.connect(self._scanner_worker.deleteLater)
            self._scanner_thread.finished.connect(self._scanner_thread.deleteLater)
            self._scanner_thread.start()

    def on_scan_stop(self):
        if hasattr(self, "_cancel_event"):
            self._cancel_event.set()

    def populate_tree_with_data(self, tree_data):
        self.tree_widget.clear()
        if tree_data is None:
            # キャンセルされた場合は、結果を表示しない
            return
        root_item = self.build_tree_item(tree_data)
        root_item.setExpanded(False)
        self.tree_widget.addTopLevelItem(root_item)

    def on_scan_finished(self, tree_data):
        self.populate_tree_with_data(tree_data)
        # スキャン終了後、ステータスをクリア
        self.scan_status_label.setText("")
        # 経過時間を計算して所要時間表示ラベルに更新
        if hasattr(self, "_start_time"):
            elapsed = time.perf_counter() - self._start_time
            self.scan_duration_label.setText(f"スキャン所要時間: {elapsed:.2f} 秒")
        else:
            self.scan_duration_label.setText("スキャン所要時間: 0.00 秒")

        # エラー情報があれば警告ダイアログで表示
        if tree_data is not None and tree_data.get("error"):
            QMessageBox.warning(
                self,
                "スキャンエラー",
                f"スキャン中にエラーが発生しました:\n{tree_data.get('error')}",
            )

    class CustomTreeWidgetItem(QTreeWidgetItem):
        """
        独自のソート順を実現するための QTreeWidgetItem のサブクラス
        各項目には、ユーザデータ (Qt.UserRole) にタイプコードを設定し、
        タイプコードが低いものを優先してソートする。
        """

        def __lt__(self, other):
            column = self.treeWidget().sortColumn()
            if column == 1:
                # サイズ列：生の数値データを使って比較
                my_size = self.data(1, Qt.ItemDataRole.UserRole)
                other_size = other.data(1, Qt.ItemDataRole.UserRole)
                if my_size is not None and other_size is not None:
                    return my_size < other_size
                else:
                    return self.text(1) < other.text(1)
            else:
                # 名前列：まずタイプコードで比較
                my_order = self.data(0, Qt.ItemDataRole.UserRole)
                other_order = other.data(0, Qt.ItemDataRole.UserRole)
                if my_order is not None and other_order is not None:
                    if my_order != other_order:
                        return my_order < other_order
                return self.text(0) < other.text(0)

    def build_tree_item(self, data: dict) -> CustomTreeWidgetItem:
        if data.get("accessible", True):
            raw_size = data.get("size", 0)
            size_text = self.human_readable_size(raw_size)
            type_code = 0  # 通常フォルダ
        else:
            size_text = "アクセス不可"
            raw_size = 0
            type_code = 2  # アクセス不可

        # もしアクセス可能かつ隠しの場合は、タイプコード 1 に変更
        if data.get("accessible", True) and data.get("hidden", False):
            type_code = 1  # 隠しフォルダ

        item = self.CustomTreeWidgetItem([data["name"], size_text])
        item.setData(0, Qt.ItemDataRole.UserRole, type_code)
        # 列 1 には生のサイズ情報を設定しておく (ソート用)
        item.setData(1, Qt.ItemDataRole.UserRole, raw_size)

        # アクセス不可の場合は赤字、隠しの場合はグレーに設定
        if not data.get("accessible", True):
            item.setForeground(0, QBrush(QColor("red")))
            item.setForeground(1, QBrush(QColor("red")))
        elif data.get("hidden", False):
            item.setForeground(0, QBrush(QColor("gray")))
            item.setForeground(1, QBrush(QColor("gray")))

        for child in data.get("children", []):
            child_item = self.build_tree_item(child)
            item.addChild(child_item)
        return item

    def human_readable_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024 or unit == "TB":
                return f"{size:.2f} {unit}"
            size /= 1024


class ScannerWorker(QObject):
    # finished シグナルは、スキャン結果 (tree_data) を返します。キャンセル時は None を返す想定です。
    finished = pyqtSignal(object)

    def __init__(self, directory, cancel_event, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.cancel_event = cancel_event

    @pyqtSlot()
    def run(self):
        from directory_info import get_directory_tree

        try:
            # get_directory_tree は cancel_event を受け付け、定期的にチェックするものとします。
            tree_data = get_directory_tree(self.directory, self.cancel_event)
        except Exception as e:
            tree_data = {
                "name": self.directory,
                "size": 0,
                "children": [],
                "accessible": False,
                "hidden": False,
                "error": str(e),
            }
        self.finished.emit(tree_data)
