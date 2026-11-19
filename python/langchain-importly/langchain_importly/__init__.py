"""LangChain integration for Importly: transcripts of video and audio links as Documents."""

from importlib import metadata

from langchain_importly.document_loaders import ImportlyLoader

try:
    __version__ = metadata.version(__package__ or "langchain_importly")
except metadata.PackageNotFoundError:
    __version__ = ""

__all__ = ["ImportlyLoader", "__version__"]
