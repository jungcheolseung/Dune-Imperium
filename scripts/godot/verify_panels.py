"""Check expansion panels against legal saved games and direct server actions."""

import argparse
import json
import os
import subprocess
import sys
from typing import Any

from parity_fixtures import ensure_extra_saves
from verify_parity import (
    choice_fixtures,
    digest,
    fixture_saves,
    fixtures,
    request,
)

from dune_imperium.godot_client.launch import PROJECT, ensure_godot, free_port
from dune_imperium.godot_client.ui_data import write_ui_data
from dune_imperium.launcher.command import build_plan
from dune_imperium.launcher.settings import LauncherSettings
from dune_imperium.launcher.supervisor import ServerProcess
from dune_imperium.paths import PROJECT_ROOT, TMP_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True)
    parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    binary = ensure_godot(args.godot)
    directory = TMP_DIR / 'godot/panels'
    directory.mkdir(parents=True, exist_ok=True)
    saves = fixture_saves()
    names = fixtures(saves)
    names.update(ensure_extra_saves(saves))
    choices = choice_fixtures(saves)
    names.update({name: row['save_id'] for name, row in choices.items()})
    labels = directory / 'labels.json'
    write_ui_data(labels)
    settings = LauncherSettings(
        mode='local', host='127.0.0.1', port=free_port(), ai_pace='instant',
        open_browser=False, saves_dir=str(saves),
        assets_dir=str(PROJECT_ROOT / 'assets'),
    )
    server = ServerProcess(build_plan(settings, None), log_dir=directory / 'server')
    base = f'http://127.0.0.1:{settings.port}'
    cases: list[dict[str, Any]] = []
    try:
        server.start()
        server.wait_ready()
        for kind, name in (('market', 'choice-contract'),
                           ('research', 'choice-research'),
                           ('scouts', 'parity-bid')):
            load = '/saves/' + names[name] + '/load'
            for language in ('ko', 'en'):
                game = request(base, load, {})['game_id']
                summary = request(base, '/games/' + game)
                seat = int(summary['decision']['owner'])
                path = f'/games/{game}/snapshot?seat={seat}'
                case = dict(game=game, kind=kind, language=language, seat=seat)
                expected = request(base, path)
                if kind == 'research':
                    # Reference result: send the currently offered DTO on a
                    # second restore. No hand/resource/decision is fabricated.
                    reference = request(base, load, {})['game_id']
                    index = int(choices[name]['index'])
                    request(base, f'/games/{reference}/actions', {
                        'seat': seat, 'index': index,
                        'revision': expected['summary']['revision'],
                        'undo_count': expected['summary']['undo_count'],
                    })
                    expected = request(
                        base, f'/games/{reference}/snapshot?seat={seat}')
                    case['index'] = index
                case['expected'] = digest(expected)
                cases.append(case)
        scenarios = directory / 'scenarios.json'
        scenarios.write_text(json.dumps(cases, ensure_ascii=False), encoding='utf-8')
        command = [str(binary), *([] if args.capture else ['--headless']),
                   '--audio-driver', 'Dummy', '--path', str(PROJECT),
                   '--script', 'panel_test.gd', '--log-file',
                   str(directory / 'engine.log'), '--', f'--server={base}',
                   f'--labels={labels}', f'--scenarios={scenarios}']
        if args.capture:
            command.append(f'--evidence={directory / "screenshots"}')
        env = dict(os.environ, XDG_CONFIG_HOME=str(directory / 'config'),
                   XDG_DATA_HOME=str(directory / 'data'))
        log_path = directory / 'native.log'
        with log_path.open('w', encoding='utf-8') as output:
            result = subprocess.run(command, cwd=PROJECT_ROOT, env=env,
                                    stdout=output, stderr=subprocess.STDOUT,
                                    timeout=240, check=False)
        log = log_path.read_text(encoding='utf-8')
        if result.returncode or 'GODOT_PANELS_OK' not in log or 'ERROR:' in log:
            print(log, file=sys.stderr)
            return 1
        for case in cases:
            actual = digest(request(
                base, f'/games/{case["game"]}/snapshot?seat={case["seat"]}'))
            if actual != case['expected']:
                raise RuntimeError('panel changed the authorized result: '
                                   + case['kind'] + '/' + case['language'])
        checks = int(log.split('GODOT_PANELS_OK ')[1].splitlines()[0])
        report = dict(scenarios=len(cases), checks=checks, capture=args.capture)
        (directory / 'report.json').write_text(json.dumps(report), encoding='utf-8')
        print(f'Expansion panels verified: {len(cases)} snapshots; {checks} checks.')
        return 0
    finally:
        if not server.stop().port_free:
            raise RuntimeError('panel server did not release its port')


if __name__ == '__main__':
    raise SystemExit(main())
