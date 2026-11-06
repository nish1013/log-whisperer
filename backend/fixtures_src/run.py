"""Run one scenario and let it fail. Writes the exception chain as JSON to $DESCRIBE_TO."""

import json
import os
import sys
import traceback

from app.api.orders import get_order_owner
from app.clients.http import fetch_status, fetch_status_unchained, load_retry_policy
from app.db.repo import register_twice
from app.services.user import show_profile
from app.worker import run_report, walk_tree

SCENARIOS = {
    "F01": show_profile,
    "F02": lambda: get_order_owner(42),
    "F03": load_retry_policy,
    "F04": fetch_status,
    "F05": fetch_status_unchained,
    "F06": lambda: walk_tree(0),
    "F07": register_twice,
    "F09": run_report,
}
HERE = os.path.dirname(os.path.abspath(__file__))


def type_name(exc):
    cls = type(exc)
    if cls.__module__ in ("builtins", "__main__"):
        return cls.__qualname__
    return f"{cls.__module__}.{cls.__qualname__}"


def chain(exc):
    excs, reasons = [exc], []
    while True:
        if exc.__cause__ is not None:
            exc, reason = exc.__cause__, "cause"
        elif exc.__context__ is not None and not exc.__suppress_context__:
            exc, reason = exc.__context__, "context"
        else:
            break
        excs.append(exc)
        reasons.append(reason)
    excs.reverse()
    reasons.reverse()
    return list(zip(excs, [None, *reasons]))


def describe(exc):
    ordered = chain(exc)
    exceptions = []
    culprit = None
    for e, reason in ordered:
        exceptions.append({"type": type_name(e), "message": str(e), "chain_reason": reason})
        if culprit is None:
            user = [f for f in traceback.extract_tb(e.__traceback__) if f.filename.startswith(HERE)]
            if user:
                f = user[-1]
                culprit = {"file": f.filename, "line": f.lineno, "func": f.name}
    return {"exceptions": exceptions, "root_cause_index": 0, "culprit": culprit}


def hook(exc_type, exc, tb):
    sys.__excepthook__(exc_type, exc, tb)
    target = os.environ.get("DESCRIBE_TO")
    if target:
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(describe(exc), fh)


if __name__ == "__main__":
    sys.excepthook = hook
    sys.setrecursionlimit(1000)
    SCENARIOS[sys.argv[1]]()
