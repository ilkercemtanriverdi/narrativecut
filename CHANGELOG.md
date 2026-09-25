# Changelog

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
