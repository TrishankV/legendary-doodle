import logging


def logger(path : str ): -> logging.Logger :
    return logging.getLogger(f"Pipeline.{path}")