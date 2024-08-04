import sys
import logging
import traceback
from typing import Optional
from types import TracebackType

from loguru import logger
from lagrange.utils.log import log, install_loguru


def loguru_exc_callback(cls: type[BaseException], val: BaseException, tb: Optional[TracebackType], *_, **__):
    """loguru 异常回调

    Args:
        cls (Type[Exception]): 异常类
        val (Exception): 异常的实际值
        tb (TracebackType): 回溯消息
    """
    logger.opt(exception=(cls, val, tb)).error("Exception:")


def loguru_exc_callback_async(loop, context: dict):
    """loguru 异步异常回调

    Args:
        loop (AbstractEventLoop): 异常发生的事件循环
        context (dict): 异常上下文
    """
    message = context.get("message") or "Unhandled exception in event loop"
    if (
        handle := context.get("handle")
    ) and handle._callback.__qualname__ == "ClientConnectionRider.connection_manage.<locals>.<lambda>":
        logger.warning("Uncompleted aiohttp transport", style="yellow bold")
        return
    exception = context.get("exception")
    if exception is None:
        exc_info = False
    else:
        exc_info = (type(exception), exception, exception.__traceback__)
    if (
        "source_traceback" not in context
        and loop._current_handle is not None
        and loop._current_handle._source_traceback
    ):
        context["handle_traceback"] = loop._current_handle._source_traceback

    log_lines = [message]
    for key in sorted(context):
        if key in {"message", "exception"}:
            continue
        value = context[key]
        if key == "handle_traceback":
            tb = "".join(traceback.format_list(value))
            value = "Handle created at (most recent call last):\n" + tb.rstrip()
        elif key == "source_traceback":
            tb = "".join(traceback.format_list(value))
            value = "Object created at (most recent call last):\n" + tb.rstrip()
        else:
            value = repr(value)
        log_lines.append(f"{key}: {value}")

    logger.opt(exception=exc_info).error("\n".join(log_lines))


def patch_logging(level="INFO"):
    for name in logging.root.manager.loggerDict:
        _logger = logging.getLogger(name)
        for handler in _logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                _logger.removeHandler(handler)
    sys.excepthook = loguru_exc_callback
    traceback.print_exception = loguru_exc_callback
    log.set_level(level)
    logger.add(
        "./logs/latest.log",
        format="<g>{time:MM-DD HH:mm:ss}</g> | <lvl>{level: <8}</lvl> | <c><u>{name}</u></c> | <lvl>{message}</lvl>",
        level=level.upper(),
        enqueue=False,
        rotation="00:00",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
        colorize=False,
    )


install_loguru()
