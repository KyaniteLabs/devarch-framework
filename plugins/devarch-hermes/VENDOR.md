# Vendored DevArch Framework package

`archaeology/` is copied from KyaniteLabs/devarch-framework @ `b44430e198e45bfaee1edb2f3473f7d50ce17bc2` (v0.4.1).

Omitted from the vendor copy (not used by this Hermes wrap):
- `mcp_server/` (optional `mcp` extra)
- `templates/` and large `visualization/*.html` dashboards (HTML comment scanner caution; wrap uses markdown report + `_markdown_to_html`)

Refresh from repo root:

```bash
rm -rf plugins/devarch-hermes/archaeology
mkdir -p plugins/devarch-hermes/archaeology
tar -C archaeology -cf - \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='mcp_server' \
  --exclude='templates' \
  --exclude='visualization/template.html' \
  --exclude='visualization/global-template.html' \
  --exclude='visualization/multi-project-dashboard.html' \
  . | tar -C plugins/devarch-hermes/archaeology -xf -
```
