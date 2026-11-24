"""Package the original extractor so Spark can send it to worker processes."""
from pathlib import Path
from zipfile import ZipFile

def prepare():
    root = Path(__file__).parent
    with ZipFile(root / "legacy.zip", "w") as archive:
        archive.writestr("legacy/__init__.py", "")
        archive.write(root / "legacy/extractor_os.py", "legacy/extractor_os.py")


if __name__ == "__main__":
    prepare()
