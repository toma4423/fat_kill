import sys
from PyQt6.QtWidgets import QApplication
from ui import MainWindow
from directory_info import get_directory_info


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # 例: ディレクトリ情報の取得（動作確認用）
    # directory_path = "C:/path/to/check"   # 適宜変更してください
    # info = get_directory_info(directory_path)
    # print("ディレクトリ情報:", info)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
