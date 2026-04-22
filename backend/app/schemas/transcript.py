"""Compatibility shim for app.schemas.transcript
Re-exports from app.routes.schemas.transcript
"""
from app.routes.schemas.transcript import *

__all__ = getattr(__import__("app.routes.schemas.transcript", fromlist=["*"]), "__all__", [n for n in globals() if not n.startswith("_")])
