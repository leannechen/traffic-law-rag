import logging


def configure_logging() -> None:
    """讓 app.* 的 log（問答的錯誤、斷線、數字對不上）輸出到終端機。可重複呼叫。"""
    logger = logging.getLogger("app")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
