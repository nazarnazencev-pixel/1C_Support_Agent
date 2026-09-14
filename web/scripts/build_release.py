import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def collect_files(project_root: Path) -> list[Path]:
    source_directories = [
        "1C_Support_Agent/app",
        "1C_Support_Agent/support_agent_db",
        "1C_Support_Agent/scripts",
        "1C_Support_Agent/data/knowledge",
        "web/src",
        "web/public",
        "web/server",
        "web/deploy",
        "web/scripts",
        "web/tests",
    ]
    source_files = [
        "1C_Support_Agent/requirements.txt",
        "web/package.json",
        "web/package-lock.json",
        "web/tsconfig.json",
        "web/vite.config.ts",
        "web/playwright.config.ts",
        "web/index.html",
        "web/compose.yaml",
        "web/.env.example",
        "web/.gitignore",
        "web/README.md",
        "web/DEPLOYMENT.md",
        "web/FILE_UPLOADS.md",
        "web/STREAMING.md",
        "web/VERIFICATION.md",
    ]
    excluded_directories = {"__pycache__", ".git", ".pytest_cache", ".venv", "node_modules"}
    result = [project_root / relative for relative in source_files]
    for relative in source_directories:
        for source in (project_root / relative).rglob("*"):
            if not source.is_file() or source.is_symlink():
                continue
            if excluded_directories.intersection(source.relative_to(project_root).parts):
                continue
            if source.name.startswith(".env") or source.suffix in {".pyc", ".db", ".log"}:
                continue
            result.append(source)
    for source in result:
        if not source.is_file():
            raise FileNotFoundError(source)
    return sorted(set(result))


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    output_directory = project_root / "web" / ".local" / "deployment"
    output_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_path = output_directory / f"molvest-support-{timestamp}.tar.gz"
    source_files = collect_files(project_root)
    with tarfile.open(archive_path, "w:gz") as archive:
        for source in source_files:
            archive.add(source, arcname=source.relative_to(project_root).as_posix(), recursive=False)
    expected_names = {source.relative_to(project_root).as_posix() for source in source_files}
    with tarfile.open(archive_path, "r:gz") as archive:
        if set(archive.getnames()) != expected_names:
            raise RuntimeError("Состав архива не совпадает со списком исходников.")
    manifest = {
        "archive": str(archive_path),
        "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "file_count": len(source_files),
        "files": sorted(expected_names),
    }
    archive_path.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in manifest.items() if key != "files"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
