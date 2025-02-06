import os
import tkinter as tk
from tkinter import ttk, filedialog
import threading
from queue import Queue, Empty


def check_dir_access(directory):
    """ディレクトリへのアクセス権をチェック"""
    try:
        # os.listdir を試す
        os.listdir(directory)
        return True
    except PermissionError:
        return False
    except OSError:  # その他のOSErrorもキャッチ
        return False


def get_directory_info_python(path):
    """指定ディレクトリ直下のディレクトリ情報を取得 (修正版)"""
    dir_info = []
    try:
        # os.listdir を使用して直下のディレクトリのみを取得
        for item_name in os.listdir(path):
            item_path = os.path.join(path, item_name)
            if os.path.isdir(item_path) and check_dir_access(item_path):
                dir_size = 0
                has_error = False

                # サブディレクトリも含め、全ファイルのサイズを合計
                try:
                    for root, _, files in os.walk(item_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                dir_size += os.stat(file_path).st_size
                            except OSError:
                                has_error = True  # ファイルにアクセスできない
                except OSError:
                    has_error = True  # ディレクトリ自体にアクセスできない

                dir_info.append(
                    {
                        "Name": item_name,
                        "Path": item_path,
                        "Size": dir_size,
                        "HasError": has_error,
                    }
                )

    except OSError:  # os.listdir でエラー
        return []
    return dir_info


class DirectoryScanner:
    """ディレクトリのスキャンとツリービューの管理を行うクラス"""

    def __init__(self, tree_widget, progress_var):
        self.tree = tree_widget
        self.progress_var = progress_var
        self.scanning = False
        self.queue = Queue()  # UI更新用のキュー
        self.scanned_dirs = {}  # スキャン済みディレクトリ { item_id: dir_info }
        self.sort_column = "size"  # デフォルトのソート列
        self.sort_reverse = True  # デフォルトは降順

    def sort_tree(self, col):
        """ツリービューの項目をソートする"""
        if self.scanning:
            return

        # サイズ列の場合は数値としてソート
        def get_value(item_id):
            try:
                if col == "size":
                    size_str = self.tree.set(item_id, "size")
                    value = float(size_str.split()[0])
                    unit = size_str.split()[1]
                    multiplier = {
                        "B": 1,
                        "KB": 1024,
                        "MB": 1024**2,
                        "GB": 1024**3,
                        "TB": 1024**4,
                        "PB": 1024**5,
                    }
                    return value * multiplier.get(unit, 0)
                else:  # name列の場合
                    return self.tree.item(item_id)["text"].lower()
            except ValueError:  # 数値に変換できなかった場合
                return 0
            except Exception:  # その他のエラー
                return 0

        # 現在のルートレベルのアイテムを取得
        items = list(self.tree.get_children())

        # 同じ列が選択された場合はソート順を反転
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_reverse = False
            self.sort_column = col

        # ソート実行
        items.sort(key=get_value, reverse=self.sort_reverse)

        # ツリービューの項目を並び替え
        for index, item in enumerate(items):
            self.tree.move(item, "", index)

        # ヘッダーの表示を更新
        self.update_header_text()

    def update_header_text(self):
        """ソート状態に合わせてヘッダーテキストを更新"""
        self.tree.heading(
            "#0",
            text="ディレクトリ名"
            + (
                " ▼"
                if self.sort_reverse and self.sort_column == "name"
                else " ▲" if self.sort_column == "name" else ""
            ),
        )
        self.tree.heading(
            "size",
            text="サイズ"
            + (
                " ▼"
                if self.sort_reverse and self.sort_column == "size"
                else " ▲" if self.sort_column == "size" else ""
            ),
        )

    def scan_directory(self, path, parent=""):
        """指定されたパスのディレクトリをスキャンする"""
        if self.scanning:  # 処理中は重複実行しない
            return

        if not os.path.exists(path):
            self.progress_var.set(f"エラー: パスが存在しません - {path}")
            return

        self.scanning = True
        self.progress_var.set("スキャン中...")

        # スレッドでスキャン処理を実行
        thread = threading.Thread(
            target=self._scan_worker, args=(path, parent), daemon=True
        )
        thread.start()

        # UI更新用スレッドを開始
        update_thread = threading.Thread(target=self._update_ui, daemon=True)
        update_thread.start()

    def _scan_worker(self, path, parent):
        """スキャン処理の実体 (ワーカースレッド)"""
        try:
            dir_info = get_directory_info_python(path)  # 修正された関数を使用
            if dir_info:
                self.queue.put(("scan_complete", dir_info, parent))
            else:
                self.queue.put(("error", "ディレクトリ情報の取得に失敗"))

        except Exception as e:
            self.queue.put(("error", str(e)))
        finally:
            self.queue.put(("finished", None))  # スキャン完了を通知

    def _format_size(self, size):
        """サイズを見やすい形式にフォーマット"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def _update_ui(self):
        """UIを更新する (UIスレッド)"""
        while self.scanning:
            try:
                msg_type, data, *args = self.queue.get(timeout=0.1)

                if msg_type == "scan_complete":
                    dir_info, parent = data, args[0]

                    # ルートレベルの更新時はツリーをクリア
                    if parent == "":
                        self.tree.delete(*self.tree.get_children())
                        self.scanned_dirs.clear()  # ルートが更新されたらキャッシュクリア

                    children_item_ids = []  # この親の子要素の item_id を記録
                    for item in dir_info:
                        try:
                            tags = (
                                ("error",) if item.get("HasError") else ("directory",)
                            )
                            size_str = self._format_size(item["Size"])

                            item_id = self.tree.insert(
                                parent,
                                "end",
                                text=item["Name"],
                                values=(size_str, item["Path"]),  # サイズ、パスの順に
                                tags=tags,
                            )
                            children_item_ids.append(item_id)  # item_id を記録

                            # スキャン結果をキャッシュ (子要素の item_id リストも追加)
                            self.scanned_dirs[item_id] = {
                                "data": item,
                                "children": [],  # 初期状態では子は空
                            }

                            # サブディレクトリがある場合はダミーアイテムを追加
                            if os.path.isdir(item["Path"]):
                                self.tree.insert(item_id, "end", text="dummy")

                        except Exception as e:
                            print(f"項目挿入エラー: {e}")

                    # 親アイテムに子要素の item_id リストを関連付け
                    if parent != "":  # ルートでなければ
                        self.scanned_dirs[parent]["children"] = children_item_ids

                    # ソート状態を復元 & 子要素に対してもソート適用 *ここが重要*
                    self.sort_tree(self.sort_column)
                    # ルートだけでなく、parent の子要素もソートする
                    if parent != "":
                        self.sort_tree_by_parent(parent)

                elif msg_type == "error":
                    self.progress_var.set(f"エラー: {data}")

                elif msg_type == "finished":
                    self.scanning = False
                    self.progress_var.set("完了")
                    break

            except Empty:
                continue
            except Exception as e:
                print(f"UI更新エラー: {e}")
                continue

    def sort_tree_by_parent(self, parent_id):
        """指定された親の子要素をソートする"""

        # サイズ列の場合は数値としてソート
        def get_value(item_id):
            try:
                if self.sort_column == "size":
                    size_str = self.tree.set(item_id, "size")
                    value = float(size_str.split()[0])
                    unit = size_str.split()[1]
                    multiplier = {
                        "B": 1,
                        "KB": 1024,
                        "MB": 1024**2,
                        "GB": 1024**3,
                        "TB": 1024**4,
                        "PB": 1024**5,
                    }
                    return value * multiplier.get(unit, 0)
                else:  # name列の場合
                    return self.tree.item(item_id)["text"].lower()
            except ValueError:  # 数値に変換できなかった場合
                return 0
            except Exception:  # その他のエラー
                return 0

        items = list(self.tree.get_children(parent_id))
        items.sort(key=get_value, reverse=self.sort_reverse)
        for index, item in enumerate(items):
            self.tree.move(item, parent_id, index)


def select_directory(path_entry, progress_var, tree, scanner):
    """参照ボタンが押されたときの処理"""
    directory = filedialog.askdirectory(initialdir=path_entry.get())
    if directory:
        path_entry.delete(0, tk.END)
        path_entry.insert(0, directory)
        progress_var.set("待機中")
        # ツリービューはクリアしない（ルートが変わったときのみクリア）
        # scanner.scan_directory(directory)  # 自動スキャンはしない


def update_treeview(tree, path, scanner, progress_var, parent=""):
    """ツリービューを更新"""
    if not os.path.exists(path):
        progress_var.set("無効なパスです")
        return

    # ルートレベルでの実行時のみツリーをクリア
    if parent == "":
        tree.delete(*tree.get_children())
        scanner.scanned_dirs.clear()  # ルートが変わったらキャッシュクリア

    scanner.scan_directory(path, parent)


def on_tree_expand(event, tree, scanner, path_entry, progress_var):
    """ツリー展開時の処理"""
    if scanner.scanning:
        return

    try:
        item_id = tree.selection()[0]
        children = tree.get_children(item_id)

        # 子が "dummy" のみの場合のみ展開処理
        if len(children) == 1 and tree.item(children[0])["text"] == "dummy":
            tree.delete(children)  # ダミーを削除

            # スキャン済みであれば、記録から情報を取得
            if item_id in scanner.scanned_dirs:
                # キャッシュされた子要素の item_id リストを取得
                cached_children = scanner.scanned_dirs[item_id]["children"]
                if cached_children:  # 子要素がキャッシュされていれば
                    # キャッシュされた情報を使ってツリーを再構築
                    for child_id in cached_children:
                        item = scanner.scanned_dirs[child_id]["data"]
                        tags = ("error",) if item.get("HasError") else ("directory",)
                        size_str = scanner._format_size(item["Size"])

                        # アイテムを再挿入（ダミーは不要）
                        new_id = tree.insert(
                            item_id,
                            "end",
                            text=item["Name"],
                            values=(size_str, item["Path"]),
                            tags=tags,
                        )
                        # scanned_dirsに追加
                        scanner.scanned_dirs[new_id] = scanner.scanned_dirs[child_id]

                        # もし子要素がさらに子を持つなら、ダミーを追加（再帰的な展開のため）
                        if os.path.isdir(item["Path"]):
                            tree.insert(new_id, "end", text="dummy")

                    # 展開状態を維持
                    tree.item(item_id, open=True)

                    # サブディレクトリに対してもソートを適用
                    scanner.sort_tree(scanner.sort_column)

                else:  # キャッシュがない場合
                    # 未スキャンなら通常のスキャン
                    full_path = tree.item(item_id)["values"][1]  # valuesの[1]がパス
                    if os.path.exists(full_path):
                        update_treeview(tree, full_path, scanner, progress_var, item_id)
                    else:
                        progress_var.set(f"パスが見つかりません: {full_path}")

            else:  # item_idがscanned_dirsにない場合（通常発生しないはずだが、念のため）
                full_path = tree.item(item_id)["values"][1]
                if os.path.exists(full_path):
                    update_treeview(tree, full_path, scanner, progress_var, item_id)
                else:
                    progress_var.set(f"パスが見つかりません: {full_path}")

    except KeyError as e:
        progress_var.set("展開エラー: ルートディレクトリを展開してください")
        print(f"KeyError: {e}")
    except Exception as e:
        progress_var.set(f"展開エラー: {str(e)}")
        print(f"Error in on_tree_expand: {str(e)}")


def main():
    """メイン関数"""
    root = tk.Tk()
    root.title("Directory Size Viewer")
    root.geometry("800x600")

    # 進捗状況を表示
    progress_var = tk.StringVar()
    progress_var.set("待機中")

    # パスとボタン
    path_frame = ttk.Frame(root)
    path_frame.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

    path_label = ttk.Label(path_frame, text="パス:")
    path_label.pack(side="left", padx=5)

    path_entry = ttk.Entry(path_frame)
    path_entry.pack(side="left", fill="x", expand=True, padx=5)
    path_entry.insert(0, os.getcwd())

    browse_button = ttk.Button(
        path_frame,
        text="参照",
        command=lambda: select_directory(path_entry, progress_var, tree, scanner),
    )
    browse_button.pack(side="left", padx=5)

    execute_button = ttk.Button(
        path_frame,
        text="実行",
        command=lambda: update_treeview(tree, path_entry.get(), scanner, progress_var),
    )
    execute_button.pack(side="left", padx=5)

    # 進捗状況ラベル
    progress_label = ttk.Label(path_frame, textvariable=progress_var)
    progress_label.pack(side="left", padx=5)

    # Treeview
    tree = ttk.Treeview(root, columns=("size",), show="tree headings")

    # スキャナーインスタンスの作成 (グローバル変数を使わない)
    scanner = DirectoryScanner(tree, progress_var)

    tree.heading("#0", text="ディレクトリ名", command=lambda: scanner.sort_tree("name"))
    tree.heading("size", text="サイズ", command=lambda: scanner.sort_tree("size"))
    scanner.update_header_text()  # 初期状態のヘッダーを設定
    tree.column("#0", width=400)
    tree.column("size", width=100)

    # ツリー展開イベント
    tree.bind(
        "<<TreeviewOpen>>",
        lambda event: on_tree_expand(event, tree, scanner, path_entry, progress_var),
    )

    tree.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

    # スクロールバー
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
    scrollbar.grid(row=1, column=3, sticky="ns")
    tree.configure(yscrollcommand=scrollbar.set)

    # ウィンドウのサイズ変更設定
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)  # 列0をリサイズ可能に

    # スタイル設定
    tree.tag_configure("error", foreground="red")
    tree.tag_configure("directory", foreground="black")

    root.mainloop()


if __name__ == "__main__":
    main()
