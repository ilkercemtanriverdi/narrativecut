# Changelog

## [0.4.0] - 2026-10-07

- Feed the Claude scene plan into asset selection: `--scene-plan` loads a saved `scene-plan.json`, and each beat's ranking uses its scene's `search_query` terms plus a bonus for assets whose role matches the planned `visual_role`.
- Reject scene plans that do not match the script beat for beat; record the plan scene behind each beat and the planner model in `timeline.json`.
- Add synthetic placeholder assets and `examples/claude-demo/compare.py`; on the live demo plan, 4 of 8 beats change asset (`selection-comparison.md`).

## [0.3.0] - 2026-10-07

- Add optional Claude scene planning (`--plan-with-claude`, `narrativecut[claude]`): JSON-schema constrained output, local validation of beat coverage and order, deterministic timing, and `scene-plan.json` output.
- Add offline tests with a fake client, an opt-in live API test, and a demo script with unedited live output in `examples/claude-demo/`.
- Add a Claude scene planning demo section to the project website, built from the unedited live output.
- Align package version metadata (`pyproject.toml`, `narrativecut.__version__`) at 0.3.0.

## [0.2.1] - 2026-09-29

- Preserve CLI and validation exit codes; report QC failures as non-zero command exits.
- Require local FFmpeg and ffprobe, reject missing or undecodable media, and check render duration in both directions, frame rate/count, resolution, and narration audio.
- Add a synthetic end-to-end render/QC integration test and run it in CI with FFmpeg, ffprobe, and the optional YAML dependency installed.
- Close [issue #2](https://github.com/ilkercemtanriverdi/narrativecut/issues/2): local FFmpeg rendering and the synthetic integration test are covered. SVG assets need rasterization before rendering.

## [0.2.0] - 2026-09-25

- Added version 1.0 JSON project validation and optional YAML input via `narrativecut[yaml]`; legacy JSON briefs remain supported.
- Invalid and unsupported project fields now produce deterministic CLI validation errors.
- Added generic asset manifest validation for required source, rights, and subject metadata, local path references, and duplicate or conflicting IDs and file content.
- Added synthetic manifest tests for valid, missing, malformed, invalid-reference, and duplicate cases; CI passes.
- No required runtime dependencies were added; PyYAML remains optional.

### Known limitations

- Rights metadata is user-supplied; validation does not establish legal accuracy.
- Manifest validation checks adjacent JSON sidecars and file-level references; it does not decode or inspect media contents.
- YAML project input requires installing the optional PyYAML extra.

## [0.1.0] - 2026-09-23

- Initial local-first OSS core.
- Deterministic timeline, subtitle, asset-license report, revision, and QC outputs.
- Added public-readiness tests, documentation, and CI configuration.
