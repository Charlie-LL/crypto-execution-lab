# logger.py
import os
import csv
from typing import Dict, Any

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

class CSVLogger:
    def __init__(self, filepath: str, fieldnames: list[str]):
        self.filepath = filepath
        self.fieldnames = fieldnames
        parent = os.path.dirname(filepath)
        if parent:
            ensure_dir(parent)

        file_exists = os.path.exists(filepath)
        self._file = open(filepath, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=fieldnames)

        if not file_exists:
            self._writer.writeheader()
            self._file.flush()

    def write(self, row: Dict[str, Any]) -> None:
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:
            pass
