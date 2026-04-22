"""Compatibility shim for environments missing the pyaudioop module.

Some distributions (or older pydub versions) try to import `pyaudioop`.
If it's not available, this shim re-exports the standard-library
`audioop` functions so imports like `import pyaudioop as audioop` continue
to work.
"""
try:
    # Prefer the real pyaudioop if present
    import pyaudioop as _audioop  # type: ignore
except Exception:
    try:
        # Fall back to stdlib audioop
        import audioop as _audioop
    except Exception:
        raise ImportError(
            "neither pyaudioop nor audioop is available in this Python environment"
        )

# Re-export names from the chosen implementation into this module's namespace
for _name in dir(_audioop):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_audioop, _name)
__all__ = [n for n in globals().keys() if not n.startswith("_")]
