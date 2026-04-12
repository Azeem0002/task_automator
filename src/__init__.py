# src/__init__.py
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("task-automator")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"