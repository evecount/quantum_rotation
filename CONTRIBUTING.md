# Contributing to Q-Rotate

Q-Rotate is a Python package (`src/qrotate/`) plus a test suite (`tests/`),
regenerable benchmarks (`benchmarks/`) and a set of Marimo notebooks. This page
is the operational guide: how to set up, how to run the tests at the speed you
need, and how to regenerate the committed benchmark files.

## Setup in three commands

```bash
git clone https://github.com/evecount/quantum_rotation.git && cd quantum_rotation
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

That installs the `qrotate` package in editable mode from `src/`, the runtime
dependencies (numpy, scipy, aqora, guppylang, hugr-qir, pytket), the notebook
stack (marimo, altair) and the developer tools (pytest, ruff, ty). Python 3.10 or
newer is required; CI runs 3.11 and 3.12 on Ubuntu and Windows.

If you use [`uv`](https://docs.astral.sh/uv/), the committed `uv.lock` pins the
exact resolution:

```bash
uv sync --extra dev
```

Sanity check:

```bash
python -c "import qrotate; print(qrotate.__file__)"
```

Optional extras:

| Extra      | Installs            | Needed for                                          |
| ---------- | ------------------- | --------------------------------------------------- |
| `notebook` | marimo, altair      | `notebook.py`, `readme.py`, the two example notebooks |
| `dev`      | `notebook` + pytest, ruff, ty, watchdog, nbconvert, SDK helpers | running the tests, linting, authoring scripts |

The test suite imports the root-level `utils.py` (a Marimo module), so the
`dev` extra is the minimum for `pytest`.

## Running the tests

There are two tiers. Tests that take more than about a second (real-structure
shell encodings, Guppy and Pytket compilation) are marked `@pytest.mark.slow`.

```bash
# Fast tier: what CI runs on every push and pull request
pytest -m "not slow" -q

# Full suite: what CI runs on pushes to main
pytest -q
```

Useful variants:

```bash
pytest -q --durations=10        # see which tests dominate wall time
pytest -q -m slow               # only the slow tier
pytest -q -k "rus or wilson"    # by name
```

Most of the wall-clock time on a cold machine is import time (guppylang, scipy,
marimo), not test time; the slow tier removes the compile-heavy tests but cannot
remove the imports.

When you add a test that takes more than a few seconds, decorate it:

```python
import pytest

@pytest.mark.slow
def test_something_expensive():
    ...
```

The marker is registered in `pyproject.toml` under `[tool.pytest.ini_options]`.

## Regenerating the benchmarks

The JSON files in `benchmarks/` are committed outputs, not inputs. They are
rebuilt by running the modules as scripts **from the repository root** (the
output paths are relative to the working directory):

```bash
# Showdown results, molecular showdown across register sizes,
# constellation profiles and the statistical-robustness study
python -m src.qrotate.metrics
```

```bash
# Encoding diagnostics across register sizes
python -m src.qrotate.encoding_diagnostics
```

```bash
# Re-extract the active sites from RCSB / PubChem (network access required;
# raw downloads are cached under .cache/, which is git-ignored)
python -m src.qrotate.structures
```

The first command takes several minutes because the statistical-robustness
study runs 180 blind RUS trials. Commit the regenerated JSON (and the mirrored
`assets/*.js` files that `metrics.py` writes for the WebGL pages) together with
the code change that produced them, and say in the commit message which
command you ran.

Both `python -m src.qrotate.metrics` and `python -m qrotate.metrics` work once
the package is installed; the modules carry an import fallback for each spelling.
Keep that fallback intact when you edit imports.

## Linting and type checks

```bash
ruff check src tests
ruff format --check src tests
ty check src
```

Neither is enforced by CI yet; run them before opening a pull request.

## Branches and pull requests

- Branch from `main`; one topic per branch.
- CI must be green on the fast tier before review. Pushing to `main` runs the
  full suite on both operating systems and both Python versions.
- Do not rename or move existing modules under `src/qrotate/`; several
  workstreams add new modules there in parallel and depend on the current
  import paths.
- Add new runtime dependencies to `[project.dependencies]` in `pyproject.toml`
  and new optional ones to an extra; then run `uv lock` so the lock file stays
  in step with the metadata.

## Repository layout

```
src/qrotate/        the package (operators, hpc_bridge, circuits, metrics, structures, encoding_diagnostics)
tests/              pytest suite (fast tier + @pytest.mark.slow tier)
benchmarks/         generated JSON outputs, see "Regenerating the benchmarks"
assets/             images and generated *.js data for the WebGL pages
docs/               narrative docs 01–06 plus a copy of the published site
notebooks/, *.py    Marimo notebooks (need the `notebook` extra)
.github/workflows/  CI (ci.yml)
```

`docs/REPO_CLEANUP_PROPOSAL.md` describes the duplicated site artefacts and
the proposed single-source layout; nothing in it has been applied yet.
