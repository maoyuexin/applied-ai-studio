#!/usr/bin/env bash
# Applied AI Studio - Codespaces / devcontainer bootstrap.
#
# This runs ONCE, automatically, when your codespace is first created.
# You never run it by hand. It installs the two toolchains the app needs
# (JavaScript and Python) so that "npm run dev" just works afterwards.
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

echo "==> Installing the Online Order service"
npm run setup:orders

# Installed here rather than on demand so nobody hits a missing package in the
# middle of a class. Adds roughly 40 seconds to codespace creation.
echo "==> Installing the fraud-detection notebook toolkit"
npm run setup:notebook

cat <<'BANNER'

==================================================================
 Applied AI Studio is ready.

   Start it by typing this in the terminal below:

       npm run dev

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
