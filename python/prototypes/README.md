# Mode Machine Prototype

Interactive prototype for testing Agent mode transitions (IDLE | INTERACTION | SELF).

## Run

```bash
cd /home/hedaas/桌面/Conway's Agent/python
python prototypes/mode_machine/tui.py
```

## Controls

| Key | Action |
|-----|--------|
| `c` | Simulate WS connect (plugin connects) |
| `d` | Simulate WS disconnect (plugin closes Obsidian) |
| `m` | Simulate user sending a message |
| `t` | Time advance (+1 minute tick) |
| `v` | Simulate vault file event |
| `r` | Consume pending autonomous actions |
| `q` | Quit |

## State Machine

```
States: IDLE | INTERACTION | SELF

Transitions:
  IDLE + ws_connect()         → INTERACTION
  INTERACTION + ws_disconnect() → SELF
  SELF + ws_connect()          → INTERACTION
  INTERACTION + idle_timeout(60s) → SELF
  SELF + interest_threshold_reached → SELF (internal action, stays in SELF)
  SELF + ws_disconnect()       → SELF (no-op, already in SELF)
```

## Interest Accumulation

| Event | Points |
|-------|--------|
| Tick (1 min) | +1 |
| Dialogue | +5 |
| Vault event | +3 |

| Threshold | Action |
|-----------|--------|
| 20 points | `generate_world_fragment` |
| 40 points | `explore_note_links` |

## Test Sequences

### Sequence 1
```
[c] → [m] → [m] → [t]×5 → [d] → [t]×10 → [c]
```

### Sequence 2
```
[c] → [t]×20 → [d] → [t]×20
```

## Files

- `state_machine.py` — Pure reducer-style mode machine (extractable)
- `interest.py` — Interest accumulator logic (extractable)
- `tui.py` — Throwaway TUI shell
- `NOTES.md` — Findings after running
