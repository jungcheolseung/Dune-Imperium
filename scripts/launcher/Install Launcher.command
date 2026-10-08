#!/bin/zsh
# Dune Imperium 서버 런처: 처음 한 번 설치 (docs/server-launcher-plan.md 5.10).
# Finder에서 더블클릭하면 터미널이 한 번 열린다. 의존성을 맞추고, 프로젝트
# 폴더에 "Dune Imperium Server" 앱을 만들고, 런처를 띄운다. 그 뒤로는 그 앱만
# 더블클릭하면 된다.
cd "${0:A:h}/../.." || exit 1
# Finder가 띄운 셸에는 uv를 설치한 곳이 PATH에 없을 수 있다.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

pause() {
  read -k 1 "?아무 키나 누르면 창을 닫습니다... "
  echo
}

if ! command -v uv >/dev/null 2>&1; then
  echo "uv를 찾지 못했습니다. 터미널에서 먼저 설치하세요:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  pause
  exit 1
fi

extras=(--extra ui)
if read -q "answer?탐색 AI(학습한 망, 처음 한 번 약 125 MB를 내려받음)도 쓸까요? [y/N] "; then
  extras+=(--extra train)
fi
echo

# --inexact: 이미 있는 개발·학습 패키지(rl, train)는 지우지 않는다.
if ! uv sync --locked --inexact "${extras[@]}"; then
  echo "의존성 설치에 실패했습니다. 위의 메시지를 확인하세요."
  pause
  exit 1
fi
if ! ./.venv/bin/python -m dune_imperium.launcher.cli --make-shortcut; then
  pause
  exit 1
fi
open "Dune Imperium Server.app"
echo "완료: 다음부터는 프로젝트 폴더의 'Dune Imperium Server' 앱을 더블클릭하세요."
echo "(Dock에 끌어다 놓으면 더 편합니다.)"
pause
