import logging
import sys

from fish.modules.console import ConsoleStream

# Redefined Stream
stdout_stream = ConsoleStream()
stderr_stream = ConsoleStream()

sys.stdout = stdout_stream
sys.stderr = stderr_stream

# Global logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stderr_handler = logging.StreamHandler(sys.stdout)
stderr_handler.setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
stdout_handler.setFormatter(formatter)
stderr_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)
logger.addHandler(stderr_handler)
