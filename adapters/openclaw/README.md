# OpenClaw Adapter

This adapter installs the canonical `skills/aegis-alpha` package into
`$OPENCLAW_HOME/skills/aegis-alpha` or `~/.openclaw/skills/aegis-alpha`.

OpenClaw should use the package public surface and avoid exposing internal
adapter skills as default agent routes.

On first run, OpenClaw should read `data/capability-guide.json` or the
generated `profile.onboarding` block before asking for API keys. Explain what
Aegis Alpha can do without APIs, what OpenClaw-native tools can cover, and
which API groups are recommended or required for specific investment
capabilities.
