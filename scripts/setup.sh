#!/usr/bin/env bash
# Bootstrap a project-local development environment. Never install Python packages globally.
set -Eeuo pipefail

on_error() {
    local status=$?
    printf 'ERROR: setup failed at line %s (exit %s).\n' "${BASH_LINENO[0]:-unknown}" "$status" >&2
    exit "$status"
}
trap on_error ERR

info() {
    printf '\n[plaivid setup] %s\n' "$*"
}

fail() {
    printf '\nERROR: %s\n' "$*" >&2
    exit 1
}

if ! command -v dirname >/dev/null 2>&1; then
    fail "Missing 'dirname' (coreutils). Install the Linux core utilities and rerun this script."
fi
if ! command -v uname >/dev/null 2>&1; then
    fail "Missing 'uname'. Install the Linux core utilities and rerun this script."
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
[[ -f "${PROJECT_ROOT}/pyproject.toml" ]] || fail "Could not locate pyproject.toml above ${SCRIPT_DIR}."

KERNEL="$(uname -s)"
[[ "$KERNEL" == "Linux" ]] || fail "This setup script supports Linux; detected ${KERNEL}."

DISTRO_ID=unknown
DISTRO_NAME=unknown
DISTRO_VERSION=unknown
DISTRO_LIKE=""
if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_NAME="${PRETTY_NAME:-${NAME:-unknown}}"
    DISTRO_LIKE="${ID_LIKE:-}"
    DISTRO_VERSION="${VERSION_ID:-unknown}"
fi

PACKAGE_MANAGER=unavailable
case "${DISTRO_ID} ${DISTRO_LIKE}" in
    *rocky*|*rhel*|*centos*|*fedora*)
        if command -v dnf >/dev/null 2>&1; then
            PACKAGE_MANAGER=dnf
        elif command -v yum >/dev/null 2>&1; then
            PACKAGE_MANAGER=yum
        fi
        ;;
    *debian*|*ubuntu*)
        if command -v apt-get >/dev/null 2>&1; then
            PACKAGE_MANAGER=apt-get
        fi
        ;;
    *suse*|*opensuse*)
        if command -v zypper >/dev/null 2>&1; then
            PACKAGE_MANAGER=zypper
        fi
        ;;
    *alpine*)
        if command -v apk >/dev/null 2>&1; then
            PACKAGE_MANAGER=apk
        fi
        ;;
esac
if [[ "$PACKAGE_MANAGER" == unavailable ]]; then
    for candidate in dnf yum apt-get zypper apk; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PACKAGE_MANAGER="$candidate"
            break
        fi
    done
fi
info "Project root: ${PROJECT_ROOT}"
info "Detected platform: ${DISTRO_NAME} (${DISTRO_ID} ${DISTRO_VERSION}); package manager: ${PACKAGE_MANAGER}"

python_prerequisite_help() {
    case "$DISTRO_ID" in
        rocky|rhel|centos|fedora)
            printf '  Rocky/RHEL/Fedora: sudo dnf install python3.12 python3.12-pip\n'
            printf '  (Use the Python 3.12+ package available from your approved OS repositories.)\n'
            ;;
        ubuntu)
            printf '  Ubuntu: sudo apt-get install python3.12 python3.12-venv\n'
            printf '  If unavailable in the configured repositories, use an organization-approved Python 3.12 source.\n'
            ;;
        debian)
            printf '  Debian: install Python 3.12+ and its venv/ensurepip support from an approved repository.\n'
            printf '  Debian 12 commonly provides Python 3.11 by default; do not replace /usr/bin/python3.\n'
            ;;
        *)
            printf '  Install Python 3.12+ with its venv and ensurepip support using your approved Linux package source.\n'
            ;;
    esac
    printf '  Then rerun: %q\n' "${SCRIPT_DIR}/setup.sh"
}

is_supported_python() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1
}

PYTHON_BIN="${PLAIVID_PYTHON:-}"
if [[ -n "$PYTHON_BIN" ]]; then
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        printf "ERROR: PLAIVID_PYTHON='%s' is not executable or not on PATH.\n" "$PYTHON_BIN" >&2
        python_prerequisite_help >&2
        exit 1
    fi
    if ! is_supported_python "$PYTHON_BIN"; then
        EXPLICIT_VERSION="$("$PYTHON_BIN" --version 2>&1 || true)"
        printf 'ERROR: %s is not Python 3.12 or newer.\n' "$EXPLICIT_VERSION" >&2
        python_prerequisite_help >&2
        exit 1
    fi
else
    PYTHON_CANDIDATES=()
    while IFS= read -r candidate; do
        if [[ "$candidate" =~ ^python3\.[0-9]+$ ]]; then
            PYTHON_CANDIDATES+=("$candidate")
        fi
    done < <(compgen -c python3.)
    PYTHON_CANDIDATES+=(python3)
    for candidate in "${PYTHON_CANDIDATES[@]}"; do
        if command -v "$candidate" >/dev/null 2>&1 && is_supported_python "$candidate"; then
            PYTHON_BIN="$(command -v "$candidate")"
            break
        fi
    done
    if [[ -z "$PYTHON_BIN" ]]; then
        printf '\nERROR: Python 3.12 or newer was not found. No system Python was changed.\n' >&2
        python_prerequisite_help >&2
        if [[ "$PACKAGE_MANAGER" == unavailable ]]; then
            printf '  No supported package manager was detected; ask your Linux administrator for the prerequisite.\n' >&2
        fi
        exit 1
    fi
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())')"
info "Using Python ${PYTHON_VERSION} at ${PYTHON_BIN}"
if ! "$PYTHON_BIN" -c 'import venv, ensurepip' >/dev/null 2>&1; then
    printf 'ERROR: Python %s is missing venv or ensurepip support.\n' "$PYTHON_VERSION" >&2
    python_prerequisite_help >&2
    exit 1
fi

VENV_DIR="${PROJECT_ROOT}/.venv"
VENV_PYTHON="${VENV_DIR}/bin/python"
if [[ -L "$VENV_DIR" ]]; then
    fail "Refusing to use .venv because it is a symlink: ${VENV_DIR}"
fi
if [[ -e "$VENV_DIR" ]]; then
    [[ -d "$VENV_DIR" ]] || fail "${VENV_DIR} exists but is not a directory. Move it aside and rerun."
    [[ -x "$VENV_PYTHON" ]] || fail "Existing .venv is incomplete. Back it up or remove it, then rerun setup."
    if ! is_supported_python "$VENV_PYTHON"; then
        EXISTING_VERSION="$("$VENV_PYTHON" --version 2>&1 || true)"
        fail "Existing .venv uses ${EXISTING_VERSION}, but Python >=3.12 is required. Back it up or remove it, then rerun."
    fi
    "$VENV_PYTHON" -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)' \
        || fail "${VENV_PYTHON} is not an isolated virtual-environment interpreter."
    info "Reusing existing project virtual environment"
else
    info "Creating project-local virtual environment at ${VENV_DIR}"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

[[ -x "$VENV_PYTHON" ]] || fail "Virtual environment creation did not produce ${VENV_PYTHON}."
if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
    info "Bootstrapping pip inside .venv with Python's bundled ensurepip"
    "$VENV_PYTHON" -m ensurepip --upgrade
fi
info "Upgrading pip inside .venv"
"$VENV_PYTHON" -m pip install --upgrade pip

info "Installing plaivid-cli and its development/build dependencies from pyproject.toml"
(
    cd "$PROJECT_ROOT"
    "$VENV_PYTHON" -m pip install --editable '.[dev]'
)

info "Checking the installed plaivid command (help only; no PVM connection)"
"${VENV_DIR}/bin/plaivid" --help >/dev/null
printf '\nSetup complete.\n'
printf 'Activate the environment with:\n  source %q\n' "${VENV_DIR}/bin/activate"
printf 'Then run tests/build with:\n  python -m pytest -q --ignore=tests/smoke.py\n  python -m build --wheel\n'
