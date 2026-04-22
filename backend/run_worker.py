"""Run the arq worker with Python 3.14+ compatibility.

This wrapper adds clearer logging when required native/Python packages
are missing so users can fix environment issues more easily.
"""
import asyncio
import logging
import traceback
from arq.worker import run_worker
from app.queue.settings import WorkerSettings


logger = logging.getLogger("icepot.worker")
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    fh = logging.FileHandler("backend_error.log", mode="a", encoding="utf-8")
    fh.setLevel(logging.ERROR)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)


def main() -> None:
    # Python 3.14 removed implicit event loop creation in get_event_loop()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        run_worker(WorkerSettings)
    except ModuleNotFoundError as exc:
        # Log and print actionable advice for missing dependencies
        logger.exception("Worker failed to start due to missing dependency: %s", exc)
        print("Worker failed to start due to missing dependency:", exc)
        print("Install required packages: pip install -r requirements.txt")
        # Re-raise so the exit code is non-zero and the error is visible to callers
        raise
    except Exception:
        logger.exception("Unhandled exception while starting worker:\n%s", traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
