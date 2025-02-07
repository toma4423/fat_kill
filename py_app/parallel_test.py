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
    error = pyqtSignal(str, str)
    result = pyqtSignal(str, int)
    progress = pyqtSignal(int, int)
    current_file = pyqtSignal(str)


class ParallelDirSizeWorker(QRunnable):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.signals = WorkerSignals()
        self.is_cancelled = False

    def run(self):
        try:
            total_files = 0
            # 主要なサブディレクトリのみを並列処理
            dirs_to_process = self.get_subdirs(self.path)

            # 全ファイル数を計算
            for root, _, files in os.walk(self.path):
                if self.is_cancelled:
                    return
                total_files += len(files)

            processed_files = 0
            last_update = 0

            # Rustに一括で処理を依頼
            try:
                size = rust_lib.get_dir_size_py(self.path)
                self.signals.result.emit(self.path, size)
                self.signals.progress.emit(total_files, total_files)  # 完了を通知
            except Exception as e:
                self.signals.error.emit("Error", str(e))

        except Exception as e:
            self.signals.error.emit("Error", str(e))
        finally:
            self.signals.finished.emit()

    def cancel(self):
        self.is_cancelled = True


class ParallelTest(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        print(f"Maximum thread count: {self.threadpool.maxThreadCount()}")
        self.last_directory = os.getcwd()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Parallel Processing Test")
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

        # ボタン
        button_layout = QHBoxLayout()
        self.scan_button = QPushButton("Scan Directory")
        self.scan_button.clicked.connect(self.start_scan)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_scan)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.scan_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # 状態表示
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

        worker = ParallelDirSizeWorker(path)

        worker.signals.result.connect(self.handle_result)
        worker.signals.error.connect(self.handle_error)
        worker.signals.finished.connect(self.scan_complete)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.current_file.connect(self.update_current_file)

        self.current_worker = worker
        self.threadpool.start(worker)

    def cancel_scan(self):
        if hasattr(self, "current_worker"):
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
        if hasattr(self, "current_worker"):
            delattr(self, "current_worker")
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
    window = ParallelTest()
    window.show()
    sys.exit(app.exec())
