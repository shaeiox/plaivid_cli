#!/usr/bin/env bash
# Create one isolated development environment and install both Python projects.
# PVM-specific host tools (sbell and pvm-running-vms) are supplied by the PVM host,
# not by these Python distributions, so this script reports but does not install them.
set -Eeuo pipefail

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

info() {
    printf '[plaivid install] %s\n' "$*"
}

usage() {
    cat <<'EOF'
Usage: scripts/install_linux.sh [--help]

Installs the Engine, UI, and each project's development dependencies into the
repository-local .venv. Requires Linux and Python 3.12+ with venv/ensurepip.
Does not install system packages or PVM-specific binaries.

Optional environment variable:
  PLAIVID_PYTHON   Python 3.12+ executable to use (default: auto-detect)
EOF
}

case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    "") ;;
    *) usage >&2; fail "Unknown argument: $1" ;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
[[ "$(uname -s)" == Linux ]] || fail 'This installer supports Linux only.'
[[ -f "${ROOT}/pvm_control_engine/pyproject.toml" && -f "${ROOT}/UI/pyproject.toml" ]] \
    || fail "Expected Engine and UI pyproject.toml files under ${ROOT}."

python_ok() {
    command -v "$1" >/dev/null 2>&1 \
        && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1
}

PYTHON="${PLAIVID_PYTHON:-}"
if [[ -n "$PYTHON" ]]; then
    python_ok "$PYTHON" || fail "PLAIVID_PYTHON must point to an executable Python 3.12 or newer: ${PYTHON}"
else
    for candidate in python3.14 python3.13 python3.12 python3 python; do
        if python_ok "$candidate"; then
            PYTHON="$(command -v "$candidate")"
            break
        fi
    done
fi
[[ -n "$PYTHON" ]] || fail 'Python 3.12+ was not found. Install Python 3.12+ and its venv/ensurepip support, then rerun.'
"$PYTHON" -c 'import venv, ensurepip' >/dev/null 2>&1 \
    || fail "${PYTHON} is missing venv or ensurepip support. Install the matching OS venv package and rerun."

VENV="${ROOT}/.venv"
VENV_PY="${VENV}/bin/python"
if [[ -L "$VENV" ]]; then
    fail "Refusing to use a symlink as the project virtual environment: ${VENV}"
elif [[ -e "$VENV" ]]; then
    [[ -x "$VENV_PY" ]] || fail "Existing ${VENV} is incomplete; back it up or remove it, then rerun."
    python_ok "$VENV_PY" || fail "Existing ${VENV} does not use Python 3.12+; back it up or remove it, then rerun."
    "$VENV_PY" -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)' \
        || fail "${VENV_PY} is not an isolated virtual-environment interpreter."
    info "Reusing ${VENV}"
else
    info "Creating ${VENV} with $($PYTHON --version 2>&1)"
    "$PYTHON" -m venv "$VENV"
fi

if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    info 'Bootstrapping pip with ensurepip'
    "$VENV_PY" -m ensurepip --upgrade
fi
info 'Upgrading pip inside the virtual environment'
"$VENV_PY" -m pip install --upgrade pip

info 'Installing pvm-control-engine and its development dependencies'
(
    cd "${ROOT}/pvm_control_engine"
    "$VENV_PY" -m pip install --editable '.[dev]'
)
info 'Installing plaivid-ui and its development dependencies'
(
    cd "${ROOT}/UI"
    "$VENV_PY" -m pip install --editable '.[dev]'
)

info 'Checking installed command entry points (help only; no PVM operations)'
"${VENV}/bin/pvm-control-engine" --help >/dev/null
"${VENV}/bin/plaivid" --help >/dev/null

printf '\nInstallation complete.\n'
printf 'Activate the environment: source %q\n' "${VENV}/bin/activate"
printf 'Run Engine tests:       %q -m pytest -q\n' "${VENV_PY}"
printf 'Run UI tests:           (cd %q && %q -m pytest -q)\n' "${ROOT}/UI" "${VENV_PY}"
printf 'Run the Engine server:  pvm-control-engine serve\n'
printf 'Run the UI:             plaivid\n\n'

for tool in sudo sbell pvm-running-vms; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'NOTE: `%s` is not on PATH. It may be required on a configured PVM host.\n' "$tool"
    fi
done
printf 'PVM host commands and credentials are not installed or configured by this script.\n'
