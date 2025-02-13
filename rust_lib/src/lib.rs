pub fn add(left: u64, right: u64) -> u64 {
    left + right
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;
    use pyo3::types::{PyDict, PyList};

    #[test]
    fn it_works() {
        pyo3::prepare_freethreaded_python();
        let result = add(2, 2);
        assert_eq!(result, 4);
    }

    #[test]
    fn test_get_directory_info_normal() {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let dir = tempdir().unwrap();
            let path = dir.path();
            // 作業用のファイルを作成
            let file_path = path.join("test.txt");
            std::fs::write(&file_path, "hello world").unwrap();

            let result_obj = get_directory_info(py, path.to_str().unwrap()).unwrap();
            let dict: &PyDict = result_obj.extract(py).unwrap();
            let total_files: u64 = dict.get_item("total_files").unwrap().extract().unwrap();
            assert!(total_files >= 1);
        });
    }

    #[test]
    fn test_get_directory_tree_normal() {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let dir = tempdir().unwrap();
            let path = dir.path();
            // 作業用にサブディレクトリとファイルを作成
            let sub_dir = path.join("subdir");
            std::fs::create_dir(&sub_dir).unwrap();
            let file_path = sub_dir.join("testfile.txt");
            std::fs::write(&file_path, "some data").unwrap();

            let result_obj = get_directory_tree(py, path.to_str().unwrap(), Some(false)).unwrap();
            // キャンセルフラグが false のため Some で返る
            assert!(result_obj.is_some());
            let tree = result_obj.unwrap();
            let dict: &PyDict = tree.extract(py).unwrap();
            let name: String = dict.get_item("name").unwrap().extract().unwrap();
            assert!(!name.is_empty());

            let children_any = dict.get_item("children").expect("children not found");
            let children: &PyList = children_any.downcast::<PyList>().unwrap();
            assert!(children.len() >= 1);
        });
    }

    #[test]
    fn test_cancel_get_directory_tree() {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            // cancel = true の場合、None が返るはず
            let result_obj = get_directory_tree(py, "any_path", Some(true)).unwrap();
            assert!(result_obj.is_none());
        });
    }
}

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::fs;
use std::path::Path;
use std::time::UNIX_EPOCH;

use walkdir::WalkDir;

/// 再帰的にディレクトリツリーを構築する内部関数
fn build_tree(py: Python, path: &Path, cancel_flag: bool) -> PyResult<PyObject> {
    if cancel_flag {
        // キャンセルが要求されている場合は中断（ここでは例外を発生させる）
        return Err(PyErr::new::<pyo3::exceptions::PyException, _>("Cancelled"));
    }
    
    let dict = PyDict::new(py);
    // ディレクトリ名：file_name が取れなければパス文字列全体を使用
    let name = path.file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| path.to_string_lossy().into_owned());
    dict.set_item("name", name.clone())?;
    dict.set_item("size", 0)?; // 後で更新する
    dict.set_item("children", PyList::empty(py))?;
    dict.set_item("accessible", true)?;
    dict.set_item("hidden", name.starts_with("."))?;
    
    let mut total_size: u64 = 0;
    let read_dir = match fs::read_dir(path) {
        Ok(rd) => rd,
        Err(_e) => {
            // アクセス不可の場合は accessible を false にして返す
            dict.set_item("accessible", false)?;
            return Ok(dict.to_object(py));
        }
    };
    
    // ソートのためにエントリを収集してファイル名順にソート
    let mut entries: Vec<_> = read_dir.filter_map(Result::ok).collect();
    entries.sort_by_key(|entry| entry.file_name());
    
    let children_list = dict.get_item("children").unwrap().downcast::<PyList>()?;
    for entry in entries {
        if cancel_flag {
            return Err(PyErr::new::<pyo3::exceptions::PyException, _>("Cancelled"));
        }
        let entry_path = entry.path();
        if entry_path.is_dir() {
            match build_tree(py, &entry_path, cancel_flag) {
                Ok(child_obj) => {
                    // 抽出してサイズを加算
                    let child_dict = child_obj.extract::<&PyDict>(py)?;
                    let child_size: u64 = child_dict.get_item("size").and_then(|v| v.extract().ok()).unwrap_or(0);
                    total_size += child_size;
                    children_list.append(child_dict)?;
                },
                Err(e) => {
                    // エラー発生時は、エラー情報付きの辞書を追加
                    let child_dict = PyDict::new(py);
                    let child_name = entry_path.file_name()
                        .map(|s| s.to_string_lossy().into_owned())
                        .unwrap_or_else(|| entry_path.to_string_lossy().into_owned());
                    child_dict.set_item("name", child_name.clone())?;
                    child_dict.set_item("size", 0)?;
                    child_dict.set_item("children", PyList::empty(py))?;
                    child_dict.set_item("accessible", false)?;
                    child_dict.set_item("hidden", child_name.starts_with("."))?;
                    child_dict.set_item("error", format!("{:?}", e))?;
                    children_list.append(child_dict)?;
                }
            }
        } else {
            // ファイルの場合はサイズを加算
            let size = match fs::metadata(&entry_path) {
                Ok(metadata) => metadata.len(),
                Err(_) => 0,
            };
            total_size += size;
        }
    }
    
    dict.set_item("size", total_size)?;
    Ok(dict.to_object(py))
}

/// Python から呼び出す get_directory_tree 関数
///
/// cancel が Some(true) なら直ちに中断し None を返す（Python の None 相当）
///
/// 返却値は、ディレクトリツリーを表す辞書型
#[pyfunction(signature = (path, cancel=None))]
fn get_directory_tree(py: Python, path: &str, cancel: Option<bool>) -> PyResult<Option<PyObject>> {
    let cancel_flag = cancel.unwrap_or(false);
    if cancel_flag {
        // キャンセルが要求されている場合は None を返す
        return Ok(None);
    }
    match build_tree(py, Path::new(path), cancel_flag) {
        Ok(tree) => Ok(Some(tree)),
        Err(e) => {
            // エラー発生時はエラー情報付きの辞書を返す
            let dict = PyDict::new(py);
            dict.set_item("name", path)?;
            dict.set_item("size", 0)?;
            dict.set_item("children", PyList::empty(py))?;
            dict.set_item("accessible", false)?;
            let hidden = Path::new(path).file_name()
                .map(|s| s.to_string_lossy().starts_with("."))
                .unwrap_or(false);
            dict.set_item("hidden", hidden)?;
            dict.set_item("error", format!("{:?}", e))?;
            Ok(Some(dict.to_object(py)))
        }
    }
}

/// Python から呼び出す get_directory_info 関数
///
/// ディレクトリ内の全ファイル数、合計サイズ、最新更新日時（UNIXタイムスタンプ）を計算して辞書型で返す。
/// タイムスタンプの文字列変換は Python 側で行えるよう、raw な数値を返します。
#[pyfunction]
fn get_directory_info(py: Python, path: &str) -> PyResult<PyObject> {
    let mut total_files: u64 = 0;
    let mut total_size: u64 = 0;
    let mut last_modified: Option<u64> = None;
    
    // walkdir を使用して再帰的に走査
    for entry in WalkDir::new(path).into_iter().filter_map(Result::ok) {
        if entry.file_type().is_file() {
            total_files += 1;
            if let Ok(metadata) = entry.metadata() {
                total_size += metadata.len();
                if let Ok(modified) = metadata.modified() {
                    if let Ok(duration) = modified.duration_since(UNIX_EPOCH) {
                        let mod_time = duration.as_secs();
                        if last_modified.map_or(true, |lm| mod_time > lm) {
                            last_modified = Some(mod_time);
                        }
                    }
                }
            }
        }
    }
    
    let dict = PyDict::new(py);
    dict.set_item("total_files", total_files)?;
    dict.set_item("total_size", total_size)?;
    // last_modified が存在しなければ 0 を返す
    dict.set_item("last_modified", last_modified.unwrap_or(0))?;
    Ok(dict.to_object(py))
}

/// モジュールの初期化
#[pymodule]
fn rust_lib(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(get_directory_tree, m)?)?;
    m.add_function(wrap_pyfunction!(get_directory_info, m)?)?;
    Ok(())
}
