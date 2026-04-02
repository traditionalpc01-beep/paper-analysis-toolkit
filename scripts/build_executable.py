#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import textwrap
import zipfile
import tarfile
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_ROOT = PROJECT_ROOT / "build" / "pyinstaller"

TARGETS = {
    "cli": {
        "entry": PROJECT_ROOT / "paperinsight" / "__main__.py",
        "name": "PaperInsight",
        "bundle": True,
    },
    "desktop-backend": {
        "entry": PROJECT_ROOT / "paperinsight" / "desktop_bridge.py",
        "name": "PaperInsightBackend",
        "bundle": False,
    },
}


def read_version() -> str:
    namespace: dict[str, str] = {}
    init_path = PROJECT_ROOT / "paperinsight" / "__init__.py"
    exec(init_path.read_text(encoding="utf-8"), namespace)
    return namespace["__version__"]


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_platform_info() -> dict:
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "darwin":
        return {
            "system": "macos",
            "suffix": "",
            "archive_type": "tar.gz",
            "executable_suffix": "",
            "platform_name": f"macos-{machine}",
        }
    elif system == "windows":
        return {
            "system": "windows",
            "suffix": ".exe",
            "archive_type": "zip",
            "executable_suffix": ".exe",
            "platform_name": "windows-x64",
        }
    else:
        return {
            "system": "linux",
            "suffix": "",
            "archive_type": "tar.gz",
            "executable_suffix": "",
            "platform_name": f"linux-{machine}",
        }


def build_executable(target: str) -> Path:
    target_config = TARGETS[target]
    entry_script = target_config["entry"]
    executable_name = target_config["name"]
    platform_info = get_platform_info()
    
    args = [
        str(entry_script),
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        executable_name,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_ROOT / "work"),
        "--specpath",
        str(BUILD_ROOT / "spec"),
        "--collect-submodules",
        "paperinsight",
        "--collect-submodules",
        "openai",
        "--collect-submodules",
        "openpyxl",
        "--collect-submodules",
        "pydantic",
        "--collect-submodules",
        "pydantic_core",
        "--collect-data",
        "openpyxl",
    ]
    
    if platform_info["system"] == "macos":
        args.extend([
            "--osx-bundle-identifier",
            "com.paperinsight.desktop",
        ])
    
    pyinstaller_run(args)
    
    exe_path = DIST_DIR / f"{executable_name}{platform_info['executable_suffix']}"
    if not exe_path.exists():
        raise FileNotFoundError(f"PyInstaller build did not produce {exe_path}")
    return exe_path


def build_readme(version: str, platform_info: dict) -> str:
    system = platform_info["system"]
    executable_name = f"PaperInsight{platform_info['executable_suffix']}"
    
    if system == "macos":
        return textwrap.dedent(
            f"""\
            PaperInsight {version} macOS package
            ===================================

            1. Unzip this archive to any folder.
            2. Run ./{executable_name} check
            3. Run ./{executable_name} config
            4. Run ./{executable_name} analyze <pdf-folder>

            Config file location:
              ~/.paperinsight/config.yaml

            A starter config template is included at:
              config/config.example.yaml

            Release archive checksum:
              See the sibling .sha256 file next to the archive.
            """
        )
    else:
        return textwrap.dedent(
            f"""\
            PaperInsight {version} Windows package
            =====================================

            1. Unzip this archive to any folder.
            2. Run {executable_name} check
            3. Run {executable_name} config
            4. Run {executable_name} analyze <pdf-folder>

            Config file location:
              %USERPROFILE%\\.paperinsight\\config.yaml

            A starter config template is included at:
              config\\config.example.yaml

            Release archive checksum:
              See the sibling .sha256 file next to the zip archive.
            """
        )


def create_release_bundle(version: str, exe_path: Path) -> tuple[Path, Path]:
    platform_info = get_platform_info()
    bundle_dir = DIST_DIR / f"PaperInsight-{platform_info['platform_name']}-{version}"
    
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    (bundle_dir / "config").mkdir(parents=True, exist_ok=True)
    
    executable_name = f"PaperInsight{platform_info['executable_suffix']}"
    shutil.copy2(exe_path, bundle_dir / executable_name)
    
    shutil.copy2(
        PROJECT_ROOT / "config" / "config.example.yaml",
        bundle_dir / "config" / "config.example.yaml",
    )
    (bundle_dir / "README.txt").write_text(build_readme(version, platform_info), encoding="utf-8")

    archive_type = platform_info["archive_type"]
    archive_name = f"{bundle_dir.name}.{archive_type}"
    archive_path = DIST_DIR / archive_name
    
    if archive_path.exists():
        archive_path.unlink()

    if archive_type == "zip":
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(bundle_dir.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(bundle_dir.parent))
    else:
        with tarfile.open(archive_path, "w:gz") as archive:
            for file_path in sorted(bundle_dir.rglob("*")):
                if file_path.is_file():
                    archive.add(file_path, arcname=str(file_path.relative_to(bundle_dir.parent)))

    checksum_path = DIST_DIR / f"{archive_path.name}.sha256"
    checksum_path.write_text(f"{sha256sum(archive_path)}  {archive_path.name}\n", encoding="utf-8")
    return archive_path, checksum_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the PaperInsight executable.")
    parser.add_argument(
        "--target",
        choices=sorted(TARGETS.keys()),
        default="cli",
        help="Build target.",
    )
    parser.add_argument(
        "--version",
        default=read_version(),
        help="Version string used in the release bundle name.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    exe_path = build_executable(args.target)
    print(f"Built executable: {exe_path}")
    if TARGETS[args.target]["bundle"]:
        archive_path, checksum_path = create_release_bundle(args.version, exe_path)
        print(f"Built archive: {archive_path}")
        print(f"Wrote checksum: {checksum_path}")


if __name__ == "__main__":
    main()
