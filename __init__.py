import logging

logger = logging.getLogger("search-product-catalog-images")
logger.setLevel(logging.INFO)
log_format = logging.Formatter("[%(levelname)s] %(asctime)s %(name)s :%(message)s")

if not logger.handlers:
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(log_format)
    logger.addHandler(streamHandler)