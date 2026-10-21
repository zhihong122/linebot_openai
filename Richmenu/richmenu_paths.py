"""Resolve project resources independent of Python module location / Render working directory."""
from pathlib import Path


def project_root(source_file):
    source = Path(source_file).resolve().parent
    for candidate in (source, *source.parents):
        if (candidate / "static").is_dir() or (candidate / "app.py").is_file():
            return candidate
    return source


def static_root(source_file):
    return project_root(source_file) / "static"
