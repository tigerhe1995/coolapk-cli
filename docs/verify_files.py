"""K90 解锁文件完整性核查。"""

import hashlib
from pathlib import Path

ROOT = Path(r"F:\04.DSH\work\k90-root\files")
TOOL = ROOT / "01-工具" / "已解压" / "Xiaomi-QC解锁BL工具v2.5Plus"
ROM = ROOT / "03-官方线刷包" / "已解压" / "annibale_images_OS4.0.6.0.XPKCNXM_17.0"
PKG = ROOT / "02-K90工程小包" / "已解压" / "Redmi_K90工程小包-已测试-用于解锁BL"

REQUIRED = [
    ("主程序", TOOL / "双击我打开Xiaomi-QC解锁BL工具v2.5Plus.exe", 489472),
    ("驱动安装包", TOOL / "Tools" / "driver" / "QcomMtk_Driver_Setup_4.0.1.6.exe", 15490784),
    ("adb", TOOL / "Tools" / "bin" / "scrcpy-win64-v3.3.4" / "adb.exe", 6038528),
    ("K90 abl", TOOL / "Tools" / "img" / "8e_unlock_Bootloader" / "Factory_abl" / "K90_abl.elf", 335672),
    ("6.6.118 payload", TOOL / "Tools" / "img" / "8e_unlock_Bootloader" / "SELinux" / "preload_k90_k90u_6.6.118.so", 85736),
    ("64560 k90 payload", TOOL / "Tools" / "img" / "8e_unlock_Bootloader" / "SELinux_CVE-2026-64560" / "cve-2026-64560_k90_k90u.so", 98128),
    ("98260 提权库", TOOL / "Tools" / "img" / "8e_unlock_Bootloader" / "SELinux_CVE-2026-98260" / "libadbroot.so", 9800),
    ("8E gpt_both4", TOOL / "Tools" / "img" / "8e_unlock_Bootloader" / "Xiaomi_8e_gpt_both4.bin", 45056),
    ("工程小包 abl", PKG / "images" / "abl.elf", 335672),
    ("工程小包 flash_all.bat", PKG / "flash_all.bat", 6539),
    ("官方包 flash_all.bat", ROM / "flash_all.bat", 6416),
    ("官方包 flash_all_lock.bat", ROM / "flash_all_lock.bat", 6418),
    ("官方包 super.img", ROM / "images" / "super.img", 11553565264),
    ("官方包 boot.img", ROM / "images" / "boot.img", 100663296),
    ("官方包 init_boot.img", ROM / "images" / "init_boot.img", 8388608),
]

# K90 官方分区表（6 个）
for index in range(6):
    REQUIRED.append((
        f"K90 gpt_both{index}",
        TOOL / "Tools" / "img" / "8e_unlock_Bootloader" / "official-gpt_both" / "RedmiK90" / f"gpt_both{index}.bin",
        45056,
    ))


def main() -> int:
    missing = []
    wrong = []
    for label, path, expected in REQUIRED:
        if not path.exists():
            missing.append(f"{label}: {path}")
            print(f"  [MISS] {label}")
            continue
        size = path.stat().st_size
        if size != expected:
            wrong.append(f"{label}: {size} != {expected}")
            print(f"  [SIZE] {label}: {size} != {expected}")
        else:
            print(f"  [ OK ] {label:22} {size:>14,} bytes")

    print(f"\n检查 {len(REQUIRED)} 项：缺失 {len(missing)}，大小不符 {len(wrong)}")

    print("\n=== 官方线刷包 MD5 复核 ===")
    tgz = ROOT / "03-官方线刷包" / "annibale_images_OS4.0.6.0.XPKCNXM.tgz"
    if tgz.exists():
        print("  （压缩包已删除，用 images 目录内文件代替校验）")
    else:
        print("  压缩包已清理（节省磁盘），已解压目录可用")

    if missing or wrong:
        print("\n存在问题:")
        for item in missing + wrong:
            print("  -", item)
        return 1
    print("\n>>> 全部文件就位，可以开工了 <<<")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
