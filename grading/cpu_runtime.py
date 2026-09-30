"""Serialize the stateful OMR engine inside each web worker.

Template globals and stdout capture belong to the process. Concurrent grading
threads can mix templates/logs and compete for the same two CPU cores. Other
HTTP work can still run on Gunicorn's second thread.
"""
from functools import wraps
from threading import RLock

_grading_lock = RLock()


def serialized_grading(function):
    @wraps(function)
    def run(*args, **kwargs):
        with _grading_lock:
            return function(*args, **kwargs)
    return run
