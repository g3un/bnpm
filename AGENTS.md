# BNPM: Agent Guide

## Tools

- Use `uv` for Python project management.
- Use `uv run -m bnpm_dev.pack` to package the Binary Ninja plugin into
  `bundle/bnpm`.

## Commits

- Do not create commits unless the user explicitly asks
- One logical change per commit
- Use Conventional Commits, such as `feat(cli): add plugin update command`
- Use `!` or `BREAKING CHANGE:` for breaking public API changes
