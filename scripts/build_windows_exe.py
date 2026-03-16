from __future__ import annotations

import argparse
import hashlib
import shutil
import textwrap
import zipfile
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


def build_executable(target: str) -> Path:
    target_config = TARGETS[target]
    entry_script = target_config["entry"]
    executable_name = target_config["name"]
    pyinstaller_run(
        [
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
    )
    exe_path = DIST_DIR / f"{executable_name}.exe"
    if not exe_path.exists():
        raise FileNotFoundError(f"PyInstaller build did not produce {exe_path}")
    return exe_path


def build_readme(version: str) -> str:
    return textwrap.dedent(
        f"""\
        PaperInsight {version} Windows package
        =====================================

        1. Unzip this archive to any folder.
        2. Run PaperInsight.exe check
        3. Run PaperInsight.exe config
        4. Run PaperInsight.exe analyze <pdf-folder>

        Config file location:
          %USERPROFILE%\\.paperinsight\\config.yaml

        A starter config template is included at:
          config\\config.example.yaml

        Release archive checksum:
          See the sibling .sha256 file next to the zip archive.
        """
    )


def create_release_bundle(version: str, exe_path: Path) -> tuple[Path, Path]:
    bundle_dir = DIST_DIR / f"PaperInsight-windows-x64-{version}"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    (bundle_dir / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe_path, bundle_dir / "PaperInsight.exe")
    shutil.copy2(
        PROJECT_ROOT / "config" / "config.example.yaml",
        bundle_dir / "config" / "config.example.yaml",
    )
    (bundle_dir / "README.txt").write_text(build_readme(version), encoding="utf-8")

    zip_path = DIST_DIR / f"{bundle_dir.name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(bundle_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(bundle_dir.parent))

    checksum_path = DIST_DIR / f"{zip_path.name}.sha256"
    checksum_path.write_text(f"{sha256sum(zip_path)}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, checksum_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Windows PaperInsight executable.")
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
        zip_path, checksum_path = create_release_bundle(args.version, exe_path)
        print(f"Built archive: {zip_path}")
        print(f"Wrote checksum: {checksum_path}")


if __name__ == "__main__":
    main()
