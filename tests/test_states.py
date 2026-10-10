import time

from src.pet.states import PetStateMachine, pick_state


def test_priority_higher_wins():
    assert pick_state("idle", "remind") == "remind"
    assert pick_state("remind", "idle") == "remind"
    assert pick_state("error", "remind") == "error"


def test_unknown_state_never_blocks():
    assert pick_state("working", "不存在的状态") == "working"


def test_oneshot_decays_to_idle(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    machine = PetStateMachine("idle")
    machine.set("remind", ttl_ms=1000)
    assert machine.state == "remind"
    now[0] = 0.5
    assert machine.tick() is None
    now[0] = 1.5
    assert machine.tick() == "idle"
    assert machine.state == "idle"


def test_waiting_does_not_decay(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    machine = PetStateMachine("idle")
    machine.set("waiting")
    now[0] = 3600.0
    assert machine.tick() is None
    assert machine.state == "waiting"


def test_clear_returns_to_idle():
    machine = PetStateMachine("idle")
    machine.set("remind")
    machine.clear("remind")
    assert machine.state == "idle"


def test_every_state_has_a_sprite_row():
    from src.pet import states

    for state in states.STATE_PRIORITY:
        assert state in states.LONGNIANG_ROW_ALIAS, f"{state} 缺少占位图集行映射"
