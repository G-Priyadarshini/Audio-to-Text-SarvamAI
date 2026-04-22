"""Compatibility shim for app.schemas.upload
Re-exports from app.routes.schemas.upload
"""
from app.routes.schemas.upload import *

__all__ = getattr(__import__("app.routes.schemas.upload", fromlist=["*"]), "__all__", [n for n in globals() if not n.startswith("_")])
