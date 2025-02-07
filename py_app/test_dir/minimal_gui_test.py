import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel


class MinimalViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minimal Test")
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel("Test Window")
        button = QPushButton("Test Button")
        button.clicked.connect(lambda: print("Button clicked"))

        layout.addWidget(label)
        layout.addWidget(button)


if __name__ == "__main__":
    print("Starting minimal test...")
    try:
        app = QApplication(sys.argv)
        print("QApplication created")
        window = MinimalViewer()
        print("Window created")
        window.show()
        print("Window shown")
        print(f"Window visible: {window.isVisible()}")
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error: {e}")
        raise
