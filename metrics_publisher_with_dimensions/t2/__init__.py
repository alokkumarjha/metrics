import logging

null_handler = logging.NullHandler()
logger = logging.getLogger(__name__)
logger.addHandler(null_handler)

__version__ = "2.0.73"
