import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtCore import QT_VERSION_STR, QLibraryInfo

print(f"Qt version: {QT_VERSION_STR}")
# print(f"Qt paths: {QLibraryInfo.path()}") # これはエラーになるので修正
print(f"Qt PrefixPath: {QLibraryInfo.path(QLibraryInfo.LibraryPath.PrefixPath)}")

app = QApplication(sys.argv)
window = QWidget()
label = QLabel("Hello, PyQt6!")
label.show()
window.show()
sys.exit(app.exec())
