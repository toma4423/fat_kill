@echo off
echo ===== ディレクトリサイズ表示アプリケーションのリリースビルド =====

echo 1. Rustライブラリのビルド
cd rust_lib
cargo build --release
if %ERRORLEVEL% neq 0 (
    echo Rustライブラリのビルドに失敗しました
    exit /b %ERRORLEVEL%
)

echo 2. Rustライブラリのホイールを作成
cd ..\py_app
poetry run pip install maturin
cd ..\rust_lib
poetry -C ..\py_app run maturin build --release --manifest-path "Cargo.toml"
if %ERRORLEVEL% neq 0 (
    echo Rustライブラリのホイール作成に失敗しました
    exit /b %ERRORLEVEL%
)

echo 3. Rustライブラリのインストール
cd ..\py_app
for /f "tokens=*" %%a in ('dir /b ..\rust_lib\target\wheels\*.whl') do (
    poetry run pip install ..\rust_lib\target\wheels\%%a
)
if %ERRORLEVEL% neq 0 (
    echo Rustライブラリのインストールに失敗しました
    exit /b %ERRORLEVEL%
)

echo 4. PyInstallerのインストール
poetry run pip install pyinstaller
if %ERRORLEVEL% neq 0 (
    echo PyInstallerのインストールに失敗しました
    exit /b %ERRORLEVEL%
)

echo 5. 実行ファイルのビルド
poetry run pyinstaller --onefile --windowed --name=Directory_Size_Viewer --version-file=file_version_info.py Directory_Size_Viewer.py
if %ERRORLEVEL% neq 0 (
    echo 実行ファイルのビルドに失敗しました
    exit /b %ERRORLEVEL%
)

echo ===== ビルド完了 =====
echo 実行ファイル: %CD%\dist\Directory_Size_Viewer.exe
cd .. 