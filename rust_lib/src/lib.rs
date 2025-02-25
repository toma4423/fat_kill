//! ディレクトリサイズ計算ライブラリ
//!
//! このライブラリは、指定されたディレクトリのサイズを再帰的に計算する機能を提供します。
//! PyO3を使用してPythonから呼び出し可能なインターフェースを提供しています。
//!
//! # 主な機能
//! - ディレクトリサイズの再帰的計算
//! - アクセス権限エラーの適切な処理
//! - Pythonとの連携インターフェース
//! - キャンセル機能
//! - 進捗報告

use pyo3::prelude::*;
use pyo3::exceptions::PyIOError;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::fmt;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

/// ディレクトリサイズ計算時のエラー型
#[derive(Debug)]
pub enum DirSizeError {
    /// I/Oエラー（ファイルアクセスエラーなど）
    IoError { path: String, cause: io::Error },
    /// 処理がキャンセルされた
    Cancelled,
}

impl fmt::Display for DirSizeError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            DirSizeError::IoError { path, cause } => {
                write!(f, "I/Oエラー '{}': {}", path, cause)
            },
            DirSizeError::Cancelled => {
                write!(f, "処理がキャンセルされました")
            },
        }
    }
}

impl std::error::Error for DirSizeError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            DirSizeError::IoError { cause, .. } => Some(cause),
            _ => None,
        }
    }
}

impl From<(io::Error, &Path)> for DirSizeError {
    fn from((err, path): (io::Error, &Path)) -> Self {
        DirSizeError::IoError {
            path: path.to_string_lossy().into_owned(),
            cause: err,
        }
    }
}

impl From<DirSizeError> for PyErr {
    fn from(error: DirSizeError) -> Self {
        PyIOError::new_err(format!("{}", error))
    }
}

/// Pythonから呼び出し可能なディレクトリサイズ計算関数
///
/// # 引数
/// * `path` - サイズを計算するディレクトリのパス
///
/// # 戻り値
/// * `PyResult<(u64, bool)>` - (計算されたサイズ, アクセス拒否フラグ)またはエラー
#[pyfunction]
fn get_dir_size_py(path: String) -> PyResult<(u64, bool)> {
    let path_buf = PathBuf::from(path);
    get_dir_size(&path_buf).map_err(|e| e.into())
}

/// アクセス拒否を示す特別な値を返す関数
///
/// # 戻り値
/// * `u64` - アクセス拒否を示す特別な値（u64::MAX）
#[pyfunction]
fn get_access_denied_value() -> PyResult<u64> {
    Ok(u64::MAX)
}

/// ディレクトリサイズを再帰的に計算する関数
///
/// # 引数
/// * `path` - サイズを計算するディレクトリのパス
///
/// # 戻り値
/// * `Result<(u64, bool), DirSizeError>` - (計算されたサイズ, アクセス拒否フラグ)またはエラー
///
/// # エラー
/// * `DirSizeError::IoError` - ファイルシステム操作中のI/Oエラー
pub fn get_dir_size(path: &Path) -> Result<(u64, bool), DirSizeError> {
    let mut total_size = 0;
    let mut access_denied = false;

    if let Ok(entries) = fs::read_dir(path) {
        for entry in entries.flatten() {  // エラーのあるエントリはスキップ
            let path = entry.path();
            if let Ok(metadata) = entry.metadata() {
                if metadata.is_file() {
                    total_size += metadata.len();
                } else if metadata.is_dir() {
                    match get_dir_size(&path) {
                        Ok((size, has_access_denied)) => {
                            total_size += size;
                            if has_access_denied {
                                access_denied = true;
                            }
                        },
                        Err(_) => {
                            access_denied = true;
                        }
                    }
                }
            }
        }
    } else {
        return Err((io::Error::new(io::ErrorKind::PermissionDenied, "アクセスが拒否されました"), path).into());
    }

    Ok((total_size, access_denied))
}

/// ディレクトリサイズを再帰的に計算する関数（進捗報告とキャンセル機能付き）
///
/// # 引数
/// * `path` - サイズを計算するディレクトリのパス
/// * `cancelled` - キャンセルフラグ
/// * `progress_callback` - 進捗報告用コールバック関数
///
/// # 戻り値
/// * `Result<(u64, bool), DirSizeError>` - (計算されたサイズ, アクセス拒否フラグ)またはエラー
pub fn get_dir_size_with_progress<F>(
    path: &Path,
    cancelled: Arc<AtomicBool>,
    progress_callback: &F
) -> Result<(u64, bool), DirSizeError>
where
    F: Fn(&str, u64)
{
    // キャンセルされていないか確認
    if cancelled.load(Ordering::Relaxed) {
        return Err(DirSizeError::Cancelled);
    }
    
    let mut total_size = 0;
    let mut access_denied = false;
    
    // 進捗報告
    progress_callback(path.to_string_lossy().as_ref(), 0);
    
    if let Ok(entries) = fs::read_dir(path) {
        for entry in entries.flatten() {
            // キャンセルされていないか確認
            if cancelled.load(Ordering::Relaxed) {
                return Err(DirSizeError::Cancelled);
            }
            
            let path = entry.path();
            
            if let Ok(metadata) = entry.metadata() {
                if metadata.is_file() {
                    let file_size = metadata.len();
                    total_size += file_size;
                    
                    // 進捗報告
                    progress_callback(path.to_string_lossy().as_ref(), file_size);
                } else if metadata.is_dir() {
                    // クロージャを参照として渡す
                    match get_dir_size_with_progress(&path, cancelled.clone(), progress_callback) {
                        Ok((size, has_access_denied)) => {
                            total_size += size;
                            if has_access_denied {
                                access_denied = true;
                            }
                            
                            // 進捗報告
                            progress_callback(path.to_string_lossy().as_ref(), size);
                        },
                        Err(DirSizeError::Cancelled) => {
                            return Err(DirSizeError::Cancelled);
                        },
                        Err(_) => {
                            access_denied = true;
                        }
                    }
                }
            }
        }
    } else {
        return Err((io::Error::new(io::ErrorKind::PermissionDenied, "アクセスが拒否されました"), path).into());
    }
    
    Ok((total_size, access_denied))
}

/// Pythonから呼び出し可能なキャンセル機能付きディレクトリサイズ計算関数
///
/// # 引数
/// * `path` - サイズを計算するディレクトリのパス
/// * `cancel_ptr` - キャンセルフラグへのポインタ
/// * `progress_callback` - 進捗報告用コールバック関数
///
/// # 戻り値
/// * `PyResult<(u64, bool)>` - (計算されたサイズ, アクセス拒否フラグ)またはエラー
#[pyfunction]
fn get_dir_size_with_cancel_py(
    path: String,
    cancel_ptr: usize,
    progress_callback: PyObject,
) -> PyResult<(u64, bool)> {
    let path_buf = PathBuf::from(path);
    let cancelled = unsafe { Arc::from_raw(cancel_ptr as *const AtomicBool) };
    
    // メモリリークを防ぐためにArcをクローン
    let cancelled_clone = cancelled.clone();
    std::mem::forget(cancelled);  // 元のArcを忘れる
    
    // 進捗コールバック関数
    let callback = move |path: &str, size: u64| {
        Python::with_gil(|py| {
            let _ = progress_callback.call1(py, (path, size));
        });
    };
    
    // ディレクトリサイズを計算
    let result = get_dir_size_with_progress(&path_buf, cancelled_clone, &callback);
    
    // 結果を返す
    match result {
        Ok((size, has_access_denied)) => Ok((size, has_access_denied)),
        Err(e) => Err(e.into()),
    }
}

/// キャンセルフラグを作成する関数
///
/// # 戻り値
/// * `PyResult<usize>` - キャンセルフラグへのポインタ（Pythonから管理）
#[pyfunction]
fn create_cancel_flag() -> PyResult<usize> {
    let flag = Arc::new(AtomicBool::new(false));
    let ptr = Arc::into_raw(flag);
    Ok(ptr as usize)
}

/// キャンセルフラグを設定する関数
///
/// # 引数
/// * `ptr` - キャンセルフラグへのポインタ
/// * `value` - 設定する値（trueでキャンセル）
///
/// # 戻り値
/// * `PyResult<()>` - 成功または失敗
#[pyfunction]
fn set_cancel_flag(ptr: usize, value: bool) -> PyResult<()> {
    let flag = unsafe { Arc::from_raw(ptr as *const AtomicBool) };
    flag.store(value, Ordering::SeqCst);
    // メモリリークを防ぐためにArcを忘れない
    std::mem::forget(flag);
    Ok(())
}

/// キャンセルフラグを解放する関数
///
/// # 引数
/// * `ptr` - キャンセルフラグへのポインタ
///
/// # 戻り値
/// * `PyResult<()>` - 成功または失敗
#[pyfunction]
fn release_cancel_flag(ptr: usize) -> PyResult<()> {
    unsafe {
        let _ = Arc::from_raw(ptr as *const AtomicBool);
    }
    Ok(())
}

/// Python モジュールの初期化関数
#[pymodule]
fn rust_lib(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(get_dir_size_py, m)?)?;
    m.add_function(wrap_pyfunction!(get_access_denied_value, m)?)?;
    m.add_function(wrap_pyfunction!(get_dir_size_with_cancel_py, m)?)?;
    m.add_function(wrap_pyfunction!(create_cancel_flag, m)?)?;
    m.add_function(wrap_pyfunction!(set_cancel_flag, m)?)?;
    m.add_function(wrap_pyfunction!(release_cancel_flag, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::tempdir;

    /// 正常なディレクトリサイズ計算のテスト
    #[test]
    fn test_get_dir_size_ok() {
        let dir = tempdir().unwrap();
        let dir_path = dir.path();
        let file_path = dir_path.join("test_file.txt");

        let mut file = File::create(&file_path).unwrap();
        writeln!(file, "Hello, world!").unwrap();

        drop(file);

        let size = get_dir_size(dir_path).unwrap();
        assert!(size > 0);
    }

    /// 存在しないディレクトリに対するテスト
    #[test]
    fn test_get_dir_size_not_found() {
        let result = get_dir_size(Path::new("nonexistent_directory"));
        assert!(result.is_err());

        match result.unwrap_err() {
            DirSizeError::IoError { path, cause } => {
                assert_eq!(path, "nonexistent_directory");
                assert_eq!(cause.kind(), io::ErrorKind::PermissionDenied);
            },
            DirSizeError::Cancelled => {
                panic!("予期しないキャンセルエラー");
            }
        }
    }

    /// アクセス権限がないディレクトリに対するテスト
    #[test]
    fn test_get_dir_size_permission_denied() {
        // 管理者権限が必要なディレクトリ (通常はアクセスできない)
        #[cfg(windows)]
        let dir_path = Path::new("C:\\Windows\\System32\\config"); // 例
        #[cfg(not(windows))]
        let dir_path = Path::new("/root"); // 例

        let result = get_dir_size(dir_path);
        
        // Windows環境では権限によって結果が異なる可能性があるため、
        // エラーまたはu64::MAXのどちらかを許容
        match result {
            Ok(size) => {
                assert_eq!(size, u64::MAX, "Expected access denied value");
            },
            Err(DirSizeError::IoError { path: _, cause }) => {
                assert_eq!(cause.kind(), io::ErrorKind::PermissionDenied);
            },
            Err(DirSizeError::Cancelled) => {
                panic!("予期しないキャンセルエラー");
            }
        }
    }

    /// キャンセル機能のテスト
    #[test]
    fn test_cancellation() {
        let dir = tempdir().unwrap();
        let dir_path = dir.path();
        
        // サブディレクトリとファイルを作成
        for i in 0..5 {
            let subdir = dir_path.join(format!("subdir_{}", i));
            fs::create_dir(&subdir).unwrap();
            
            for j in 0..10 {
                let file_path = subdir.join(format!("file_{}.txt", j));
                let mut file = File::create(&file_path).unwrap();
                writeln!(file, "Test content").unwrap();
            }
        }

        // キャンセルフラグを設定して即時キャンセル
        let cancelled = Arc::new(AtomicBool::new(true));
        
        // 進捗コールバック
        let progress_callback = |_path: &str, _size: u64| {
            // テスト用なので何もしない
        };

        // 実行
        let result = get_dir_size_with_progress(dir_path, cancelled, &progress_callback);
        
        // キャンセルエラーを期待
        assert!(matches!(result, Err(DirSizeError::Cancelled)));
    }
}