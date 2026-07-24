"""
tiny-state — Zero-dependency finite state machine for Python.
MIT License. https://github.com/hussain-alsaibai/tiny-state
"""
from __future__ import annotations
import time
import json
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio

__version__ = "1.0.0"
__all__ = ["FSM", "AsyncFSM", "state", "transition", "guard", "Context", "Transition"]


class StateType(Enum):
    REGULAR = "regular"
    INITIAL = "initial"
    FINAL = "final"


@dataclass
class Transition:
    from_state: str
    to_state: str
    trigger: str
    action: Optional[Callable] = None
    guard: Optional[Callable] = None

    def to_dict(self) -> dict:
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "trigger": self.trigger,
        }


@dataclass
class Context:
    """Holds FSM runtime data."""
    state: str
    fsm_name: str
    data: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def now(self) -> float:
        return time.time()

    def now_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.now()))

    def set(self, key: str, value: Any):
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


class FSM:
    """Synchronous finite state machine."""

    def __init__(self, name: str, initial_state: Optional[str] = None):
        self.name = name
        self._states: dict[str, Callable] = {}
        self._transitions: list[Transition] = []
        self._transition_map: dict[str, list[Transition]] = {}
        self._initial_state = initial_state
        self._ctx: Optional[Context] = None

    # ── Decorators ──────────────────────────────────────────────────────────

    def state(self, name: str):
        """Decorator: define a state handler."""
        def decorator(fn: Callable):
            self._states[name] = fn
            return fn
        return decorator

    def transition(
        self,
        from_state: str,
        to_state: str,
        trigger: Optional[str] = None,
    ):
        """Decorator: define a transition between states."""
        def decorator(fn: Callable):
            t = Transition(
                from_state=from_state,
                to_state=to_state,
                trigger=trigger or fn.__name__,
                action=fn,
            )
            self._transitions.append(t)
            self._transition_map.setdefault(t.trigger, []).append(t)
            return fn
        return decorator

    def guard(self, trigger: str):
        """Decorator: add a guard condition to a transition by trigger name."""
        def decorator(fn: Callable):
            for t in self._transition_map.get(trigger, []):
                t.guard = fn
            return fn
        return decorator

    # ── Init / Trigger ──────────────────────────────────────────────────────

    def init(self, context: Optional[dict] = None) -> Context:
        """Initialize the FSM to its initial state."""
        initial = self._initial_state or (
            list(self._states.keys())[0] if self._states else None
        )
        if initial is None:
            raise ValueError("No states defined. Use @fsm.state() first.")
        self._ctx = Context(
            state=initial,
            fsm_name=self.name,
            data=dict(context or {}),
        )
        self._ctx.metadata["initialized_at"] = self._ctx.now_iso()
        self._enter_state(initial)
        return self._ctx

    @property
    def state(self) -> str:
        """Current state name."""
        if self._ctx is None:
            raise RuntimeError("FSM not initialized. Call .init() first.")
        return self._ctx.state

    @property
    def context(self) -> Context:
        """Current context object."""
        if self._ctx is None:
            raise RuntimeError("FSM not initialized. Call .init() first.")
        return self._ctx

    def trigger(self, event: str, **kwargs) -> bool:
        """Fire an event to attempt a state transition."""
        if self._ctx is None:
            raise RuntimeError("FSM not initialized. Call .init() first.")

        candidates = self._transition_map.get(event, [])
        for t in candidates:
            if t.from_state == self._ctx.state:
                # Run guard
                if t.guard is not None:
                    try:
                        result = t.guard(self._ctx, **kwargs)
                        if not result:
                            self._ctx.metadata[f"guard_denied_{event}"] = (
                                self._ctx.now_iso()
                            )
                            continue
                    except Exception:
                        continue

                # Exit old state (metadata)
                self._ctx.metadata[f"exited_{t.from_state}_at"] = (
                    self._ctx.now_iso()
                )

                # Run action
                if t.action is not None:
                    result = t.action(self._ctx, **kwargs)
                    if result is False:
                        self._ctx.metadata[f"action_denied_{event}"] = (
                            self._ctx.now_iso()
                        )
                        continue

                # Transition
                old_state = self._ctx.state
                self._ctx.state = t.to_state
                self._ctx.history.append({
                    "from": old_state,
                    "to": t.to_state,
                    "trigger": event,
                    "at": self._ctx.now_iso(),
                })
                self._ctx.metadata[f"entered_{t.to_state}_at"] = (
                    self._ctx.now_iso()
                )
                self._enter_state(t.to_state)
                return True

        self._ctx.metadata[f"no_transition_{event}"] = self._ctx.now_iso()
        return False

    def _enter_state(self, state_name: str):
        handler = self._states.get(state_name)
        if handler is not None:
            try:
                handler(self._ctx)
            except Exception as e:
                self._ctx.metadata["state_error"] = str(e)

    def can_trigger(self, event: str) -> bool:
        """Check if an event is valid in the current state."""
        if self._ctx is None:
            return False
        for t in self._transition_map.get(event, []):
            if t.from_state == self._ctx.state:
                return True
        return False

    # ── Serialization ──────────────────────────────────────────────────────

    def to_json(self) -> str:
        """Serialize FSM state to JSON."""
        return json.dumps({
            "name": self.name,
            "state": self.state,
            "data": self._ctx.data,
            "history": self._ctx.history,
            "metadata": self._ctx.metadata,
        }, indent=2)

    def from_json(self, json_str: str):
        """Restore FSM state from JSON."""
        obj = json.loads(json_str)
        self._ctx = Context(
            state=obj["state"],
            fsm_name=obj["name"],
            data=obj.get("data", {}),
            history=obj.get("history", []),
            metadata=obj.get("metadata", {}),
        )

    def available_triggers(self) -> list[str]:
        """List valid triggers in current state."""
        if self._ctx is None:
            return []
        return [
            t.trigger
            for t in self._transition_map.get(self.state, [])
            if t.from_state == self._ctx.state
        ]

    def info(self) -> dict:
        """Return FSM structure info."""
        return {
            "name": self.name,
            "states": list(self._states.keys()),
            "transitions": [t.to_dict() for t in self._transitions],
            "current_state": self.state if self._ctx else None,
        }


class AsyncFSM(FSM):
    """Async finite state machine."""

    async def ainit(self, context: Optional[dict] = None) -> Context:
        initial = self._initial_state or (
            list(self._states.keys())[0] if self._states else None
        )
        if initial is None:
            raise ValueError("No states defined. Use @fsm.state() first.")
        self._ctx = Context(
            state=initial,
            fsm_name=self.name,
            data=dict(context or {}),
        )
        self._ctx.metadata["initialized_at"] = self._ctx.now_iso()
        await self._aenter_state(initial)
        return self._ctx

    async def atrigger(self, event: str, **kwargs) -> bool:
        if self._ctx is None:
            raise RuntimeError("FSM not initialized. Call .ainit() first.")

        candidates = self._transition_map.get(event, [])
        for t in candidates:
            if t.from_state == self._ctx.state:
                if t.guard is not None:
                    result = t.guard(self._ctx, **kwargs)
                    if not result:
                        continue

                self._ctx.metadata[f"exited_{t.from_state}_at"] = (
                    self._ctx.now_iso()
                )

                if t.action is not None:
                    if asyncio.iscoroutinefunction(t.action):
                        result = await t.action(self._ctx, **kwargs)
                    else:
                        result = t.action(self._ctx, **kwargs)
                    if result is False:
                        continue

                old_state = self._ctx.state
                self._ctx.state = t.to_state
                self._ctx.history.append({
                    "from": old_state,
                    "to": t.to_state,
                    "trigger": event,
                    "at": self._ctx.now_iso(),
                })
                self._ctx.metadata[f"entered_{t.to_state}_at"] = (
                    self._ctx.now_iso()
                )
                await self._aenter_state(t.to_state)
                return True

        self._ctx.metadata[f"no_transition_{event}"] = self._ctx.now_iso()
        return False

    async def _aenter_state(self, state_name: str):
        handler = self._states.get(state_name)
        if handler is not None:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(self._ctx)
                else:
                    handler(self._ctx)
            except Exception as e:
                self._ctx.metadata["state_error"] = str(e)


# ── Standalone convenience decorators ─────────────────────────────────────────

def state(name: str):
    """Standalone decorator. Usage: @state("name") then attach to FSM."""
    def decorator(fn: Callable):
        fn._state_name = name
        return fn
    return decorator


def transition(
    from_state: str,
    to_state: str,
    trigger: Optional[str] = None,
):
    """Standalone decorator. Usage: @transition("a", "b", "go") then attach to FSM."""
    def decorator(fn: Callable):
        fn._transition_from = from_state
        fn._transition_to = to_state
        fn._transition_trigger = trigger
        return fn
    return decorator


def guard(fn: Callable) -> Callable:
    """Standalone guard decorator."""
    return fn
