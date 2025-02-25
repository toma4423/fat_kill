"""
ディレクトリサイズ表示アプリケーション

このアプリケーションは、選択したディレクトリのサイズを計算し、
サブディレクトリごとのサイズをツリービュー形式で表示します。
Rustライブラリを使用して高速な計算を実現しています。
オンラインストレージ対策として、タイムアウト機能とネットワークドライブ検出・スキップ機能を備えています。
"""

import os
import sys
import time
import threading
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable, Any

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFileDialog,
    QProgressBar,
    QTreeView,
    QMessageBox,
    QStatusBar,
    QCheckBox,
    QSpinBox,
    QGroupBox,
    QFormLayout,
    QDialog,
    QDialogButtonBox,
)
from PyQt6.QtCore import (
    Qt,
    QObject,
    QRunnable,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
    QModelIndex,
    QSize,
    QTimer,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem

# Rustライブラリのインポート
try:
    import rust_lib

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    print("警告: Rustライブラリが見つかりません。Pythonの実装を使用します。")


class WorkerSignals(QObject):
    """ワーカースレッドからのシグナルを定義するクラス"""

    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(str, int)
    warning = pyqtSignal(str)


class DirectorySizeWorker(QRunnable):
    """ディレクトリサイズ計算を行うワーカークラス"""

    def __init__(self, directory: str, options: dict):
        """ワーカーの初期化"""
        super().__init__()
        self.directory = directory
        self.options = options
        self.signals = WorkerSignals()
        self.is_cancelled = False
        self.last_progress_time = time.time()

        # キャンセルフラグの作成（Rust実装の場合）
        if RUST_AVAILABLE:
            self.cancel_ptr = rust_lib.create_cancel_flag()
        else:
            self.cancel_ptr = None

    def cancel(self):
        """処理のキャンセル"""
        self.is_cancelled = True
        if RUST_AVAILABLE and self.cancel_ptr is not None:
            rust_lib.set_cancel_flag(self.cancel_ptr, True)

    @pyqtSlot()
    def run(self):
        """ディレクトリサイズの計算を実行"""
        try:
            # ネットワークドライブのチェック
            if self.is_network_drive(self.directory):
                if self.options.get("skip_network", True):  # デフォルトでスキップする
                    self.signals.warning.emit(
                        f"警告: {self.directory} はネットワークドライブまたはオンラインストレージのため、スキップします。"
                    )
                    # ネットワークドライブ用の結果を作成
                    result = {
                        "total_size": 0,
                        "dir_structure": {
                            "path": self.directory,
                            "size": 0,
                            "children": [],
                            "network_drive": True,
                        },
                        "elapsed_time": 0,
                    }
                    self.signals.result.emit(result)
                    return
                else:
                    self.signals.warning.emit(
                        "警告: ネットワークドライブまたはオンラインストレージが検出されました。処理に時間がかかる場合があります。"
                    )

            start_time = time.time()

            if RUST_AVAILABLE:
                # Rust実装を使用
                try:
                    # 進捗コールバック関数
                    def progress_callback(path, size):
                        self.last_progress_time = time.time()
                        self.signals.progress.emit(path, size)

                    # Rustライブラリを使用してディレクトリサイズを計算
                    total_size, has_access_denied = (
                        rust_lib.get_dir_size_with_cancel_py(
                            self.directory, self.cancel_ptr, progress_callback
                        )
                    )

                    # ディレクトリ構造とサイズを取得
                    dir_structure = self.get_directory_structure(self.directory, 0)

                    # アクセス拒否フラグを設定
                    dir_structure["has_access_denied"] = has_access_denied

                except Exception as e:
                    if "キャンセルされました" in str(e):
                        self.signals.error.emit("処理がキャンセルされました")
                    else:
                        self.signals.error.emit(f"エラー: {e}")
                    return
            else:
                # Python実装を使用
                try:
                    total_size, dir_structure = self.get_directory_size_py(
                        self.directory
                    )
                except Exception as e:
                    self.signals.error.emit(f"エラー: {e}")
                    return

            elapsed_time = time.time() - start_time

            # 結果を返す
            result = {
                "total_size": total_size,
                "dir_structure": dir_structure,
                "elapsed_time": elapsed_time,
                "has_access_denied": dir_structure.get("has_access_denied", False),
            }
            self.signals.result.emit(result)

        except Exception as e:
            self.signals.error.emit(f"予期せぬエラー: {e}")
        finally:
            # キャンセルフラグの解放（Rust実装の場合）
            if RUST_AVAILABLE and self.cancel_ptr is not None:
                rust_lib.release_cancel_flag(self.cancel_ptr)
                self.cancel_ptr = None

            self.signals.finished.emit()

    def is_network_drive(self, path):
        """ネットワークドライブまたはオンラインストレージかどうかを判定"""
        # Windowsのネットワークドライブパターン (UNCパス)
        if re.match(r"^\\\\", path):
            return True

        # マウントされたネットワークドライブ
        if sys.platform == "win32":
            # Windowsの場合
            drive_letter = os.path.splitdrive(path)[0]
            if drive_letter:
                try:
                    import win32file

                    drive_type = win32file.GetDriveType(drive_letter)
                    return drive_type == win32file.DRIVE_REMOTE
                except ImportError:
                    # win32fileがない場合は簡易チェック
                    pass

        # オンラインストレージの詳細なパターンチェック
        # BoxDriveの検出強化
        box_patterns = [
            r"\\Box\\",
            r"/Box/",
            r"\\BoxSync\\",
            r"/BoxSync/",
            r"\\Box Sync\\",
            r"/Box Sync/",
            r"\\BoxDrive\\",
            r"/BoxDrive/",
            r"\\Box Drive\\",
            r"/Box Drive/",
        ]
        for pattern in box_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return True

        # その他のクラウドストレージサービス
        cloud_storage_patterns = [
            # OneDrive
            r"\\OneDrive\\",
            r"/OneDrive/",
            r"\\OneDrive - ",
            r"/OneDrive - ",
            # Dropbox
            r"\\Dropbox\\",
            r"/Dropbox/",
            # Google Drive
            r"\\Google Drive\\",
            r"/Google Drive/",
            r"\\GoogleDrive\\",
            r"/GoogleDrive/",
            r"\\Google ドライブ\\",
            r"/Google ドライブ/",
            # iCloud
            r"\\iCloud Drive\\",
            r"/iCloud Drive/",
            r"\\iCloudDrive\\",
            r"/iCloudDrive/",
            # その他の一般的なクラウドストレージ
            r"\\pCloud\\",
            r"/pCloud/",
            r"\\MEGA\\",
            r"/MEGA/",
            r"\\Nextcloud\\",
            r"/Nextcloud/",
            r"\\ownCloud\\",
            r"/ownCloud/",
        ]

        for pattern in cloud_storage_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return True

        # 特定のパスパターンを持つが、ローカルディレクトリである可能性のあるケースを除外
        # 例: "C:\Users\username\Documents\Box" はBoxという名前のローカルフォルダかもしれない
        # この場合、完全なパスパターンでマッチしない限り、クラウドストレージとは判定しない

        # 単純な名前のみのチェックは行わない（誤検出防止）
        # 以前の実装:
        # online_storage_patterns = ["OneDrive", "Dropbox", "Google Drive", "Box", "iCloud Drive"]
        # for pattern in online_storage_patterns:
        #     if re.search(pattern, path, re.IGNORECASE):
        #         return True

        return False

    def get_directory_structure(self, directory, depth=0):
        """ディレクトリ構造を再帰的に取得（深さ制限付き）"""
        result = {
            "path": directory,
            "size": 0,
            "children": [],
            "has_access_denied": False,
        }

        # ネットワークドライブのチェック
        if self.options.get("skip_network", True) and self.is_network_drive(directory):
            result["network_drive"] = True
            result["size"] = 0
            return result

        # 深さ制限のチェック
        max_depth = self.options.get("max_depth", 0)
        if max_depth > 0 and depth >= max_depth:
            result["depth_limited"] = True
            return result

        # タイムアウトのチェック
        timeout = self.options.get("timeout", 10)
        current_time = time.time()
        if (
            self.options.get("timeout_enabled", True)
            and current_time - self.last_progress_time > timeout
        ):
            self.signals.warning.emit(
                f"警告: {directory} の処理がタイムアウトしました。スキップします。"
            )
            result["timeout"] = True
            return result

        # ディレクトリサイズの計算
        try:
            # サブディレクトリを取得
            with os.scandir(directory) as entries:
                for entry in entries:
                    # キャンセルチェック
                    if self.is_cancelled:
                        return result

                    # タイムアウトチェック
                    current_time = time.time()
                    if (
                        self.options.get("timeout_enabled", True)
                        and current_time - self.last_progress_time > timeout
                    ):
                        self.signals.warning.emit(
                            f"警告: {directory} の処理がタイムアウトしました。スキップします。"
                        )
                        result["timeout"] = True
                        break

                    if entry.is_dir():
                        # ネットワークドライブのチェック
                        if self.options.get(
                            "skip_network", True
                        ) and self.is_network_drive(entry.path):
                            child = {
                                "path": entry.path,
                                "size": 0,
                                "children": [],
                                "network_drive": True,
                            }
                            result["children"].append(child)
                            continue

                        # 再帰的にサブディレクトリの構造を取得
                        child = self.get_directory_structure(entry.path, depth + 1)
                        result["children"].append(child)
                        result["size"] += child["size"]

                        # アクセス拒否フラグの伝播
                        if child.get("has_access_denied", False) or child.get(
                            "access_denied", False
                        ):
                            result["has_access_denied"] = True
                    else:
                        # ファイルサイズを取得
                        try:
                            file_size = entry.stat().st_size
                            result["size"] += file_size
                        except (PermissionError, OSError):
                            # ファイルアクセスエラーは無視
                            pass

                    # 進捗コールバック
                    self.signals.progress.emit(directory, result["size"])
                    self.last_progress_time = time.time()

        except PermissionError:
            # アクセス拒否の場合
            if self.options.get("skip_access_denied", True):
                result["access_denied"] = True
                result["size"] = 0  # アクセス拒否の場合はサイズを0とする
            else:
                # アクセス拒否をスキップしない場合は、親ディレクトリにフラグを設定
                result["access_denied"] = True
                result["has_access_denied"] = True
                # サイズは0のままで、親ディレクトリの合計には影響しない

        except Exception as e:
            # その他のエラー
            result["error"] = str(e)
            result["size"] = 0

        return result

    def get_directory_size_py(self, directory, report_progress=True):
        """Pythonによるディレクトリサイズ計算（再帰的）"""
        total_size = 0
        dir_structure = {
            "path": directory,
            "size": 0,
            "children": [],
            "has_access_denied": False,
        }

        # ネットワークドライブのチェック
        if self.options.get("skip_network", True) and self.is_network_drive(directory):
            dir_structure["network_drive"] = True
            return 0, dir_structure

        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    # キャンセルチェック
                    if self.is_cancelled:
                        raise Exception("キャンセルされました")

                    # タイムアウトチェック
                    current_time = time.time()
                    if self.options.get(
                        "timeout_enabled", True
                    ) and current_time - self.last_progress_time > self.options.get(
                        "timeout", 10
                    ):
                        dir_structure["timeout"] = True
                        return total_size, dir_structure

                    if entry.is_dir():
                        # サブディレクトリの場合
                        subdir_path = entry.path
                        try:
                            subdir_size, subdir_structure = self.get_directory_size_py(
                                subdir_path, False
                            )
                            dir_structure["children"].append(subdir_structure)
                            total_size += subdir_size

                            # アクセス拒否フラグの伝播
                            if subdir_structure.get(
                                "has_access_denied", False
                            ) or subdir_structure.get("access_denied", False):
                                dir_structure["has_access_denied"] = True
                        except PermissionError:
                            # アクセス拒否の場合
                            if self.options.get("skip_access_denied", True):
                                # アクセス拒否をスキップする場合
                                child = {
                                    "path": subdir_path,
                                    "size": 0,
                                    "children": [],
                                    "access_denied": True,
                                }
                                dir_structure["children"].append(child)
                                dir_structure["has_access_denied"] = True
                            else:
                                # アクセス拒否をスキップしない場合
                                # 親ディレクトリにフラグを設定するが、サイズには影響しない
                                child = {
                                    "path": subdir_path,
                                    "size": 0,
                                    "children": [],
                                    "access_denied": True,
                                }
                                dir_structure["children"].append(child)
                                dir_structure["has_access_denied"] = True
                    else:
                        # ファイルの場合
                        try:
                            file_size = entry.stat().st_size
                            total_size += file_size
                        except (PermissionError, OSError):
                            # ファイルアクセスエラーは無視
                            pass

                    # 進捗報告
                    if report_progress:
                        self.signals.progress.emit(directory, total_size)
                        self.last_progress_time = time.time()

        except PermissionError:
            # アクセス拒否の場合
            if self.options.get("skip_access_denied", True):
                # アクセス拒否をスキップする場合
                dir_structure["access_denied"] = True
                dir_structure["has_access_denied"] = True
                return 0, dir_structure
            else:
                # アクセス拒否をスキップしない場合
                # 親ディレクトリにフラグを設定するが、サイズには影響しない
                dir_structure["access_denied"] = True
                dir_structure["has_access_denied"] = True
                return 0, dir_structure

        dir_structure["size"] = total_size
        return total_size, dir_structure


class SizeItem(QStandardItem):
    """サイズ表示用のカスタムアイテムクラス"""

    def __init__(self, size_bytes):
        """アイテムの初期化"""
        self.size_bytes = size_bytes
        size_str = self.format_size(size_bytes)
        super().__init__(size_str)

    def format_size(self, size_bytes):
        """バイト数を読みやすい形式に変換"""
        if size_bytes == 0:
            return "0 B"

        # アクセス拒否値の場合
        if RUST_AVAILABLE and size_bytes == rust_lib.get_access_denied_value():
            return "アクセス拒否"

        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1

        return f"{size:.2f} {units[i]}"

    def __lt__(self, other):
        """ソート用の比較演算子"""
        if isinstance(other, SizeItem):
            return self.size_bytes < other.size_bytes
        return super().__lt__(other)


class DirectorySizeViewer(QMainWindow):
    """ディレクトリサイズ表示アプリケーションのメインクラス"""

    def __init__(self):
        """アプリケーションの初期化"""
        super().__init__()
        self.setWindowTitle("ディレクトリサイズ表示")
        self.setGeometry(100, 100, 1000, 700)

        # オプションの初期化
        self.options = {
            "timeout_enabled": True,  # タイムアウト機能の有効/無効
            "timeout": 10,  # タイムアウト時間（秒）
            "max_depth": 0,  # 最大深さ（0は無制限）
            "skip_network": True,  # ネットワークドライブをスキップするかどうか
            "skip_box": True,  # Box Driveをスキップするかどうか
            "skip_cloud": True,  # その他のクラウドストレージをスキップするかどうか
            "skip_access_denied": True,  # アクセス拒否ディレクトリをスキップするかどうか
        }

        # スレッドプールの設定
        self.thread_pool = QThreadPool()
        print(f"スレッド数: {self.thread_pool.maxThreadCount()}")

        # 現在のワーカー
        self.current_worker = None

        # タイムアウト監視用タイマー
        self.timeout_timer = QTimer(self)
        self.timeout_timer.timeout.connect(self.check_timeout)
        self.last_progress_time = 0

        # アクセス拒否値の取得
        if RUST_AVAILABLE:
            self.access_denied_value = rust_lib.get_access_denied_value()
        else:
            self.access_denied_value = 2**64 - 1  # u64::MAX

        # UIの設定
        self.setup_ui()

    def setup_ui(self):
        """UIコンポーネントの設定"""
        # メインウィジェット
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # メインレイアウト
        main_layout = QVBoxLayout(main_widget)

        # 上部フレーム（ディレクトリ選択部分）
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # ディレクトリラベル
        dir_label = QLabel("ディレクトリ:")
        top_layout.addWidget(dir_label)

        # ディレクトリ入力欄
        self.dir_entry = QLineEdit()
        top_layout.addWidget(self.dir_entry)

        # 参照ボタン
        self.browse_button = QPushButton("参照")
        self.browse_button.clicked.connect(self.browse_directory)
        top_layout.addWidget(self.browse_button)

        # 解析ボタン
        self.analyze_button = QPushButton("解析")
        self.analyze_button.clicked.connect(self.analyze_directory)
        top_layout.addWidget(self.analyze_button)

        # キャンセルボタン
        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.cancel_button.setEnabled(False)
        top_layout.addWidget(self.cancel_button)

        # オプションボタン
        self.options_button = QPushButton("オプション")
        self.options_button.clicked.connect(self.show_options)
        top_layout.addWidget(self.options_button)

        # ツリービュー
        self.tree_view = QTreeView()
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.tree_view.setMinimumHeight(400)
        main_layout.addWidget(self.tree_view)

        # モデルの設定
        self.model = QStandardItemModel(0, 2)
        self.model.setHorizontalHeaderLabels(["名前", "サイズ"])
        self.tree_view.setModel(self.model)

        # 進捗バー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不確定モード
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ステータスバー
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了")

        # カラム幅の設定
        self.tree_view.setColumnWidth(0, 500)  # 名前
        self.tree_view.setColumnWidth(1, 150)  # サイズ

    def show_options(self):
        """オプション設定ダイアログを表示"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("オプション設定")
        dialog.setMinimumWidth(450)

        # ダイアログのレイアウト
        dialog_layout = QVBoxLayout(dialog)

        # タイムアウト設定
        timeout_group = QGroupBox("タイムアウト設定")
        timeout_layout = QVBoxLayout()
        timeout_group.setLayout(timeout_layout)

        # タイムアウト有効/無効
        timeout_enabled_checkbox = QCheckBox("タイムアウト機能を有効にする")
        timeout_enabled_checkbox.setChecked(self.options.get("timeout_enabled", True))
        timeout_layout.addWidget(timeout_enabled_checkbox)

        # タイムアウト時間設定
        timeout_time_layout = QHBoxLayout()
        timeout_label = QLabel("タイムアウト時間:")
        timeout_spinbox = QSpinBox()
        timeout_spinbox.setRange(1, 60)
        timeout_spinbox.setValue(self.options["timeout"])
        timeout_spinbox.setSuffix(" 秒")
        timeout_spinbox.setEnabled(self.options.get("timeout_enabled", True))
        timeout_time_layout.addWidget(timeout_label)
        timeout_time_layout.addWidget(timeout_spinbox)
        timeout_time_layout.addStretch(1)
        timeout_layout.addLayout(timeout_time_layout)

        # タイムアウト有効/無効の連動
        timeout_enabled_checkbox.toggled.connect(timeout_spinbox.setEnabled)

        # 深さ制限設定
        depth_group = QGroupBox("深さ制限設定")
        depth_layout = QFormLayout()
        depth_group.setLayout(depth_layout)

        depth_spinbox = QSpinBox()
        depth_spinbox.setRange(0, 100)
        depth_spinbox.setValue(self.options["max_depth"])
        depth_spinbox.setSpecialValueText("無制限")
        depth_layout.addRow("最大深さ:", depth_spinbox)

        # スキップ設定
        skip_group = QGroupBox("スキップ設定")
        skip_layout = QVBoxLayout()
        skip_group.setLayout(skip_layout)

        # アクセス拒否ディレクトリのスキップ
        access_denied_checkbox = QCheckBox("アクセス拒否ディレクトリをスキップする")
        access_denied_checkbox.setChecked(self.options.get("skip_access_denied", True))
        skip_layout.addWidget(access_denied_checkbox)

        # ネットワークドライブのスキップ
        network_checkbox = QCheckBox("ネットワークドライブを自動的にスキップする")
        network_checkbox.setChecked(self.options.get("skip_network", True))
        skip_layout.addWidget(network_checkbox)

        # Box Driveのスキップ
        box_checkbox = QCheckBox("Box Driveを自動的にスキップする")
        box_checkbox.setChecked(self.options.get("skip_box", True))
        skip_layout.addWidget(box_checkbox)

        # その他のクラウドストレージのスキップ
        cloud_checkbox = QCheckBox("その他のクラウドストレージを自動的にスキップする")
        cloud_checkbox.setChecked(self.options.get("skip_cloud", True))
        skip_layout.addWidget(cloud_checkbox)

        # レイアウトに追加
        dialog_layout.addWidget(timeout_group)
        dialog_layout.addWidget(depth_group)
        dialog_layout.addWidget(skip_group)

        # ボタンの設定
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)

        # ダイアログの表示
        result = dialog.exec()

        # OKボタンが押された場合、設定を更新
        if result == QDialog.DialogCode.Accepted:
            self.options["timeout_enabled"] = timeout_enabled_checkbox.isChecked()
            self.options["timeout"] = timeout_spinbox.value()
            self.options["max_depth"] = depth_spinbox.value()
            self.options["skip_access_denied"] = access_denied_checkbox.isChecked()
            self.options["skip_network"] = network_checkbox.isChecked()
            self.options["skip_box"] = box_checkbox.isChecked()
            self.options["skip_cloud"] = cloud_checkbox.isChecked()

    def browse_directory(self):
        """ディレクトリ選択ダイアログを表示"""
        directory = QFileDialog.getExistingDirectory(self, "ディレクトリを選択")
        if directory:
            self.dir_entry.setText(directory)

    def analyze_directory(self):
        """ディレクトリの解析を開始"""
        directory = self.dir_entry.text()
        if not directory:
            QMessageBox.warning(self, "警告", "ディレクトリを選択してください")
            return

        if not os.path.isdir(directory):
            QMessageBox.warning(self, "警告", "有効なディレクトリを選択してください")
            return

        # UIの状態を更新
        self.analyze_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.options_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)

        # モデルをクリア
        self.model.removeRows(0, self.model.rowCount())

        # ワーカーの作成と実行
        self.current_worker = DirectorySizeWorker(directory, self.options)
        self.current_worker.signals.result.connect(self.update_tree)
        self.current_worker.signals.error.connect(self.show_error)
        self.current_worker.signals.warning.connect(self.show_warning)
        self.current_worker.signals.finished.connect(self.on_worker_finished)
        self.current_worker.signals.progress.connect(self.update_progress)

        # タイムアウト監視の開始
        self.last_progress_time = time.time()
        self.timeout_timer.start(1000)  # 1秒ごとにチェック

        self.thread_pool.start(self.current_worker)
        self.status_bar.showMessage("解析中...")

    def check_timeout(self):
        """タイムアウトのチェック"""
        if not self.current_worker:
            self.timeout_timer.stop()
            return

        # タイムアウト機能が無効の場合はチェックしない
        if not self.options.get("timeout_enabled", True):
            return

        current_time = time.time()
        if current_time - self.last_progress_time > self.options["timeout"] * 2:
            # タイムアウト時間の2倍経過した場合は強制キャンセル
            self.show_warning(
                f"警告: 処理が長時間応答していません。処理をキャンセルします。"
            )
            self.cancel_analysis()

    def cancel_analysis(self):
        """解析処理をキャンセル"""
        if self.current_worker:
            self.current_worker.cancel()
            self.status_bar.showMessage("キャンセル中...")
            self.timeout_timer.stop()

    def update_tree(self, result):
        """ディレクトリツリーの更新"""
        # 結果の取得
        total_size = result["total_size"]
        dir_structure = result["dir_structure"]
        elapsed_time = result["elapsed_time"]
        has_access_denied = result.get("has_access_denied", False)

        # ルートアイテムの作成
        root_path = dir_structure["path"]
        root_name = os.path.basename(root_path) or root_path

        # アクセス拒否がある場合は表示に追加
        display_name = root_name
        if has_access_denied:
            display_name = f"{root_name} (一部アクセス拒否あり)"

        root_item = QStandardItem(display_name)
        size_item = SizeItem(total_size)

        # モデルにルートアイテムを追加
        self.model.appendRow([root_item, size_item])

        # 子ディレクトリを再帰的に追加
        self.add_directory_to_tree(dir_structure, root_item)

        # ツリーを展開
        self.tree_view.expand(self.model.indexFromItem(root_item))

        # カラムのリサイズ
        self.tree_view.resizeColumnToContents(0)

        # ステータスバーの更新
        if has_access_denied:
            size_mb = total_size / (1024 * 1024)
            status = (
                f"完了 - {size_mb:.2f} MB (一部アクセス拒否あり) - {elapsed_time:.2f}秒"
            )
        else:
            size_mb = total_size / (1024 * 1024)
            status = f"完了 - {size_mb:.2f} MB - {elapsed_time:.2f}秒"

        self.status_bar.showMessage(status)

    def add_directory_to_tree(self, dir_info, parent_item):
        """ディレクトリ情報をツリーに再帰的に追加"""
        # 子ディレクトリを追加
        for child in dir_info.get("children", []):
            dir_path = child["path"]
            dir_name = os.path.basename(dir_path)
            dir_size = child["size"]

            # 特殊状態の表示
            display_name = dir_name
            if child.get("access_denied", False):
                display_name = f"{dir_name} (アクセス拒否)"
            elif child.get("timeout", False):
                display_name = f"{dir_name} (タイムアウト)"
            elif child.get("depth_limited", False):
                display_name = f"{dir_name} (深さ制限)"
            elif child.get("network_drive", False):
                display_name = f"{dir_name} (ネットワークドライブ - スキップ)"
            elif child.get("box_drive", False):
                display_name = f"{dir_name} (Box Drive - スキップ)"
            elif child.get("cloud_storage", False):
                display_name = f"{dir_name} (クラウドストレージ - スキップ)"
            elif child.get("error", False):
                display_name = f"{dir_name} (エラー: {child['error']})"

            name_item = QStandardItem(display_name)
            size_item = SizeItem(dir_size)

            # 親アイテムに追加
            parent_item.appendRow([name_item, size_item])

            # 子ディレクトリがある場合は再帰的に追加
            if child.get("children") and len(child["children"]) > 0:
                self.add_directory_to_tree(child, name_item)

    def update_progress(self, path, size):
        """進捗状況の更新"""
        # 最終進捗時間の更新
        self.last_progress_time = time.time()

        # パスの短縮表示
        short_path = os.path.basename(path)
        size_kb = size / 1024

        # ステータスバーの更新
        self.status_bar.showMessage(f"処理中: {short_path} - {size_kb:.1f} KB")

    def show_error(self, error_message):
        """エラーメッセージの表示"""
        QMessageBox.critical(self, "エラー", error_message)

    def show_warning(self, warning_message):
        """警告メッセージの表示"""
        self.status_bar.showMessage(warning_message)
        print(warning_message)  # コンソールにも出力

    def on_worker_finished(self):
        """ワーカー終了時の処理"""
        # タイムアウト監視の停止
        self.timeout_timer.stop()

        # UIの状態をリセット
        self.analyze_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.options_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.current_worker = None

    def is_network_or_cloud_storage(self, path):
        """ネットワークドライブまたはクラウドストレージかどうかを判定"""
        # 基本的なネットワークドライブチェック
        if self.options.get("skip_network", True):
            # UNCパスまたはマウントされたネットワークドライブ
            if self.is_network_drive_basic(path):
                return True, "network"

        # Box Driveのチェック
        if self.options.get("skip_box", True):
            if self.is_box_drive(path):
                return True, "box"

        # その他のクラウドストレージのチェック
        if self.options.get("skip_cloud", True):
            if self.is_cloud_storage(path):
                return True, "cloud"

        return False, ""

    def is_network_drive_basic(self, path):
        """基本的なネットワークドライブチェック"""
        # UNCパス
        if re.match(r"^\\\\", path):
            return True

        # マウントされたネットワークドライブ
        if sys.platform == "win32":
            drive_letter = os.path.splitdrive(path)[0]
            if drive_letter:
                try:
                    import win32file

                    drive_type = win32file.GetDriveType(drive_letter)
                    return drive_type == win32file.DRIVE_REMOTE
                except ImportError:
                    pass

        return False

    def is_box_drive(self, path):
        """Box Driveかどうかを判定"""
        box_patterns = [
            r"\\Box\\",
            r"/Box/",
            r"\\BoxSync\\",
            r"/BoxSync/",
            r"\\Box Sync\\",
            r"/Box Sync/",
            r"\\BoxDrive\\",
            r"/BoxDrive/",
            r"\\Box Drive\\",
            r"/Box Drive/",
        ]
        for pattern in box_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        return False

    def is_cloud_storage(self, path):
        """その他のクラウドストレージかどうかを判定"""
        cloud_patterns = [
            # OneDrive
            r"\\OneDrive\\",
            r"/OneDrive/",
            r"\\OneDrive - ",
            r"/OneDrive - ",
            # Dropbox
            r"\\Dropbox\\",
            r"/Dropbox/",
            # Google Drive
            r"\\Google Drive\\",
            r"/Google Drive/",
            r"\\GoogleDrive\\",
            r"/GoogleDrive/",
            # iCloud
            r"\\iCloud Drive\\",
            r"/iCloud Drive/",
            r"\\iCloudDrive\\",
            r"/iCloudDrive/",
        ]
        for pattern in cloud_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        return False


def main():
    """アプリケーションのメイン関数"""
    app = QApplication(sys.argv)
    viewer = DirectorySizeViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
