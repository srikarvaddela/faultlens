"""Run separately: python -m app.worker."""
import logging
import signal
import threading

from .database import initialize_database, SessionLocal
from .jobs import process_one


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    initialize_database()
    stop = threading.Event()
    for name in ("SIGINT", "SIGTERM"):
        signal.signal(getattr(signal, name), lambda *_: stop.set())
    logging.info("FaultLens worker ready")
    while not stop.is_set():
        try:
            process_one(SessionLocal)
        except Exception:
            logging.exception("Worker database operation failed")
        stop.wait(0.5)


if __name__ == "__main__":
    main()
