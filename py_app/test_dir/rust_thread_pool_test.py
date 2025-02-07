import sys
import os
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


class DirSizeWorker(QRunnable):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.signals = WorkerSignals()

    def run(self):
        try:
            size = rust_lib.get_dir_size_py(self.path)
            self.signals.result.emit(self.path, size)
        except OSError as e:
            self.signals.error.emit("OSError", str(e))
        except Exception as e:
            self.signals.error.emit("Error", str(e))
        finally:
            self.signals.finished.emit()


class RustThreadPoolTest(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        print(f"Maximum thread count: {self.threadpool.maxThreadCount()}")
        self.last_directory = os.getcwd()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Rust ThreadPool Test")
        self.setGeometry(100, 100, 600, 200)

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

        # 実行ボタンとラベル
        self.label = QLabel("Ready")
        self.scan_button = QPushButton("Scan Directory")
        self.scan_button.clicked.connect(self.start_scan)

        # プログレスバー
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        layout.addWidget(self.label)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.progress)

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
            self.label.setText("Error: No path specified")
            return

        if not os.path.exists(path):
            self.label.setText("Error: Path does not exist")
            return

        if not os.path.isdir(path):
            self.label.setText("Error: Not a directory")
            return

        self.scan_button.setEnabled(False)
        self.progress.show()
        self.label.setText("Scanning...")

        worker = DirSizeWorker(path)
        worker.signals.result.connect(self.handle_result)
        worker.signals.error.connect(self.handle_error)
        worker.signals.finished.connect(self.scan_complete)

        self.threadpool.start(worker)

    def handle_result(self, path, size):
        size_str = self.format_size(size)
        self.label.setText(f"Size of {path}: {size_str}")

    def handle_error(self, error_type, message):
        self.label.setText(f"{error_type}: {message}")

    def scan_complete(self):
        self.progress.hide()
        self.scan_button.setEnabled(True)

    def format_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RustThreadPoolTest()
    window.show()
    sys.exit(app.exec())
