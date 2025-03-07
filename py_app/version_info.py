"""
バージョン情報管理モジュール
"""

# アプリケーションのバージョン
VERSION = "1.0.1"  # メジャー.マイナー.パッチ

# PyInstallerのバージョン情報（条件付きインポート）
try:
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo,
        FixedFileInfo,
        StringFileInfo,
        StringTable,
        StringStruct,
        VarFileInfo,
        VarStruct,
    )
except ImportError:
    # PyInstallerがインストールされていない場合や、実行時には不要
    pass
else:
    # PyInstallerのバージョン情報（ビルド時のみ使用）
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=(1, 0, 1, 0),
            prodvers=(1, 0, 1, 0),
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "Your Company"),
                            StringStruct("FileDescription", "Directory Size Viewer"),
                            StringStruct("FileVersion", "1.0.1"),
                            StringStruct("InternalName", "Directory_Size_Viewer"),
                            StringStruct("LegalCopyright", "Copyright (c) 2024"),
                            StringStruct(
                                "OriginalFilename", "Directory_Size_Viewer.exe"
                            ),
                            StringStruct("ProductName", "Directory Size Viewer"),
                            StringStruct("ProductVersion", "1.0.1"),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )
