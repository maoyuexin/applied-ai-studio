#!/usr/bin/env bash
# Applied AI Studio - Codespaces / devcontainer bootstrap.
#
# This runs ONCE, automatically, when your codespace is first created.
# You never run it by hand. It installs the two toolchains the app needs
# (JavaScript and Python); post-start.sh launches the app afterwards and on resume.
#
# If something here fails, the messages below are written for someone who has
# never used a terminal. Read the last few lines - they say what to do next.

set -euo pipefail

REQUIRED_PY_MAJOR_MINOR="3.11 or newer"

# ---------------------------------------------------------------------------
# Find a Python 3.11 interpreter.
#
# Why this is not just "python3.11": the devcontainer Python feature installs
# the interpreter as "python" and "python3" and does NOT always create a
# version-suffixed "python3.11" binary. Calling python3.11 directly used to
# abort this whole script (set -e), which also skipped the npm install below
# and left the codespace looking broken for no obvious reason.
# ---------------------------------------------------------------------------
# Accept 3.11 OR NEWER, not exactly 3.11. services/order-api/pyproject.toml declares
# requires-python = ">=3.11", so 3.12 and 3.13 are perfectly valid. Demanding an exact
# match would reject a container that could run the app fine - a self-inflicted failure
# on any image that ships a newer Python.
find_python() {
  local candidate
  for candidate in python3.11 python3.12 python3.13 python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

echo "==> Installing JavaScript dependencies (this is the slow one, please wait)"
npm ci

echo "==> Looking for Python ${REQUIRED_PY_MAJOR_MINOR}"
if ! PYTHON_BIN="$(find_python)"; then
  echo ""
  echo "  Could not find Python ${REQUIRED_PY_MAJOR_MINOR} in this codespace."
  echo ""
  echo "  What still works: nothing yet - the app needs this step."
  echo "  What to do: delete this codespace and create a new one. That fixes"
  echo "  it almost every time. Creating a fresh codespace is normal and safe;"
  echo "  you lose nothing, because your work lives in the repository."
  echo "  If a second codespace fails the same way, tell your instructor and"
  echo "  paste in this line:  find_python failed on $(uname -sr)"
  echo ""
  exit 1
fi
echo "    using ${PYTHON_BIN}"

echo "==> Creating the Python environment"
"${PYTHON_BIN}" -m venv .venv

# The large lab datasets live as GitHub Release assets, not in git. Fetch them
# before anything tries to prepare a model from them. If this fails the setup
# continues: the notebooks are committed with their outputs and every lab has an
# offline HTML copy, so only RE-RUNNING those labs is affected.
echo "==> Fetching the large lab datasets"
npm run fetch:data || echo "    (some lab data could not be fetched - see the note above)"

echo "==> Installing the Online Order service"
npm run setup:orders

# Installed here rather than on demand so nobody hits a missing package in the
# middle of a class. Adds roughly 40 seconds to codespace creation.
# PyTorch first, from the CPU wheel index. On Linux the default PyPI wheel is the
# CUDA build: about 3 GB of NVIDIA libraries that nothing in this repo can use,
# because a Codespace has no GPU. Installing it filled the 32 GB disk and failed
# container creation with "No space left on device". setup:notebook now runs this
# first, but it is spelled out here so the ordering is visible.
echo "==> Installing PyTorch (CPU build - the CUDA build does not fit and is not used)"
npm run setup:torch-cpu

echo "==> Installing the fraud-detection notebook toolkit"
npm run setup:notebook

echo "==> Installing the Fraud Detection Lab service"
npm run setup:fraud

echo "==> Preparing the Fraud Detection Lab model"
npm run prepare:fraud || echo "    (skipped: prepare:fraud could not complete - the notebook's"\
    "committed outputs and offline HTML still work; re-run it later)"

echo "==> Installing the Chest X-ray Prioritization service"
npm run setup:pneumonia

if [[ -s notebooks/pneumonia-screening/artifacts/model.pt \
   && -s notebooks/pneumonia-screening/artifacts/model_card.json \
   && -s notebooks/pneumonia-screening/artifacts/operating_policy.json \
   && -s notebooks/pneumonia-screening/artifacts/evaluation.json \
   && -s notebooks/pneumonia-screening/artifacts/sample_manifest.parquet ]]; then
  echo "==> Using the validated Chest X-ray artifacts included with the course"
else
  echo "==> Rebuilding missing Chest X-ray artifacts"
  npm run prepare:pneumonia || echo "    (skipped: prepare:pneumonia could not complete - the notebook's"\
    "committed outputs and offline HTML still work; re-run it later)"
fi

echo "==> Installing the Credit Risk Review service"
npm run setup:credit

echo "==> Preparing the Credit Risk Review model"
npm run prepare:credit || echo "    (skipped: prepare:credit could not complete - the notebook's"\
    "committed outputs and offline HTML still work; re-run it later)"

echo "==> Installing the Complaint Routing service"
npm run setup:complaints

echo "==> Preparing the Complaint Routing model"
npm run prepare:complaints || echo "    (skipped: prepare:complaints could not complete - the notebook's"\
    "committed outputs and offline HTML still work; re-run it later)"

echo "==> Installing the Predictive Maintenance service"
npm run setup:pdm

echo "==> Preparing the Predictive Maintenance model"
npm run prepare:pdm || echo "    (skipped: prepare:pdm could not complete - the notebook's"\
    "committed outputs and offline HTML still work; re-run it later)"

echo "==> Installing the Procedure Assistant service"
npm run setup:procedures

echo "==> Preparing the Procedure Assistant index"
npm run prepare:procedures || echo "    (skipped: prepare:procedures could not complete - the notebook's"\
    "committed outputs and offline HTML still work; re-run it later)"

echo "==> Installing the Demand Forecast service"
npm run setup:forecast

echo "==> Preparing the Demand Forecast model"
npm run prepare:forecast || echo "    (skipped: prepare:forecast could not complete - the notebook's"\
    "committed outputs and offline HTML still work; re-run it later)"

echo "==> Installing the Product Recommendation service"
npm run setup:recommendations

echo "==> Preparing the Product Recommendation model"
npm run prepare:recommendations || echo "    (skipped: prepare:recommendations could not complete - the notebook's"\
    "committed outputs and offline HTML still work; re-run it later)"

# pip's wheel cache is worth hundreds of megabytes by now and is never read again
# in a fresh container. Reclaim it so a student running `df -h` sees honest numbers.
echo "==> Reclaiming disk (pip cache)"
node scripts/venv-python.mjs -m pip cache purge || true

echo "==> Installing the Chest X-ray Prioritization service"
npm run setup:pneumonia

if [[ -s notebooks/pneumonia-screening/artifacts/model.pt \
   && -s notebooks/pneumonia-screening/artifacts/model_card.json \
   && -s notebooks/pneumonia-screening/artifacts/operating_policy.json \
   && -s notebooks/pneumonia-screening/artifacts/evaluation.json \
   && -s notebooks/pneumonia-screening/artifacts/sample_manifest.parquet ]]; then
  echo "==> Using the validated Chest X-ray artifacts included with the course"
else
  echo "==> Rebuilding missing Chest X-ray artifacts"
  npm run prepare:pneumonia
fi

cat <<'BANNER'

==================================================================
 Applied AI Studio setup is ready.

   The app starts automatically now and whenever this codespace
   resumes. You do not need to type npm run dev in Codespaces.

   Then wait a few seconds. A box will pop up in the corner saying
   the app is running on port 5173 - click "Open in Browser".

   Missed the pop-up? Click the "Ports" tab next to this terminal,
   find 5173, and click the little globe icon.

   The web address is private to you. Nobody else can open it.

   The "Ask Studio" chat page needs GitHub Copilot on your account.
   There is nothing to install or sign in to - if you have Copilot it
   just works, and if you do not, that page says so. Every other page
   works either way. See docs/student-quickstart.md, section 4.
==================================================================

BANNER
