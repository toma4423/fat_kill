import sys
from PyQt6.QtWidgets import QApplication
from rust_ui import MainWindow
from rust_dir_info import get_directory_info, get_directory_tree


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
