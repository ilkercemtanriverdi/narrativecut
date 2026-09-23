# Source map

| Source | Staging destination | Purpose |
|---|---|---|
| `documentary-engine-v1/documentary_engine/core.py` | `fluxengine_video_studio/core.py` | deterministic asset catalog, timeline, assembly, QC |
| `documentary-engine-v1/documentary_engine/__main__.py` | `fluxengine_video_studio/__main__.py` | local CLI |
| `documentary-engine-v1/documentary_engine/__init__.py` | `fluxengine_video_studio/__init__.py` | package marker |
| `documentary-engine-v1/tests/test_core.py` | `tests/test_core.py` | core smoke test |
| `fluxengine_work/engine/video_studio/timeline.py` | deferred | donor candidate: measured narration clock utilities; not copied because it depends on the private runtime contract |
| `fluxengine_work/engine/video_studio/revision_budget.py` | deferred | donor candidate: bounded revision state; not copied because it depends on private job storage |
| `fluxengine_work/engine/video_studio/visual_policy.py` | deferred | donor candidate: visual-mix gate; not copied because it contains private channel policy names |
| `fluxengine_work/engine/video_studio/speech_audit.py` | deferred | donor candidate: audio timing checks; not copied because it depends on private runtime helpers |
| `fluxengine_work/engine/video_studio/media_quality.py` | deferred | donor candidate: local media checks; not copied because it depends on private runtime helpers |
| `fluxengine_work/engine/video_studio/cleanup.py` | deferred | donor candidate: generated-cache cleanup; not copied because it targets private job storage |
| `fluxengine_work/engine/video_studio/plan.schema.json` | `docs/flux-plan.schema.json` | donor: plan schema reference |

The deferred donor modules remain in the read-only source workspace; the active
CLI does not require FluxEngine's private provider or channel configuration.
