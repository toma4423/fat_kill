import sys
import os
import time
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QProgressBar,
    QLineEdit,
    QHBoxLayout,
    QFileDialog,
)
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject

import rust_lib


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str, str)  # エラー種別, メッセージ
    result = pyqtSignal(str, int)  # パス, サイズ
    progress = pyqtSignal(int, int)  # 処理済みファイル数, 合計ファイル数
    current_file = pyqtSignal(str)  # 現在処理中のファイル


class DirSizeWorker(QRunnable):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.signals = WorkerSignals()
        self.is_cancelled = False
        self.update_interval = 100  # 進捗更新の間隔（ファイル数）

    def run(self):
        try:
            total_files = sum(len(files) for _, _, files in os.walk(self.path))
            processed_files = 0
            last_update = 0

            for root, _, files in os.walk(self.path):
                if self.is_cancelled:
                    return

                processed_files += len(files)

                # 一定間隔でのみUIを更新
                if processed_files - last_update >= self.update_interval:
                    self.signals.current_file.emit(root)
                    self.signals.progress.emit(processed_files, total_files)
                    last_update = processed_files

            # 最終的なサイズ計算は一度だけ
            if not self.is_cancelled:
                size = rust_lib.get_dir_size_py(self.path)
                self.signals.result.emit(self.path, size)
                # 最終進捗更新
                self.signals.progress.emit(total_files, total_files)

        except OSError as e:
            self.signals.error.emit("OSError", str(e))
        except Exception as e:
            self.signals.error.emit("Error", str(e))
        finally:
            self.signals.finished.emit()

    def cancel(self):
        self.is_cancelled = True


class ProgressTest(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.current_worker = None
        print(f"Maximum thread count: {self.threadpool.maxThreadCount()}")
        self.last_directory = os.getcwd()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Progress Test")
        self.setGeometry(100, 100, 800, 400)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # パス入力部分
        path_layout = QHBoxLayout()
        self.path_entry = QLineEdit(self.last_directory)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_directory)
        path_layout.addWidget(self.path_entry)
        path_layout.addWidget(self.browse_button)
        layout.addLayout(path_layout)

        # 実行ボタンとキャンセルボタン
        button_layout = QHBoxLayout()
        self.scan_button = QPushButton("Scan Directory")
        self.scan_button.clicked.connect(self.start_scan)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_scan)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.scan_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # 進捗状況表示
        self.status_label = QLabel("Ready")
        self.current_file_label = QLabel("")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()

        layout.addWidget(self.status_label)
        layout.addWidget(self.current_file_label)
        layout.addWidget(self.progress)

        # 結果表示
        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

    def browse_directory(self):
        directory = str(
            QFileDialog.getExistingDirectory(
                self,
                "Select Directory",
                self.last_directory,
            )
        )
        if directory:
            self.last_directory = directory
            self.path_entry.setText(directory)

    def start_scan(self):
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
        self.progress.show()
        self.status_label.setText("Scanning...")
        self.result_label.setText("")

        worker = DirSizeWorker(path)
        self.current_worker = worker

        worker.signals.result.connect(self.handle_result)
        worker.signals.error.connect(self.handle_error)
        worker.signals.finished.connect(self.scan_complete)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.current_file.connect(self.update_current_file)

        self.threadpool.start(worker)

    def cancel_scan(self):
        if self.current_worker:
            self.current_worker.cancel()
            self.status_label.setText("Cancelling...")
            self.cancel_button.setEnabled(False)

    def handle_result(self, path, size):
        size_str = self.format_size(size)
        self.result_label.setText(f"Size of {path}: {size_str}")

    def handle_error(self, error_type, message):
        self.status_label.setText(f"{error_type}: {message}")
        self.scan_complete()

    def update_progress(self, current, total):
        percentage = (current * 100) // total
        self.progress.setValue(percentage)
        self.status_label.setText(
            f"Processing: {current}/{total} files ({percentage}%)"
        )

    def update_current_file(self, path):
        self.current_file_label.setText(f"Current: {path}")

    def scan_complete(self):
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.current_worker = None
        self.status_label.setText("Scan completed")
        self.current_file_label.setText("")

    def format_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProgressTest()
    window.show()
    sys.exit(app.exec())
