import sys
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QProgressBar,
)
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(str(result))
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class ThreadPoolTest(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        print(f"Maximum thread count: {self.threadpool.maxThreadCount()}")
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("ThreadPool Test")
        self.setGeometry(100, 100, 400, 200)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # テスト用のボタンとラベル
        self.label = QLabel("Ready")
        self.button = QPushButton("Start Test")
        self.button.clicked.connect(self.start_task)

        # プログレスバー
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        layout.addWidget(self.label)
        layout.addWidget(self.button)
        layout.addWidget(self.progress)

    def start_task(self):
        self.button.setEnabled(False)
        self.progress.show()

        # テスト用の重い処理
        def heavy_task():
            import time

            time.sleep(3)  # 3秒間のスリープで重い処理をシミュレート
            return "Task completed"

        worker = Worker(heavy_task)
        worker.signals.result.connect(self.handle_result)
        worker.signals.error.connect(self.handle_error)
        worker.signals.finished.connect(self.task_complete)

        self.threadpool.start(worker)

    def handle_result(self, result):
        self.label.setText(result)

    def handle_error(self, error):
        self.label.setText(f"Error: {error}")

    def task_complete(self):
        self.progress.hide()
        self.button.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ThreadPoolTest()
    window.show()
    sys.exit(app.exec())
