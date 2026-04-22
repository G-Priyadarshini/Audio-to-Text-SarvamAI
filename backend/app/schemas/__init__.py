"""Compatibility layer: re-export schemas from `app.routes.schemas`.

This allows existing imports like `from app.schemas.job import JobCreate` to continue
working while the real schema modules live under `app.routes.schemas`.
"""

from importlib import import_module

_modules = [
	"app.routes.schemas.job",
	"app.routes.schemas.transcript",
	"app.routes.schemas.upload",
	"app.routes.schemas.download",
]

__all__ = []
for m in _modules:
	mod = import_module(m)
	# import all public names from the module into this package
	for name, val in vars(mod).items():
		if not name.startswith("_"):
			globals()[name] = val
	# collect module __all__ if present
	if hasattr(mod, "__all__"):
		__all__.extend(getattr(mod, "__all__"))
	else:
		__all__.extend([n for n in vars(mod) if not n.startswith("_")])

