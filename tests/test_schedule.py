from datetime import datetime

from src.schedule.clock import DailySchedule, DailyTask


def _task(hour=11, minute=30, grace=120):
    seen = []
    task = DailyTask(name="lunch", hour=hour, minute=minute, grace_minutes=grace,
                     callback=lambda late: seen.append(late))
    task._seen = seen  # type: ignore[attr-defined]
    return task


def test_not_due_before_target():
    schedule = DailySchedule([_task()])
    now = datetime(2026, 10, 10, 11, 0)
    assert schedule.due(now) == []


def test_due_on_time_without_late_flag():
    schedule = DailySchedule([_task()])
    now = datetime(2026, 10, 10, 11, 31)
    due = schedule.due(now)
    assert len(due) == 1
    assert due[0][1] is False  # 不超过 5 分钟，不算迟到


def test_late_flag_when_woke_up_after_target():
    schedule = DailySchedule([_task()])
    now = datetime(2026, 10, 10, 13, 0)  # 迟到 90 分钟，仍在 120 分钟宽限内
    due = schedule.due(now)
    assert due[0][1] is True


def test_skipped_when_beyond_grace_and_marked_fired():
    task = _task(grace=60)
    schedule = DailySchedule([task])
    now = datetime(2026, 10, 10, 23, 0)
    assert schedule.due(now) == []
    assert task.last_fired == "2026-10-10"


def test_fires_only_once_per_day():
    task = _task()
    schedule = DailySchedule([task])
    schedule.fire(datetime(2026, 10, 10, 11, 30))
    schedule.fire(datetime(2026, 10, 10, 12, 30))
    assert task._seen == [False]  # type: ignore[attr-defined]


def test_fires_again_next_day():
    task = _task()
    schedule = DailySchedule([task])
    schedule.fire(datetime(2026, 10, 10, 11, 30))
    schedule.fire(datetime(2026, 10, 11, 11, 30))
    assert len(task._seen) == 2  # type: ignore[attr-defined]
