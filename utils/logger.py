import logging
import sys

def setup_logger(name="lbank_ws_logger", level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if not logger.handlers:
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')

        # Console output
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # File logging
        file_handler = logging.FileHandler("log.txt")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

