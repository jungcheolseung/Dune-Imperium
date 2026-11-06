#!/usr/bin/env bash
# Dune Imperium 서버 런처: WSL에서 처음 한 번 설치 (docs/server-launcher-plan.md 5.13).
# WSL 터미널에서 실행한다. 의존성을 맞추고, 창의 한글을 그릴 Tk를 받아 두고,
# 프로젝트 폴더에 Windows 바로가기 "Dune Imperium Server.lnk"를 만들고, 런처를
# 띄운다. 그 뒤로는 탐색기에서 그 바로가기만 더블클릭하면 된다.
cd "$(dirname "$0")/../.." || exit 1
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv를 찾지 못했습니다. 먼저 설치하세요:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

extras=(--extra ui)
read -r -p "탐색 AI(학습한 망, 처음 한 번 약 125 MB를 내려받음)도 쓸까요? [y/N] " answer
case "$answer" in
  [yY]*) extras+=(--extra rl --extra train) ;;
esac

# --inexact: 이미 있는 개발·학습 패키지는 지우지 않는다. 탐색 AI는 torch
# (train)와 numpy·gymnasium·pettingzoo(rl)가 모두 있어야 한다.
if ! uv sync --locked --inexact "${extras[@]}"; then
  echo "의존성 설치에 실패했습니다. 위의 메시지를 확인하세요."
  exit 1
fi

# uv의 Python은 Xft 없이 빌드된 Tk라 한글을 \uXXXX로 그린다. Ubuntu의 libtk8.6
# 패키지를 sudo 없이 받아 local/xft-tk에 풀어 두면 런처가 그것을 쓴다
# (src/dune_imperium/launcher/wsl.py). 시스템에 libtk8.6이 있으면 그쪽이 먼저다.
tk_dir=local/xft-tk
if [[ ! -f $tk_dir/usr/share/tcltk/tk8.6/tk.tcl ]]; then
  mkdir -p tmp "$tk_dir"
  work=$(mktemp -d tmp/xft-tk.XXXXXX)
  if (cd "$work" && apt-get download libtk8.6) \
    && dpkg-deb -x "$work"/libtk8.6_*.deb "$tk_dir"; then
    echo "한글을 그릴 Tk를 받았습니다: $tk_dir"
  else
    echo "주의: Tk를 받지 못했습니다. 창의 한글이 \\uXXXX로 보이면"
    echo "  sudo apt install libtk8.6"
  fi
  rm -rf "$work"
fi

if ! ./.venv/bin/python -m dune_imperium.launcher.cli --make-shortcut; then
  exit 1
fi
setsid ./.venv/bin/python -m dune_imperium.launcher </dev/null >/dev/null 2>&1 &
echo "완료: 다음부터는 탐색기에서 프로젝트 폴더의 'Dune Imperium Server' 바로가기를"
echo "더블클릭하세요: $(wslpath -w "$PWD")"
echo "(바탕 화면이나 작업 표시줄에 끌어다 놓으면 더 편합니다.)"
