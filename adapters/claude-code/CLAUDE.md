# Aegis Alpha

Aegis Alpha is a research-only investment skillpack installed in this project.
Use the bundled canonical source in `skillpack/`.

Use only the public surface in `skillpack/data/surface-map.json`. Internal
skills are data providers, parsers, storage shims, or compatibility adapters.

Safety rules:

- Do not produce executable financial advice.
- Keep `decision_allowed=false`.
- Missing critical evidence must fail closed.
- Do not infer empty portfolios, empty opportunity sets, or no risk from missing
  data.
- Paper trade plans require explicit human confirmation outside the skill.

To run a command:

```bash
python3 skillpack/<skill>/scripts/dispatch.py --command <command> --payload '<json>'
```

Set `AEGIS_ALPHA_WORKSPACE` for runtime artifacts. The default is
`~/.aegis-alpha/workspace`.
