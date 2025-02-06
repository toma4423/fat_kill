use std::fs::{self, DirEntry};
use std::io;
use std::path::{Path, PathBuf};
use std::fmt;

#[derive(Debug)]
pub enum DirSizeError {
    IoError { path: String, cause: io::Error },
}

impl fmt::Display for DirSizeError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            DirSizeError::IoError { path, cause } => {
                write!(f, "I/O error at '{}': {}", path, cause)
            }
        }
    }
}

impl std::error::Error for DirSizeError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            DirSizeError::IoError { cause, .. } => Some(cause),
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

#[pyfunction]
fn get_dir_size(path: &Path) -> Result<u64, DirSizeError> {
    let mut total_size = 0;
    println!("Entering get_dir_size: {:?}", path); // 関数開始時にパスを出力

    for entry_result in fs::read_dir(path).map_err(|e| DirSizeError::from((e, path)))? {
        let entry: DirEntry = match entry_result { // 型を明示
            Ok(entry) => entry,
            Err(e) => {
                println!("Error reading entry: {:?}", e); // エラーを出力
                return Err(DirSizeError::from((e, path)));
            }
        };

        println!("Processing entry: {:?}", entry.path()); // 処理中のエントリを出力

        let metadata = entry
            .metadata()
            .map_err(|e| DirSizeError::from((e, entry.path().as_path())))?;

        if metadata.is_dir() {
            println!("  It's a directory");
            total_size += get_dir_size(&entry.path())?;
        } else {
            println!("  It's a file, size: {}", metadata.len()); // ファイルサイズを出力
            total_size += metadata.len();
        }
    }

    println!("Leaving get_dir_size, total_size: {}", total_size); // 関数終了時にサイズを出力
    Ok(total_size)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::tempdir;

    #[test]
    fn test_get_dir_size_ok() {
        let dir = tempdir().unwrap();
        let dir_path = dir.path();
        let file_path = dir_path.join("test_file.txt");

        println!("Test dir: {:?}", dir_path);
        println!("Test file: {:?}", file_path);

        let mut file = File::create(&file_path).unwrap();
        writeln!(file, "Hello, world!").unwrap();

        drop(file); // 明示的にファイルを閉じる

        // let metadata = file.metadata().unwrap();  // 不要になる
        // println!("File size: {}", metadata.len());

        let size = get_dir_size(dir_path).unwrap();

        println!("Calculated size: {}", size);

        assert!(size > 0);
    }

    #[test]
    fn test_get_dir_size_not_found() {
        let result = get_dir_size(Path::new("nonexistent_directory"));
        assert!(result.is_err());

        match result.unwrap_err() {
            DirSizeError::IoError { path, cause } => {
                assert_eq!(path, "nonexistent_directory");
                assert_eq!(cause.kind(), io::ErrorKind::NotFound);
            }
        }
    }
    #[test]
    fn test_get_dir_size_permission_denied() {
        // 管理者権限が必要なディレクトリ (通常はアクセスできない)
        #[cfg(windows)]
        let dir_path = Path::new("C:\\Windows\\System32"); // 例
        #[cfg(not(windows))]
        let dir_path = Path::new("/root"); // 例

        let result = get_dir_size(dir_path);
        assert!(result.is_err());

        match result.unwrap_err() {
            DirSizeError::IoError { path: _, cause } => {
                assert_eq!(cause.kind(), io::ErrorKind::PermissionDenied);
            }
        }
    }
}