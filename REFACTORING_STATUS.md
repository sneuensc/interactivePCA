# Refactoring Status

## Status (March 2026)

Refactoring is complete enough for production use of the packaged app layout/callback architecture.

## Final structure

- `interactive_pca/layouts/`: layout assembly
- `interactive_pca/callbacks/`: callback orchestration by concern
- `interactive_pca/components/`: reusable helper modules
- `interactive_pca/app.py`: app factory + wiring

## Recent behavior updates

- Conditional UI panel suppression:
  - No annotation → hide table, map, and time plot.
  - Missing latitude/longitude → hide map.
  - Missing time column → hide time plot.
- Conditional callback registration aligned with rendered components.

## Next maintenance focus

- Keep docs aligned with source behavior.
- Add/expand tests for conditional rendering and callback registration paths.
