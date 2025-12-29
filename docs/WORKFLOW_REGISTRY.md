# Workflow Registry Guide (M2+)

The registry defines which workflows are available and how they map to UI and runtime behavior.

## Current
- **M2** is the only active workflow.
- API workflow file: `workflows/ANIMATION_M2_Api.json`

## Future Milestones (M3–M6)
To add a new milestone:
1) Add the API workflow JSON to `workflows/`
2) Register it in `modules/workflows/registry.py`
3) Add prompt logic if needed
4) Update docs

## Notes
- M2 uses dual prompts (Stage 1 + Stage 2)
- Reference image is required (IP-Adapter only)
