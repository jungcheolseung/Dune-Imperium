"""Exercise native local seats, remote cookies, SSE and readonly reviews."""

import argparse
import os
import subprocess
import sys

from dune_imperium.godot_client.launch import PROJECT, ensure_godot, free_port
from dune_imperium.godot_client.ui_data import write_ui_data
from dune_imperium.launcher.command import build_plan
from dune_imperium.launcher.settings import LauncherSettings
from dune_imperium.launcher.supervisor import ServerProcess
from dune_imperium.paths import PROJECT_ROOT, TMP_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True)
    args = parser.parse_args()
    binary = ensure_godot(args.godot)
    directory = TMP_DIR / 'godot' / 'contracts'
    directory.mkdir(parents=True, exist_ok=True)
    empty = directory / 'empty-assets'
    empty.mkdir(exist_ok=True)
    labels = directory / 'labels.json'
    write_ui_data(labels)
    env = dict(os.environ, XDG_CONFIG_HOME=str(directory / 'config'),
               XDG_DATA_HOME=str(directory / 'data'))
    for mode in ('open', 'remote'):
        saves = directory / f'{mode}-saves'
        saves.mkdir(exist_ok=True)
        settings = LauncherSettings(
            mode='local' if mode == 'open' else 'remote', host='127.0.0.1',
            port=free_port(), ai_pace='instant', open_browser=False,
            saves_dir=str(saves), assets_dir=str(empty),
        )
        # A synthetic test key, never any user's administrator credential.
        plan = build_plan(settings, 'a' * 48 if mode == 'remote' else None)
        server = ServerProcess(plan, log_dir=directory / f'{mode}-server')
        try:
            server.start()
            server.wait_ready()
            with (directory / f'{mode}.log').open('wb') as output:
                result = subprocess.run([
                    str(binary), '--headless', '--path', str(PROJECT),
                    '--script', 'contract_test.gd', '--log-file',
                    str(directory / f'{mode}-engine.log'), '--',
                    f'--server=http://127.0.0.1:{settings.port}',
                    f'--labels={labels}', f'--mode={mode}',
                ], cwd=PROJECT_ROOT, env=env, stdout=output,
                    stderr=subprocess.STDOUT, timeout=180, check=False)
            log = (directory / f'{mode}.log').read_text(encoding='utf-8')
            if (result.returncode or 'GODOT_CONTRACTS_OK' not in log
                    or 'SCRIPT ERROR' in log or 'ERROR:' in log):
                print(log, file=sys.stderr)
                return 1
            print(f'Native {mode} contracts verified.')
        finally:
            stopped = server.stop()
            if not stopped.port_free:
                raise RuntimeError('validation server did not release its port')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
