# Poetry環境でのPython実行ファイル化ガイド

## 前提条件
- Poetry がインストールされていること
- プロジェクトが Poetry で管理されていること
- Windows環境であること（このガイドはWindows向け）

## 手順

### 1. PyInstallerのインストール
```bash
# プロジェクトの依存関係として追加
poetry add --group dev pyinstaller
```

### 2. 実行環境の確認
```bash
# Poetry環境が有効か確認
poetry env info

# インストールされたPyInstallerのバージョン確認
poetry run pyinstaller --version
```

### 3. EXE化の実行
```bash
# 基本的なEXE化
poetry run pyinstaller your_script.py

# シングルファイル化する場合（推奨）
poetry run pyinstaller --onefile your_script.py

# アイコンを追加する場合
poetry run pyinstaller --icon=your_icon.ico your_script.py

# 一般的な推奨オプション
poetry run pyinstaller --onefile --noconsole --icon=your_icon.ico your_script.py
```

### 4. 生成されるファイル・ディレクトリ
- `dist/`: 生成された実行ファイルが格納
- `build/`: ビルド時の中間ファイルが格納
- `*.spec`: PyInstallerの設定ファイル

### 5. 外部ライブラリやDLLの扱い
```bash
# 外部ライブラリを含める場合
poetry run pyinstaller --hidden-import=package_name your_script.py

# DLLを含める場合
poetry run pyinstaller --add-binary "path/to/dll;." your_script.py

# 複数のリソースを含める場合
poetry run pyinstaller --add-data "resource1;." --add-data "resource2;." your_script.py
```

### 6. よくある問題と解決策

#### 依存関係の問題
- モジュールが見つからない場合:
```bash
poetry run pyinstaller --hidden-import=package_name your_script.py
```

#### デバッグ
```bash
# 詳細なログを表示
poetry run pyinstaller --debug=all your_script.py

# コンソール出力を保持
poetry run pyinstaller --console your_script.py
```

### 7. バージョン管理設定
```gitignore
# PyInstaller
build/
dist/
*.spec

# 一時ファイル
__pycache__/
*.pyc
*.pyo
*.pyd
```

## 注意事項
1. 実行ファイルのサイズ
   - 依存関係すべてが含まれるため、サイズが大きくなる
   - 必要最小限の依存関係のみを含めることを推奨
   - `--exclude-module` オプションで不要なモジュールを除外可能

2. アンチウイルスソフト
   - 誤検知される可能性がある
   - 必要に応じて除外設定を追加
   - デジタル署名の追加を検討

3. 環境変数
   - 実行環境の環境変数に注意
   - 必要な環境変数は明示的に設定
   - `--runtime-tmpdir` オプションでテンポラリディレクトリを指定可能

## トラブルシューティング
1. モジュールが見つからない場合
   - `--hidden-import` オプションを使用
   - `.spec` ファイルを編集

2. 実行時エラー
   - `--debug` オプションでログを確認
   - 依存関係を再確認

3. ファイルパスの問題
   - 相対パスを絶対パスに変更
   - リソースファイルの配置を確認

## ベストプラクティス
1. 開発環境
   - クリーンな環境でテスト
   - 必要な依存関係を明確化

2. バージョン管理
   - `.spec` ファイルをバージョン管理に含めるか検討
   - ビルド手順をドキュメント化

3. テスト
   - 異なる環境での動作確認
   - エッジケースのテスト

## 参考リンク
- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [Poetry Documentation](https://python-poetry.org/docs/)
```

このガイドはGitで管理すべきです。また、以下のファイルは`.gitignore`に追加すべきです：
```gitignore
# PyInstaller
build/
dist/
*.spec
```

このガイドは汎用的な内容となっており、今後の他のプロジェクトでも使用できます。実際のEXE化作業を始めましょうか？


## 実行ファイルの最適化

### 1. リソースファイルの扱い
```bash
# リソースファイルを含める場合
poetry run pyinstaller --add-data "path/to/resource;resource" your_script.py

# 複数のリソースを含める場合
poetry run pyinstaller --add-data "resource1;." --add-data "resource2;." your_script.py
```

### 2. 最適化オプション
```bash
# 最適化レベルを指定
poetry run pyinstaller -O2 your_script.py

# 不要なモジュールを除外
poetry run pyinstaller --exclude-module=module_name your_script.py
```

### 3. マルチプラットフォーム対応
- Windows用ビルド時の注意点
  - パスの区切り文字に注意
  - Windows固有のDLLの扱い
- クロスプラットフォームビルドは非推奨

### 4. セキュリティ考慮事項
- 機密情報の扱い
- 実行ファイルの署名
- アンチウイルス対策

## CI/CD統合

### 1. GitHub Actions例
```yaml
name: Build EXE
on: [push]
jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
      - name: Install Poetry
        run: pip install poetry
      - name: Install dependencies
        run: poetry install
      - name: Build EXE
        run: poetry run pyinstaller your_script.py
```

### 2. ビルド自動化
- バージョン管理との連携
- 自動テスト実行
- 成果物の保存

## メンテナンス

### 1. 更新管理
- 依存関係の更新手順
- 実行ファイルの再ビルド
- バージョン管理

### 2. 配布方法
- インストーラーの作成
- 自動更新の実装
- ライセンス管理

## チェックリスト
- [ ] 必要な依存関係の確認
- [ ] リソースファイルの確認
- [ ] テスト実行
- [ ] ビルド設定の確認
- [ ] 動作確認
- [ ] セキュリティチェック
- [ ] ドキュメント更新
```

このガイドは、プロジェクトのルートディレクトリに配置し、Gitで管理します。

また、プロジェクト固有の設定やビルド手順は別ファイル（例：`build_instructions.md`）に記録することをお勧めします。

実際のEXE化作業を始めましょうか？