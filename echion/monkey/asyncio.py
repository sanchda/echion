import typing as t
from asyncio import tasks
from asyncio.events import BaseDefaultEventLoopPolicy
from functools import wraps
from threading import current_thread

import echion.core as echion


# -----------------------------------------------------------------------------

_set_event_loop = BaseDefaultEventLoopPolicy.set_event_loop


@wraps(_set_event_loop)
def set_event_loop(self, loop) -> None:
    echion.track_asyncio_loop(t.cast(int, current_thread().ident), loop)
    return _set_event_loop(self, loop)


# -----------------------------------------------------------------------------

_gather = tasks._GatheringFuture.__init__  # type: ignore[attr-defined]


@wraps(_gather)
def gather(self, children, *, loop):
    try:
        return _gather(self, children, loop=loop)
    finally:
        # Link the parent gathering task to the gathered children
        parent = tasks.current_task(loop)
        for child in children:
            echion.link_tasks(parent, child)


# -----------------------------------------------------------------------------


def patch():
    BaseDefaultEventLoopPolicy.set_event_loop = set_event_loop  # type: ignore[method-assign]
    tasks._GatheringFuture.__init__ = gather  # type: ignore[attr-defined]

    echion.init_asyncio(tasks._current_tasks, tasks._all_tasks.data)  # type: ignore[attr-defined]


def unpatch():
    BaseDefaultEventLoopPolicy.set_event_loop = _set_event_loop  # type: ignore[method-assign]
    tasks._GatheringFuture.__init__ = _gather  # type: ignore[attr-defined]
