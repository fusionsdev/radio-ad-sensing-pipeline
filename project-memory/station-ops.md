# Station Operations

Quick-reference. Canonical policy: `Stations/Batch Policy.md`, `02_Operating_Policy.md`.

## Station Decision Types

- **Keep:** station is healthy and useful for consumer loan ad detection.
- **Pause:** station is low-signal, unstable, or currently not worth capacity.
- **Rotate:** station URL or station candidate should be replaced or retested.
- **Probe:** station needs reachability/valid-chunk/ffmpeg audit before decision.

## Current Known Policy

Do not scale workers or change scheduler logic before checking whether bad station streams are causing drops.

Station health review should include:

- valid chunks
- dropped chunks
- ffmpeg decode errors
- zero-transcript rate
- keyword/classifier yield
- days running
- last successful chunk

## Logging station decisions

```bash
python tools/memory/station_logger.py CALLSIGN keep|watch|pause|rotate_out --reasoning "…"
```