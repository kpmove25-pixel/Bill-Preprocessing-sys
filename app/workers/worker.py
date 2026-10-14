"""后台任务 worker：线程队列，串行处理任务，避免请求阻塞。"""
from __future__ import annotations

import logging
import queue
import threading

from app.services import task_service

logger = logging.getLogger(__name__)

_task_queue: "queue.Queue" = queue.Queue()
_worker_thread: threading.Thread = None
_running = threading.Event()

# 当前运行中的任务，用于取消
_current: dict = {"task_id": None, "cancel": False}

# 排队中被取消的任务
_cancelled: set = set()


def _worker_loop():
    while _running.is_set():
        try:
            task_id = _task_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        # 排队期间被取消：跳过处理
        if task_id in _cancelled:
            _cancelled.discard(task_id)
            _task_queue.task_done()
            continue
        _current["task_id"] = task_id
        _current["cancel"] = False
        try:
            task_service.process_task(task_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("任务 %s 处理异常", task_id)
            task_service._update_task(task_id, status="failed")
        finally:
            _current["task_id"] = None
            _task_queue.task_done()


def start_worker():
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _running.set()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    logger.info("后台 worker 已启动")


def stop_worker():
    _running.clear()


def submit_task(task_id: str):
    _task_queue.put(task_id)


def cancel_task(task_id: str) -> bool:
    """请求取消任务（若正在处理则标记取消，否则标记排队取消）。"""
    if _current["task_id"] == task_id:
        _current["cancel"] = True
        task_service._update_task(task_id, status="cancelled")
        return True
    # 排队中的任务：加入取消集合，worker 处理前跳过
    _cancelled.add(task_id)
    task_service._update_task(task_id, status="cancelled")
    return True


def is_cancelled(task_id: str) -> bool:
    if _current["task_id"] == task_id:
        return _current["cancel"]
    return task_id in _cancelled
