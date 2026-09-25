# Changelog

## Unreleased

- Added version 1.0 JSON project validation and optional YAML input via `narrativecut[yaml]`; legacy JSON briefs remain supported.
- Invalid and unsupported project fields now produce deterministic CLI validation errors.
- Added generic asset sidecar validation for required rights metadata, file references, and duplicate or conflicting IDs; available with `--validate-assets`.

## [0.1.0] - 2026-09-23

- Initial local-first OSS core.
- Deterministic timeline, subtitle, asset-license report, revision, and QC outputs.
- Added public-readiness tests, documentation, and CI configuration.
