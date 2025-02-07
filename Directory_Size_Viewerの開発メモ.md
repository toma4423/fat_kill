# Directory Size Viewer 開発メモ

## 開発の目的
- ディレクトリのサイズを再帰的に計算し、ツリービュー形式で表示
- Rustの高速な処理とPythonのGUI機能を組み合わせた効率的な実装
- ユーザーフレンドリーなインターフェース

## 開発記録

### ファイル構成
- `Directory_Size_Viewer.py`: 本番用（最終的にexe化）
- `gui_integration_test.py` (旧`test_file.py`): 本番前の統合テスト用
- `gui_feature_test.py` (旧`testfile.py`): 新機能のテスト用
- `test_qt.py`: GUI+Rust連携のテスト用
- `import_tester.py`: ライブラリ互換性テスト用

### GUI実装
#### 試行錯誤
1. QTreeViewの実装
   - 失敗したアプローチ: gui_feature_test.py (旧testfile.py)でウィンドウが表示されない
   - 成功したアプローチ: gui_integration_test.py (旧test_file.py)では正常に動作
   - 新たな問題:
     - スレッド終了時のSystemError
     - 原因: ThreadHandleのis_doneメソッドでの例外
     - 解決策: アプリケーション終了処理の修正
   - デバッグ手順:
     1. 最小限のGUIテストファイル作成
     2. スレッドなしでの動作確認
     3. 段階的な機能追加でのテスト
   - テスト結果:
     1. minimal_gui_test.py:
       - 基本的なGUI機能は正常に動作
       - ウィンドウ表示とボタンクリックが機能
       - スレッドなしでは終了時エラーなし
        - → test_dirに移動（役割完了）
     2. gui_feature_test.py:
       - スレッド終了時にSystemErrorが発生
       - ThreadHandleのis_doneメソッドで例外
     3. gui_integration_test.py:
       - 正常に動作（参考実装）
     4. thread_pool_test.py:
        - QThreadPoolの基本機能確認
        - → test_dirに移動（役割完了）
     5. rust_thread_pool_test.py:
        - Rustライブラリとの統合確認
        - スレッド終了時のエラーなし
        - 非同期処理が正常に動作
        - エラーハンドリングも機能
     6. progress_test.py:
        - 進捗状況の表示機能追加
        - キャンセル機能の実装
     7. gui_integration_test.py:
        - ツリービュー実装の問題:
          - 子ディレクトリ展開時のエラー
          - 原因: ルートアイテムの親参照エラー
        - 新しいアプローチ:
          - os.walkの代わりにos.scandirを使用
          - 直接の子ディレクトリのみを処理
        - 表示仕様の決定:
          - ファイルも含めた完全なツリー表示を採用
          - 理由:
            1. 全体のサイズ構成が把握しやすい
            2. 詳細な情報が必要な場合に便利
            3. 展開/折りたたみで表示制御可能
          - 利点:
            - 直感的なディレクトリ構造の把握
            - 正確なサイズ情報の表示
            - 必要に応じた情報の取捨選択
        - 期待される効果:
          - より明確な階層構造
          - パフォーマンスの向上
          - メモリ使用量の削減
        - 解決策:
          - 親アイテムの存在チェック追加
          - ルートアイテムの特別処理
        - 教訓:
          - QStandardItemModelの階層構造の扱い
          - ルートアイテムと子アイテムの区別が重要
        - 今後の改善点:
          - エラーハンドリングの強化
          - アイテム更新処理の整理
          - デバッグログの体系化
   - 問題の切り分け:
     1. 基本的なGUI機能は問題なし
     2. スレッド管理が問題の原因
     3. 非同期処理の実装方法を見直す必要あり
   - スレッド管理の改善方針:
     1. QThreadPoolアプローチ（採用）:
       - メリット:
         - Qtの標準機能で安定性が高い
         - リソース管理が明示的
         - スレッドの再利用が可能
         - Rustの並行処理モデルと相性が良い
       - デメリット:
         - 実装がやや冗長
         - スレッドプールのサイズ管理が必要
       - 実装手順:
         1. 基本的なQThreadPool動作確認
           - WorkerSignalsクラスでシグナル管理
           - QRunnableベースのWorkerクラス
           - 軽量なテストタスクで動作確認
         2. Rust処理の統合
           - ディレクトリ走査をWorkerで実行
           - 進捗状況の通知機能追加
         3. エラーハンドリング
           - 例外の適切な捕捉と通知
           - クリーンアップ処理の確認
         4. テスト結果:
             - スレッド数: 6 (自動設定)
             - UI応答性: 良好
             - プログレス表示: 正常
             - エラーハンドリング: 機能確認済み
         5. 次のステップ:
            1. Rustライブラリとの統合
              - get_dir_size_py関数の非同期実行
              - 進捗状況の通知機能追加
            2. ツリービューの実装
              - QThreadPoolを使用した更新
              - 段階的なデータ表示
   - 追加の修正:
     - アプリケーションインスタンスの管理強化
     - 終了時のクリーンアップ処理追加
     - 例外処理の改善
   - 原因候補:
     1. イベントループの実装の違い
     2. シグナル/スロットの実装の違い
     3. Qt関連クラスのインポートの違い
   - 詳細分析:
     1. イベントループ: gui_integration_testは詳細なデバッグ出力とエラーハンドリングあり
     2. 非同期処理: gui_integration_testはWorkerクラスを使用
     3. インポート: gui_integration_testは非同期処理用のクラスを含む
   - 修正方針:
     1. メインループのデバッグ出力とエラーハンドリングを強化
     2. 非同期処理の実装を追加
     3. 必要なQtクラスのインポートを追加
   - 機能改善:
     1. サイズのソート機能を実装（単位を考慮）
     2. カスタムQStandardItemクラスでソートロジックを実装
     3. 生のバイト数を保持してソートに使用

2. ディレクトリ選択機能
   - 実装内容:
     1. 最後に選択したディレクトリを記憶
     2. パス入力欄でEnterキーを押したときの実行
     3. パスの検証機能の強化
   - 改善点:
     1. パス履歴機能の追加
     2. お気に入りディレクトリの保存
     3. ドラッグ&ドロップでのディレクトリ選択

3. プログレス表示
   - 実装内容:
     1. QProgressBarをindeterminateモードで使用
     2. 処理開始時に表示、完了時に非表示
     3. 処理中はExecuteボタンを無効化
   - 改善点:
     1. 進捗率の表示（現在は不確定表示のみ）
     2. キャンセル機能の追加
     3. 残り時間の表示

### Rust連携
#### 試行錯誤
1. ディレクトリサイズ計算
   - 実装内容:
      1. Rustで再帰的なディレクトリ走査
      2. PyO3を使用したPython連携
      3. 非同期処理によるUI応答性の確保
   - 改善点:
      1. キャンセル機能の実装
      2. 進捗状況の通知
      3. 並列処理の導入

2. エラーハンドリング
   - 実装内容:
      1. Rust側でのエラー型の定義
      2. Python側でのエラーメッセージの表示
      3. 権限エラーの適切な処理
   - 改善点:
      1. より詳細なエラー情報の提供
      2. リトライ機能の実装
      3. エラーログの保存

### パフォーマンス最適化
#### 試行錯誤
1. 大規模ディレクトリの処理
   - 実装内容:
      1. 非同期処理によるUI応答性の確保
      2. Rustによる高速なディレクトリ走査
      3. メモリ効率の良いデータ構造の使用
   - 改善点:
      1. 並列処理による高速化
      2. キャッシュの活用
      3. 部分的な更新処理の実装

2. メモリ使用量の最適化
   - 実装内容:
      1. 必要なデータのみを保持
      2. 大きなディレクトリの段階的な読み込み
      3. 不要なオブジェクトの適切な解放
   - 改善点:
      1. メモリ使用量の監視機能
      2. 大規模ディレクトリのページング
      3. メモリリークの検出と修正

### EXE化対応
#### 試行錯誤
1. PyInstallerとの互換性問題
   - 問題:
     - Python 3.13がPyInstallerの対応バージョン外
     - PyInstallerは3.8以上3.14未満をサポート
   - 解決策:
     1. pyproject.tomlのPythonバージョン指定を修正
     2. 安定版Python（3.11など）での環境構築
   - 検討結果:
     - Python 3.11環境での構築を選択
     - 理由:
       1. 安定性が重要なEXE化フェーズでは実績のある環境が望ましい
       2. PyInstallerとの完全な互換性が保証される
       3. 将来的な保守性が高い
       4. 多くのライブラリが安定してサポート
   - 実施手順:
     1. Python 3.11のインストール
       - Python 3.11.9を公式サイトからダウンロード
       - インストーラーオプション:
         - "Add Python 3.11 to PATH" を有効化
         - "Install for all users" を選択
       - インストール後の確認:
         - `python --version` で3.11.xを確認
         - 確認結果:
           - `py -3.11 --version` で Python 3.11.9 を確認
     2. Poetry環境の再構築
        - pyproject.tomlのPythonバージョンを3.11に変更
        - 注意: コマンドは必ずpy_appディレクトリで実行
        - トラブルシューティング:
          ```bash
          # VSCode環境の確認と再設定が成功
          # - Python 3.11.9が正しく認識された
          # - 注意: 必ずpy_appディレクトリで実行すること
          cd py_app
          # - Python 3.11環境の明示的な指定
          poetry env use C:\Users\ikai0700275\AppData\Local\Programs\Python\Python311\python.exe
          # - 環境の確認
          poetry env info  # Python 3.11.9が正しく設定されたことを確認
          # - 依存関係のインストールを実行
          poetry install
          # - Rustライブラリの再ビルド
          cd ../rust_lib
          poetry -C ../py_app run maturin build --release --manifest-path "%CD%\Cargo.toml"
          cd ../py_app
          poetry run pip install ../rust_lib/target/wheels/rust_lib-0.1.0-cp311-cp311-win_amd64.whl
          # - インストール確認
          poetry run python -c "import rust_lib; print('rust_lib installed successfully')"
          # インポートエラーが発生したため、以下の手順で再インストール
          # 1. Poetry依存関係の再インストール
          poetry install
          # 2. PyQt6の動作確認
          poetry run python -c "import PyQt6; print('PyQt6 installed successfully')"
          # 3. Rustライブラリの再ビルドとインストール
          cd ../rust_lib
          poetry -C ../py_app run maturin build --release --manifest-path "%CD%\Cargo.toml"
          cd ../py_app
          poetry run pip install ../rust_lib/target/wheels/rust_lib-0.1.0-cp311-cp311-win_amd64.whl
          ```
        - `poetry install` で依存関係を再インストール
        - 動作確認: Rustライブラリが正常にインストールされたことを確認
        - Rustライブラリのインポート確認
          ```bash
          poetry run python -c "import rust_lib; print('rust_lib installed successfully')"
          ```
        - アプリケーションの動作確認
          ```bash
          poetry run python gui_integration_test.py
          ```
        - インポートエラーが発生したため、以下の手順で再インストール
        - 1. Poetry依存関係の再インストール
        - 2. PyQt6の動作確認
        - 3. Rustライブラリの再ビルドとインストール
     3. 依存関係の再インストール
     4. 動作テスト
     5. EXE化作業
       - 本番用ファイルの準備
         ```bash
         # gui_integration_test.pyの内容をDirectory_Size_Viewer.pyにコピー
         copy gui_integration_test.py Directory_Size_Viewer.py
         ```
       - 動作確認
         ```bash
         # 本番用ファイルの動作確認
         poetry run python Directory_Size_Viewer.py
         
         # 確認項目:
         # 1. 通常のディレクトリ走査
         # 2. アクセス権限エラーの表示
         # 3. キャンセル機能
         # 4. ツリービューの展開
         
         # アクセス権限エラーの改善
         # Rust側での改善:
         # - アクセス拒否時はそのディレクトリをスキップ
         # - 特別な値(u64::MAX)でアクセス拒否を通知
         # - 注意: 再インストール時は--force-reinstallオプションが必要
         #   poetry run pip install --force-reinstall ../rust_lib/target/wheels/*.whl
         # Python側での改善:
         # - アクセス拒否があったディレクトリを視覚的に表示
         # - ツールチップで詳細情報を表示
         ```
       - PyInstallerのインストール

2. アクセス権限エラー処理の改善
   - 問題:
     - アクセス拒否されたディレクトリでアプリケーションが停止
     - エラー表示が不適切
   - 解決策:
     1. Rust側の改善
       - アクセス拒否時はディレクトリをスキップ
       - 特別な値(u64::MAX)でアクセス拒否を通知
       - エラーのあるエントリは`flatten()`でスキップ
     2. Python側の改善
       - アクセス拒否ディレクトリの視覚的表示
       - ツールチップによる詳細情報表示
       - 空ディレクトリとアクセス拒否の区別
   - 動作確認:
     - テストディレクトリ構造の作成
     - アクセス権限制御によるテスト
     - 正常なディレクトリとアクセス拒否ディレクトリの混在確認
   - 次のステップ:
     1. サイズ表示のソート機能実装
     2. キャッシュ機能の追加
     3. EXE化作業の継続

## 重要な発見や教訓
1. アーキテクチャに関する発見
   - Python (GUI) + Rust (処理) の組み合わせが効果的
   - 非同期処理が不可欠
   - モジュール間の明確な責任分担が重要

2. 実装上の注意点
   - エラーハンドリングは両言語で適切に実装
   - UI応答性の確保が重要
   - デバッグ出力の活用

3. パフォーマンスに関する知見
   - Rustによる処理が大幅な高速化に貢献
   - メモリ管理の重要性
   - 非同期処理によるUI応答性の向上

## 今後の改善点
1. 機能面
   - サブディレクトリの自動展開機能
   - ファイル種別ごとの集計機能
   - 検索・フィルタリング機能

2. パフォーマンス面
   - Rustでの並列処理の実装
   - キャッシュシステムの導入
   - メモリ使用量の最適化

3. ユーザビリティ面
   - ダークモード対応
   - キーボードショートカットの追加
   - 設定画面の実装

## 参考資料とリンク
- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Rust PyO3 User Guide](https://pyo3.rs/)
- [Qt for Python Documentation](https://doc.qt.io/qtforpython-6/)

## バージョン履歴
### v0.1.0
- 実装内容:
  - 基本的なGUI実装（QTreeView, プログレスバー）
  - Rustによるディレクトリサイズ計算
  - 非同期処理の実装
- 問題点:
  - 大規模ディレクトリでの処理速度
  - メモリ使用量の最適化が必要
  - エラーハンドリングの改善が必要
- 改善点: 
  - 並列処理の導入
  - キャッシュシステムの実装
  - ユーザビリティの向上 