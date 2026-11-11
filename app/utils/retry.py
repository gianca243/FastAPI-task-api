import logging
import time

from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def retry(fn, max_attempts=5, base_delay=1.0, sleep=time.sleep):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except OperationalError:
            if attempt == max_attempts:
                raise
            delay = base_delay * attempt
            logger.warning("intento %d/%d fallo, reintento en %0.1fs", attempt, max_attempts, delay)
            sleep(delay)
