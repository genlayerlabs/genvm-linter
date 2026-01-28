# Publish to PyPI

Publish genvm-linter package to PyPI.

## Auto Publish (Recommended)

GitHub Action publishes automatically on push to main when version changes.

```bash
cd /Users/edgars/Dev/genvm-linter-official

# Bump version in BOTH files
# - pyproject.toml
# - src/genvm_linter/__init__.py

# Commit and push
git add pyproject.toml src/genvm_linter/__init__.py
git commit -m "Release v0.X.Y"
git push origin main
```

Action checks if version exists → publishes to PyPI if new.

Monitor: https://github.com/genlayerlabs/genvm-linter/actions

## Manual Publish (Fallback)

If GitHub Action fails:

```bash
cd /Users/edgars/Dev/genvm-linter-official
rm -rf dist && uv build

PYPI_TOKEN=$(op read "op://Engineering/API Token PyPi genvm-linter/credential" --account yeagerai.1password.com)
uv publish --token "$PYPI_TOKEN"
```

## GitHub Secret

Required in repo Settings → Secrets → Actions:
- `PYPI_API_TOKEN` - PyPI token

## Links

- PyPI: https://pypi.org/project/genvm-linter/
