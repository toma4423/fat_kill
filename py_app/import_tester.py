from PyQt6.QtCore import QT_VERSION_STR, QLibraryInfo
from PyQt6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)  # 追加

print(f"Qt version: {QT_VERSION_STR}")
print(f"Qt paths: {QLibraryInfo.path()}")
