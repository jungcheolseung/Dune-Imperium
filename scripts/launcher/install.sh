#!/bin/sh
# Dune Imperium: install or update the game on a Mac with one line, without
# git and without a Python of your own (docs/remote-play-host-guide.md,
# "한 줄 설치"). In the Terminal app:
#
#   curl -fsSL https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.sh | sh
#
# Everything goes in one folder, "~/Dune Imperium" unless
# DUNE_IMPERIUM_HOME names another: the public repository's source snapshot,
# uv, Python, the packages, and later the saves and the launcher's settings.
# Nothing is written outside it and PATH is not changed, so deleting the
# folder removes all of it. Running the same line again updates the game and
# keeps saves/, local/, checkpoints/ and assets/.
#
# Files fetched this way carry no quarantine flag, so Gatekeeper does not
# stop them, and the launcher app is made on this Mac (shortcuts.py).
#
# For tests and special cases:
#   DUNE_IMPERIUM_HOME     the install folder (default: $HOME/Dune Imperium)
#   DUNE_IMPERIUM_ARCHIVE  the source snapshot, a .tar.gz URL (file:// works)
#   DUNE_IMPERIUM_NO_OPEN  1: do not open the folder and the launcher at the end
#
# Everything sits in main(), called on the last line: sh reads a piped script
# as it goes, so a half-downloaded script must not run, and no command may
# read the rest of it from standard input (each gets </dev/null).

# The uv release this installs (its installer checks the download's sha256).
# Keep it at the uv that wrote uv.lock.
UV_VERSION="0.11.24"
ARCHIVE_URL="https://github.com/jungcheolseung/Dune-Imperium/archive/refs/heads/master.tar.gz"
APP_NAME="Dune Imperium Server"

say() {
    printf '%s\n' "$*"
}

fail() {
    printf '\n설치를 멈췄습니다: %s\n' "$*" >&2
    exit 1
}

main() {
    set -eu
    if [ "$(uname -s)" != "Darwin" ]; then
        fail "macOS용 설치입니다. Windows는 PowerShell용 한 줄을, Linux·WSL은 호스트 가이드의 설치 방법을 쓰세요."
    fi
    for tool in curl tar; do
        command -v "$tool" >/dev/null 2>&1 || fail "$tool 명령이 없습니다."
    done

    home="${DUNE_IMPERIUM_HOME:-$HOME/Dune Imperium}"
    archive="${DUNE_IMPERIUM_ARCHIVE:-$ARCHIVE_URL}"
    runtime="$home/runtime"
    marker="$runtime/install-marker.txt"

    # Only a folder this script made, or an empty or missing one: an update
    # replaces the snapshot's folders (src/, docs/ ...) wholesale.
    if [ -e "$home/.git" ]; then
        fail "$home 은(는) git으로 받은 저장소입니다. 그 폴더는 git pull로 업데이트하세요."
    fi
    if [ -d "$home" ] && [ ! -f "$marker" ] && [ -n "$(ls -A "$home" 2>/dev/null)" ]; then
        fail "$home 에 이미 다른 파일이 있습니다. 비우거나 DUNE_IMPERIUM_HOME으로 다른 폴더를 지정하세요."
    fi
    mkdir -p "$runtime" || fail "$home 폴더를 만들지 못했습니다."
    [ -f "$marker" ] || say "Made by scripts/launcher/install.sh; an update may replace this folder's files." >"$marker"
    cd "$home" || fail "$home 폴더로 들어가지 못했습니다."

    # An update under a running launcher would mix old and new code; the
    # launcher's own single-instance lock tells (instance.py).
    if [ -x .venv/bin/python ]; then
        status=0
        .venv/bin/python -c "import sys
from dune_imperium.launcher.instance import InstanceLock
sys.exit(0 if InstanceLock().acquire() else 3)" </dev/null >/dev/null 2>&1 || status=$?
        if [ "$status" -eq 3 ]; then
            fail "서버 런처가 켜져 있습니다. 런처 창을 닫은 뒤 같은 줄을 다시 실행하세요."
        fi
    fi

    say "1/4 uv $UV_VERSION 준비"
    uv="$runtime/bin/uv"
    if [ ! -x "$uv" ] || [ "$("$uv" --version 2>/dev/null | cut -d' ' -f2)" != "$UV_VERSION" ]; then
        curl -fsSL --proto '=https' --retry 3 -o "$runtime/uv-installer.sh" \
            "https://astral.sh/uv/$UV_VERSION/install.sh" </dev/null ||
            fail "uv 설치 파일을 받지 못했습니다. 인터넷 연결을 확인하고 같은 줄을 다시 실행하세요."
        UV_UNMANAGED_INSTALL="$runtime/bin" sh "$runtime/uv-installer.sh" --quiet </dev/null ||
            fail "uv를 설치하지 못했습니다."
        rm -f "$runtime/uv-installer.sh"
    fi
    [ -x "$uv" ] || fail "uv가 $runtime/bin 에 없습니다."

    say "2/4 게임 파일 받기"
    work="$runtime/download"
    rm -rf "$work"
    mkdir -p "$work/new"
    curl -fL --proto '=https,file' --retry 3 --progress-bar -o "$work/game.tar.gz" "$archive" </dev/null ||
        fail "게임 파일을 받지 못했습니다($archive). 인터넷 연결을 확인하고 같은 줄을 다시 실행하세요."
    tar -xzf "$work/game.tar.gz" -C "$work/new" </dev/null || fail "받은 게임 파일을 풀지 못했습니다."
    set -- "$work/new"/*
    snapshot="$1"
    if [ "$#" -ne 1 ] || [ ! -f "$snapshot/pyproject.toml" ] || [ ! -f "$snapshot/uv.lock" ] ||
        [ ! -d "$snapshot/src/dune_imperium" ]; then
        fail "받은 게임 파일의 모양이 예상과 다릅니다."
    fi
    # Each top-level entry of the snapshot replaces the old one. What the
    # snapshot never holds (all git-ignored) stays: the saves, the launcher's
    # settings, networks, pictures, the environment and this runtime.
    for entry in "$snapshot"/* "$snapshot"/.[!.]* "$snapshot"/..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        name="${entry##*/}"
        case "$name" in
            runtime | saves | local | checkpoints | assets | tmp | .venv | "$APP_NAME.app") continue ;;
        esac
        rm -rf "./$name"
        mv "$entry" "./$name" || fail "$name 을(를) 옮기지 못했습니다."
    done
    rm -rf "$work"

    say "3/4 Python과 패키지 설치(처음에는 몇 분 걸립니다)"
    unset VIRTUAL_ENV CONDA_PREFIX PYTHONHOME PYTHONPATH || true
    # uv's Python, its cache and nothing else in this folder.
    UV_PYTHON_INSTALL_DIR="$runtime/python" UV_CACHE_DIR="$runtime/cache" \
        UV_PYTHON_INSTALL_BIN=0 UV_NO_MODIFY_PATH=1 \
        "$uv" sync --locked --no-dev --extra ui --managed-python </dev/null ||
        fail "패키지를 설치하지 못했습니다. 인터넷 연결을 확인하고 같은 줄을 다시 실행하세요."

    say "4/4 런처 앱 만들기"
    .venv/bin/python -m dune_imperium.launcher.cli --make-shortcut </dev/null ||
        fail "런처 앱을 만들지 못했습니다."

    say ""
    say "설치를 마쳤습니다: $home"
    say "다음부터는 이 폴더의 '$APP_NAME' 앱을 더블클릭하세요(Dock에 끌어다 두면 편합니다)."
    say "업데이트는 같은 줄을 다시 실행하고, 지울 때는 폴더를 통째로 휴지통에 넣습니다."
    if [ "${DUNE_IMPERIUM_NO_OPEN:-}" != "1" ]; then
        open "$home" </dev/null || true
        open "$home/$APP_NAME.app" </dev/null || true
    fi
}

main "$@"
