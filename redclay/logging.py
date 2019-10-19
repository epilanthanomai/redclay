import contextlib
import contextvars
import logging
import re
import time
import traceback

LOGGING_CONTEXT = contextvars.ContextVar(__name__ + ".LOGGING_CONTEXT")


def init_logging():
    logging.setLoggerClass(Logger)

    handler = logging.StreamHandler()
    handler.setFormatter(Formatter())

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)


class Logger(logging.Logger):
    def makeRecord(
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ):
        record = super().makeRecord(
            name, level, fn, lno, msg, args, exc_info, func, extra, sinfo
        )
        record.extra = extra or {}
        record.context = get_logging_context()
        return record


class Formatter(logging.Formatter):
    def format(self, record):
        context = self.serialize_contexts(record.context, record.extra or {})
        created = time.strftime("%Y%m%dT%H%M%S", time.gmtime(record.created))
        msecs = int(record.msecs)
        base = (
            f"{created}.{msecs:03} {record.levelname:7s} "
            f"{record.name} {record.getMessage()}"
        )
        exc_text = (
            "\n" + self.format_exception(record.exc_info) if record.exc_info else ""
        )
        return base + (" | " + context if context else "") + exc_text

    def format_exception(self, exc_info):
        lines = traceback.format_exception(*exc_info)
        return "".join(lines)

    def serialize_contexts(self, *cxs):
        return " ".join(f"{key}:{value!r}" for cx in cxs for key, value in cx.items())


@contextlib.contextmanager
def logging_context(**kwargs):
    cx = get_logging_context()
    new_cx = cx.copy()
    new_cx.update(kwargs)

    token = LOGGING_CONTEXT.set(new_cx)
    try:
        yield
    finally:
        LOGGING_CONTEXT.reset(token)


def get_logging_context():
    try:
        return LOGGING_CONTEXT.get()
    except LookupError:
        return {}
