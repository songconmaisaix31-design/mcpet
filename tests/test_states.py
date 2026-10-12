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


def test_lower_priority_event_does_not_extend_notification(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    machine = PetStateMachine()
    machine.set("error", ttl_ms=1000)
    now[0] = 0.8
    machine.set("idle", ttl_ms=90000)
    now[0] = 1.1
    assert machine.tick() == "idle"


def test_repeated_notification_does_not_renew_ttl(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    machine = PetStateMachine()
    machine.set("happy", ttl_ms=1000)
    now[0] = 0.8
    machine.set("happy")
    now[0] = 1.1
    assert machine.tick() == "idle"


def test_background_waiting_can_finish_but_explicit_waiting_is_preserved():
    machine = PetStateMachine()
    assert machine.set_base("waiting") == "waiting"
    assert machine.set_base("working") == "working"
    machine.set("waiting")
    assert machine.set_base("thinking") == "waiting"
    machine.clear("waiting")
    assert machine.state == "thinking"


def test_notification_returns_to_most_recent_base(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    machine = PetStateMachine()
    machine.set_base("working")
    machine.set("happy", ttl_ms=1000)
    machine.set_base("thinking")
    assert machine.state == "happy"
    clock[0] = 1.1
    assert machine.tick() == "thinking"


def test_interaction_hides_event_expiry_and_clear_without_losing_base(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    machine = PetStateMachine()
    machine.set_base("working")
    machine.set("greet", ttl_ms=1000)
    machine.set_interaction("run-right")
    machine.set("error", ttl_ms=2000)
    assert machine.state == "run-right"
    machine.set_base("thinking")
    clock[0] = 2.1
    assert machine.tick() is None  # Event expiry must not interrupt the ongoing gesture.
    assert machine.state == "run-right"
    assert machine.set_interaction(None) == "thinking"
    machine.set("waiting")
    machine.set_interaction("sleeping")
    machine.clear("waiting")
    assert machine.state == "sleeping"
    assert machine.set_interaction(None) == "thinking"
