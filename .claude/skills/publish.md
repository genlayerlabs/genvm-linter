# Publish to PyPI

Publish genvm-linter package to PyPI.

## Steps

1. **Bump version** in both files:
   - `pyproject.toml`
   - `src/genvm_linter/__init__.py`

2. **Build**:
   ```bash
   cd /Users/edgars/Dev/genvm-linter-official
   rm -rf dist && uv build
   ```

3. **Publish**:
   ```bash
   PYPI_TOKEN=$(op item get 7jsql74ko65ehgy2vcvv4cwx6i --account yeagerai.1password.com --format json | jq -r '.fields[] | select(.id == "credential") | .value')
   uv publish --token "$PYPI_TOKEN"
   ```

4. **Commit and push**:
   ```bash
   git add -A && git commit -m "Release vX.Y.Z" && git push
   ```

## 1Password

PyPI token stored in yeagerai.1password.com:
- Item ID: `7jsql74ko65ehgy2vcvv4cwx6i`
- Name: "API Token PyPi genvm-linter"
- Vault: Engineering
