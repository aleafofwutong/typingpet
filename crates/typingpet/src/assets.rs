//! 内置图片素材：直接嵌入二进制，首次运行时释放到数据目录。
//!
//! 内置素材随二进制发布，启动时释放到用户数据目录。

use std::fs;
use std::path::Path;

pub const BUILT_IN_ASSETS: &[(&str, &[u8])] = &[
    (
        "pet-idle.apng",
        include_bytes!("../resources/pet-idle.apng"),
    ),
    (
        "pet-typing.apng",
        include_bytes!("../resources/pet-typing.apng"),
    ),
    (
        "pet-surprise.gif",
        include_bytes!("../resources/pet-surprise.gif"),
    ),
    (
        "pet-reaction-1.gif",
        include_bytes!("../resources/pet-reaction-1.gif"),
    ),
    (
        "pet-reaction-2.gif",
        include_bytes!("../resources/pet-reaction-2.gif"),
    ),
    (
        "pet-reaction-3.gif",
        include_bytes!("../resources/pet-reaction-3.gif"),
    ),
    (
        "pet-reaction-4.gif",
        include_bytes!("../resources/pet-reaction-4.gif"),
    ),
    (
        "pet-reaction-5.gif",
        include_bytes!("../resources/pet-reaction-5.gif"),
    ),
    (
        "pet-reaction-6.gif",
        include_bytes!("../resources/pet-reaction-6.gif"),
    ),
];

/// 把当前二进制中的内置素材释放到 `directory`。
///
/// BuiltIn 由程序自身管理，每次启动覆盖，避免升级后继续使用旧版本素材。
pub fn ensure_builtin_assets(directory: &Path) -> std::io::Result<()> {
    fs::create_dir_all(directory)?;
    for (name, bytes) in BUILT_IN_ASSETS {
        let path = directory.join(name);
        fs::write(&path, bytes)?;
    }
    Ok(())
}
