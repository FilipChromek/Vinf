"""Small file helpers shared by the indexer and reports."""
import csv
import json
from pathlib import Path


def read_books(path):
    path = Path(path)
    if path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                row["authors"] = row.get("author", "").split("; ") if row.get("author") else []
                row["tags"] = row.get("tags", "").split("; ") if row.get("tags") else []
                row["published_year"] = int(row["published"]) if row.get("published", "").isdigit() else None
                yield row
    else:
        paths = sorted(path.glob("part-*")) if path.is_dir() else [path]
        if not paths:
            raise ValueError("No part files in " + str(path))
        for file in paths:
            with file.open(encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        yield json.loads(line)


def legacy_text(book):
    # Match the seven fields in the original indexer.
    values = [book.get("title", ""), book.get("author", ""),
              book.get("published", book.get("published_year", "")),
              book.get("publisher", ""), book.get("tags", []),
              book.get("description", ""), book.get("author_bio", "")]
    return " ".join("; ".join(v) if isinstance(v, list) else str(v or "") for v in values)
