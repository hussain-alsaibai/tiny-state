# tiny-state

> Zero-dependency finite state machine for Python. Built for AI agents, workflows, and anything that needs predictable state transitions.

```bash
pip install tiny-state
```

## Why?

AI agents need state machines. Tools like LangChain give you a "state graph" that's 50MB of dependencies. `tiny-state` gives you the same power in one file:

```python
from tiny_state import FSM, state, transition

fsm = FSM("order")

@fsm.state("pending")
def pending(ctx):
    ctx.total = 0

@fsm.state("paid")
def paid(ctx):
    ctx.paid_at = ctx.now()

@fsm.state("shipped")
def shipped(ctx):
    ctx.shipped_at = ctx.now()

@fsm.state("delivered")
def delivered(ctx):
    ctx.delivered_at = ctx.now()

@fsm.transition("pending", "paid", trigger="pay")
@fsm.transition("paid", "shipped", trigger="ship")
@fsm.transition("shipped", "delivered", trigger="deliver")

ctx = fsm.init()
assert fsm.state == "pending"
fsm.trigger("pay")
assert fsm.state == "paid"
```

## Features

- **Decorators** — Define states and transitions cleanly
- **Guards** — Conditional transitions with `if_state()` and `unless_state()`
- **Actions** — Run code on enter/exit/state-change
- **Async** — Full `async`/`await` support
- **History** — Track state transitions for debugging/replay
- **Persistence** — Save/restore state to JSON
- **No dependencies** — Pure Python stdlib

## Installation

```bash
pip install tiny-state
```

Or copy `tiny_state.py` into your project. It's one file.

## Quick Start

### Basic FSM

```python
from tiny_state import FSM, state, transition

fsm = FSM("traffic_light")

@fsm.state("green")
def green(ctx):
    ctx.timer = 30

@fsm.state("yellow")
def yellow(ctx):
    ctx.timer = 5

@fsm.state("red")
def red(ctx):
    ctx.timer = 45

@fsm.transition("green", "yellow", trigger="timeout")
@fsm.transition("yellow", "red", trigger="timeout")
@fsm.transition("red", "green", trigger="timeout")

ctx = fsm.init()
fsm.trigger("timeout")  # green -> yellow
fsm.trigger("timeout")  # yellow -> red
fsm.trigger("timeout")  # red -> green
```

### With Guards

```python
from tiny_state import FSM, state, transition, guard

fsm = FSM("auth")

@fsm.state("logged_out")
def logged_out(ctx):
    ctx.user = None

@fsm.state("logged_in")
def logged_in(ctx):
    ctx.login_at = ctx.now()

@fsm.transition("logged_out", "logged_in", trigger="login")
@fsm.transition("logged_in", "logged_out", trigger="logout")

@guard("login")
def check_password(ctx, password: str, hash: str):
    return verify_hash(password, hash)
```

### Async FSM

```python
import asyncio
from tiny_state import AsyncFSM, state, transition

fsm = AsyncFSM("async_workflow")

@fsm.state("idle")
async def idle(ctx):
    pass

@fsm.state("running")
async def running(ctx):
    ctx.result = await compute()

@fsm.transition("idle", "running", trigger="start")
@fsm.transition("running", "idle", trigger="complete")

async def main():
    ctx = await fsm.init()
    await fsm.trigger("start")
    await fsm.trigger("complete")
```

### Persistence

```python
# Save
json_state = fsm.to_json()

# Restore
fsm2 = FSM("order")
fsm2.from_json(json_state)
assert fsm2.state == fsm.state
```

## API Reference

### `FSM(name, initial_state=None)`

Create a new FSM instance.

**Methods:**

| Method | Description |
|--------|-------------|
| `state(name)` | Decorator to define a state handler |
| `transition(from_state, to_state, trigger=None)` | Decorator to define a transition |
| `init(context=None)` | Initialize with optional context dict |
| `trigger(event, **kwargs)` | Fire an event to transition state |
| `can_trigger(event)` | Check if event is valid in current state |
| `to_json()` | Serialize state to JSON |
| `from_json(data)` | Restore state from JSON |

### Decorators

#### `@fsm.state(name)`

Define a state. The decorated function receives `ctx` (Context object) and runs on state entry.

#### `@fsm.transition(from_state, to_state, trigger=None)`

Define a transition. The decorated function is the action that runs during transition.

### Context Object

The `ctx` object passed to state/transition handlers has:

- `ctx.state` — Current state name
- `ctx.fsm` — Reference to the FSM instance
- `ctx.data` — Dict for arbitrary data
- `ctx.now()` — Current timestamp (callable)
- `ctx.history` — List of past transitions
- `ctx.metadata` — Dict for metadata (timestamps, etc.)

## License

MIT — do whatever you want.
