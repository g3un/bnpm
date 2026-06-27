# BNPM: Agent Guide

## Commits

- Do not create commits or release tags unless the user explicitly asks
- One logical change per commit; use Conventional Commits, e.g. `feat(cli): add plugin update command`
- Do not bump versions except for release/publish work or when asked
- Use date-based package versions: `{major}.YYYYMMDD.{patch}` (e.g. `1.20260627.0`); increment `patch` for additional releases on the same date
- Release tags must be `v${package.version}` (e.g. `v1.20260627.0`); stable publishes to `latest`, prereleases to `next`
- Use `!` or `BREAKING CHANGE:` for breaking public API changes
