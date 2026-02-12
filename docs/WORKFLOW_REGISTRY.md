# Workflow Registry Guide (M3+)

The registry defines which workflows are available and how they map to UI and runtime behavior.

## Current
- **M3** is the only active workflow.
- API workflow file: `workflows/Animation_Workflow_M3_Api.json`

## Future Milestones (M3–M6)
To add a new milestone:
1) Add the API workflow JSON to `workflows/`
2) Register it in `modules/workflows/registry.py`
3) Add prompt logic if needed
4) Update docs

## Notes
- M3 uses dual prompts (Stage 1 + Stage 2)
- Reference image is required (IP-Adapter only)
