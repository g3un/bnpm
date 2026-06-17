# BNPM: Agent Guide

## Commits

- Do not create commits or release tags unless the user explicitly asks
- One logical change per commit; use Conventional Commits, e.g. `feat(cli): add plugin update command`
- Do not bump versions except for release/publish work or when asked
- Use CalVer without leading zeroes: `YYYY.M.D` (`2026.6.17`) or prerelease `YYYY.M.D-N` (`2026.6.17-0`)
- Release tags must be `v${package.version}`; stable publishes to `latest`, prereleases to `next`
- Use `!` or `BREAKING CHANGE:` for breaking public API changes
