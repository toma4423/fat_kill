import rust_lib
import os

# テスト用のディレクトリを作成
test_dir = "test_dir"
os.makedirs(test_dir, exist_ok=True)

# テスト用のファイルを作成
test_file = os.path.join(test_dir, "test_file.txt")
with open(test_file, "w") as f:
    f.write("Hello, world!")

# Rust ライブラリの関数を呼び出す
try:
    dir_size = rust_lib.get_dir_size_py(test_dir)
    print(f"The size of '{test_dir}' is: {dir_size} bytes")

    # 存在しないディレクトリをテスト
    nonexistent_dir = "nonexistent_dir"
    try:
        size = rust_lib.get_dir_size_py(nonexistent_dir)
        print(f"Size of '{nonexistent_dir}': {size}")  # ここには到達しない
    except OSError as e:
        print(f"Error accessing '{nonexistent_dir}': {e}")

except OSError as e:
    print(f"Error: {e}")

# テスト用のディレクトリとファイルを削除 (オプション)
# import shutil
# shutil.rmtree(test_dir)
