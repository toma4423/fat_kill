import os
from datetime import datetime


def get_directory_info(path: str) -> dict:
    """
    指定ディレクトリの情報を取得する関数
    例：ファイル数、合計サイズ、最終更新日時などを返す
    """
    info = {
        "total_files": 0,
        "total_size": 0,
        "last_modified": None,
    }
    for root, dirs, files in os.walk(path):
        info["total_files"] += len(files)
        for f in files:
            full_path = os.path.join(root, f)
            try:
                size = os.path.getsize(full_path)
                info["total_size"] += size
                mod_time = os.path.getmtime(full_path)
                if info["last_modified"] is None or mod_time > info["last_modified"]:
                    info["last_modified"] = mod_time
            except Exception:
                pass
    if info["last_modified"]:
        info["last_modified"] = datetime.fromtimestamp(info["last_modified"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    return info


def get_directory_tree(path: str, cancel_event=None) -> dict:
    """
    指定したディレクトリのツリー情報を辞書形式で返す関数。
    各辞書は以下のキーを持つ:
      - name: ディレクトリ名
      - size: ディレクトリ内の全ファイルサイズの合計（サブディレクトリも含む）
      - children: 子ディレクトリのリスト（同じ形式の辞書）
      - accessible: アクセス可能かどうか (Falseの場合はアクセス不可)
      - hidden: 隠しディレクトリかどうか (名前が '.' で始まる)
    """
    if cancel_event is not None and cancel_event.is_set():
        return None

    tree = {
        "name": os.path.basename(path) or path,
        "size": 0,
        "children": [],
        "accessible": True,
        "hidden": os.path.basename(path).startswith("."),
    }
    try:
        children = sorted(os.listdir(path))
    except PermissionError:
        tree["accessible"] = False
        return tree

    total = 0
    for child in children:
        # キャンセルチェック
        if cancel_event is not None and cancel_event.is_set():
            return None

        child_path = os.path.join(path, child)
        if os.path.isdir(child_path):
            try:
                subtree = get_directory_tree(child_path, cancel_event)
            except Exception as e:
                # エラー発生時はそのディレクトリをアクセス不可・エラー情報付きとして返す
                subtree = {
                    "name": child,
                    "size": 0,
                    "children": [],
                    "accessible": False,
                    "hidden": child.startswith("."),
                    "error": str(e),
                }
            if subtree is None:
                return None
            tree["children"].append(subtree)
            total += subtree.get("size", 0)
        else:
            try:
                size = os.path.getsize(child_path)
            except Exception:
                size = 0
            total += size
    tree["size"] = total
    return tree
