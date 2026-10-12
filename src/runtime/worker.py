"""Spawn-safe process entrypoint. No GUI, credentials, network or account writes."""

from __future__ import annotations

from ..agentbridge import build_providers
from ..metering.usage import UsageMeter
from ..progress.tracker import ProgressTracker


def observe(connection, stopping, kind: str, options: dict) -> None:
    """One persistent process per observation kind; only usage owns its ledger."""
    try:
        providers = build_providers(options["roots"])
        observer = None
        while not stopping.is_set():
            if not connection.poll(0.1):
                continue
            connection.recv()
            try:
                if observer is None:
                    if kind == "usage":
                        observer = UsageMeter(
                            providers, state_path=options["state_path"],
                            pricing_override=options["pricing_override"],
                            window_hours=options["window_hours"],
                        )
                    else:
                        observer = ProgressTracker(
                            providers, stale_minutes=options["stale_minutes"],
                            max_sessions=options["max_sessions"],
                            watch_processes=options["watch_processes"],
                        )
                if kind == "usage":
                    scanned = observer.scan(cancelled=stopping.is_set)
                    if stopping.is_set():
                        break
                    snapshot = observer.snapshot()
                    projected, _, sample_ok = observer.window_projection(snapshot)
                    payload = (snapshot, projected, sample_ok)
                else:
                    snapshot = observer.snapshot()
                    payload = snapshot
                connection.send(("ready", payload))
            except Exception as exc:
                connection.send(("failed", f"{kind}: {type(exc).__name__}: {exc}"))
    except (EOFError, BrokenPipeError, OSError):
        pass
    finally:
        connection.close()
