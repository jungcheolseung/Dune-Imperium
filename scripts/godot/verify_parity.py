"""Compare browser/native picks and resulting snapshots from identical saves.

Requires the optional developer Playwright installation and Chromium. Nothing
is added to the portable player's dependencies. Fixtures use legal engine
actions only; the test never edits a hand, rule, resource or decision frame.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from parity_fixtures import ensure_extra_saves

from dune_imperium.agents import HeuristicAgent
from dune_imperium.godot_client.launch import PROJECT, ensure_godot, free_port
from dune_imperium.godot_client.ui_data import write_ui_data
from dune_imperium.launcher.command import build_plan
from dune_imperium.launcher.settings import LauncherSettings
from dune_imperium.launcher.supervisor import ServerProcess
from dune_imperium.paths import PROJECT_ROOT, TMP_DIR
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager


def fixtures(directory: Path) -> dict[str, str]:
    store = SaveStore(directory)
    names = {str(row['name']): str(row['save_id']) for row in store.list()}
    for name, script in (
        ('navigation-chamber', 'navigation_chamber_saves.py'),
        ('held-acquire', 'held_choice_saves.py'),
    ):
        if name not in names:
            subprocess.run([
                sys.executable, str(PROJECT_ROOT / 'scripts/e2e/fixtures' / script),
                str(directory),
            ], cwd=PROJECT_ROOT, check=True, timeout=180, capture_output=True)
            names.update({str(row['name']): str(row['save_id'])
                          for row in store.list()})
    if 'parity-basic' not in names:
        manager: Any = GameSessionManager()
        summary = manager.create_game(('human',) * 4, game_seed=11)
        saved = store.write(manager.save_game(
            str(summary['game_id']), name='parity-basic'))
        names['parity-basic'] = str(saved['save_id'])
    if 'parity-graft' not in names:
        manager = GameSessionManager()
        summary = manager.create_game(('human',) * 4, immortality=True, game_seed=1)
        gid = str(summary['game_id'])
        agents = [HeuristicAgent(seed=200 + seat) for seat in range(4)]
        for _ in range(2000):
            if summary['finished']:
                raise RuntimeError('graft fixture ended before its target')
            if summary['confirmation'] is not None:
                summary = manager.confirm_turn(
                    gid, int(summary['confirmation']), int(summary['revision']))
                continue
            owner = int(summary['decision']['owner'])
            session = manager._get(gid)
            actions = session.engine.legal_actions(session.state, owner)
            if any(a.action_id == 'agent_turn' and dict(a.arguments).get('graft')
                   for a in actions):
                saved = store.write(manager.save_game(gid, name='parity-graft'))
                names['parity-graft'] = str(saved['save_id'])
                break
            buy = next((a for a in actions if a.action_id == 'acquire_tleilaxu'), None)
            chosen = buy if buy is not None else agents[owner].choose_action(
                session.engine.observe(session.state, owner), actions)
            summary = manager.apply_action(
                gid, owner, int(summary['revision']), actions.index(chosen))
        else:
            raise RuntimeError('bounded graft fixture did not reach its target')
    return names


def request(base: str, path: str, body: dict[str, Any] | None = None) -> Any:
    req = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                  headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def digest(snapshot: dict[str, Any]) -> str:
    # Independent restored games have independent IDs/clocks/log epochs.
    # Compare the complete authorized gameplay projection and actual moves.
    projection = {key: snapshot[key] for key in ('view', 'actions')}
    projection['decision'] = snapshot['summary']['decision']
    projection['confirmation'] = snapshot['summary']['confirmation']
    projection['revision'] = snapshot['summary']['revision']
    projection['undo_count'] = snapshot['summary']['undo_count']
    projection['moves'] = snapshot.get('log', {}).get('entries', [])
    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: scrub(part) for key, part in value.items()
                    if key not in ('game_id', 'clock')}
        if isinstance(value, list):
            return [scrub(part) for part in value]
        return value
    encoded = json.dumps(scrub(projection), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def click_ref(page: Any, ref: str, *, space: bool = False) -> None:
    selector = (f'.hotspot[data-space="{ref}"], .space-row[data-space="{ref}"]'
                if space else f'.vcard[data-instance="{ref}"]')
    node = page.locator(selector).first
    node.scroll_into_view_if_needed()
    page.wait_for_function('''(sel) => [...document.querySelectorAll(sel)].every(
        node => [...node.querySelectorAll('img')].every(i => i.complete))
    ''', arg=selector)
    node.click()


def browser_case(page: Any, base: str, game: str, kind: str,
                 *, space_first: bool = False) -> dict[str, Any]:
    page.goto(base + '/#game=' + game)
    page.wait_for_function('''state.view !== null && refreshFlight === null
        && !state.busy''')
    revision = page.evaluate('state.summary.revision')
    seat = page.evaluate('state.viewSeat')
    case: dict[str, Any] = {
        'kind': kind, 'seat': seat, 'space_first': space_first}
    placements = page.evaluate('placementActions()')
    if kind == 'held':
        chosen = page.evaluate('''state.actions.actions.find(a =>
            a.sent_by_turn_end && (a.arguments.instance_id || a.arguments.card_id))
        ''')
        assert chosen, 'fixture must provide a held table card'
        ref = chosen['arguments'].get('instance_id', chosen['arguments'].get('card_id'))
        case.update(card=ref, index=chosen['index'], steps=1)
        click_ref(page, ref)
        assert page.evaluate('heldChoice().index') == chosen['index']
        click_ref(page, ref)
        assert page.evaluate('heldChoice().index') == chosen['index']
        assert page.evaluate('state.summary.revision') == revision
        row = f'.action-item[data-index="{chosen["index"]}"] button'
        page.locator(row).first.click()
        assert page.evaluate('heldChoice()') is None
        click_ref(page, ref)
        page.locator('.held-send-row button').click()
    else:
        if kind == 'multiple':
            chosen = next(a for a in placements
                          if a['arguments']['space_id'] == 'spice_refinery'
                          and a['arguments'].get('discount') == 'spice')
        elif kind == 'graft':
            chosen = next(a for a in placements if a['arguments'].get('graft'))
        else:
            pairs = Counter((a['arguments']['card_id'], a['arguments']['space_id'])
                            for a in placements)
            chosen = next(a for a in placements if pairs[
                (a['arguments']['card_id'], a['arguments']['space_id'])] == 1)
        card = chosen['arguments']['card_id']
        space = chosen['arguments']['space_id']
        case.update(card=card, space=space, steps=2 if kind == 'graft' else 1)
        click_ref(page, space if space_first else card, space=space_first)
        assert page.evaluate('state.summary.revision') == revision
        case['lit'] = page.evaluate('''(spaceFirst) =>
            [...document.querySelectorAll(spaceFirst
                ? '.hand-cards .vcard.legal' : '.hotspot.legal, .space-row.legal')]
            .map(n => spaceFirst ? n.dataset.instance : n.dataset.space).sort()
        ''', space_first)
        if kind == 'graft':
            partner = page.evaluate('''(card) => state.view.private.hand
                .find(ref => canPair(card, ref))''', card)
            assert partner, 'real graft position must have a second hand card'
            case['partner'] = partner
            click_ref(page, partner)
            assert page.evaluate('state.pick.partnerId') == partner
            routes = page.evaluate('pickCandidates().map(a => a.arguments.space_id)')
            # Choose a route with one distinct DTO, so only the partner follows.
            route_counts = Counter(routes)
            space = next(route for route in routes if route_counts[route] == 1)
            case['space'] = space
        click_ref(page, card if space_first else space, space=not space_first)
        if kind == 'multiple':
            assert page.evaluate('state.summary.revision') == revision
            candidates = page.evaluate('pickCandidates()')
            case['candidates'] = sorted(a['index'] for a in candidates)
            shown = page.locator('#actions .action-item').evaluate_all(
                '(nodes) => nodes.map(n => Number(n.dataset.index))')
            assert all(index in shown for index in case['candidates'])
            case['costs'] = page.evaluate('''() => pickCandidates().map(a => ({
                index: a.index, paid: paidCost(spaceOptionsFor(
                    state.catalog.spaces[a.arguments.space_id])[
                    a.arguments.cost_option || 0].cost, a.arguments.discount)
            }))''')
            case['index'] = chosen['index']
            selector = ('#actions .action-item'
                        f'[data-index="{chosen["index"]}"] button')
            page.locator(selector).first.click()
    page.wait_for_function('''(target) => !state.busy && refreshFlight === null
        && state.summary.revision === target''', arg=revision + case['steps'])
    snapshot = request(base, f'/games/{game}/snapshot?seat={seat}')
    case['expected'] = digest(snapshot)
    return case


def info_case(page: Any, base: str, game: str, language: str) -> dict[str, Any]:
    page.goto(base + '/#game=' + game)
    page.wait_for_function('state.view !== null && refreshFlight === null')
    page.evaluate('(language) => setLanguage(language)', language)
    seat = page.evaluate('state.viewSeat')
    page.locator('#private-zone .hand-counts .stat').first.click()
    page.wait_for_function('!document.getElementById("pile-viewer").hidden')
    case: dict[str, Any] = page.evaluate('''() => ({
        kind: 'deck', top: state.view.private.peeked_card_id,
        title: document.querySelector('#pile-viewer .popover-title').textContent,
        notes: [...document.querySelectorAll('#pile-viewer .popover-note')]
            .map(node => node.textContent),
        groups: [...document.querySelectorAll('#pile-viewer .vcard')].map(node => ({
            ref: node.dataset.instance, top: node.classList.contains('deck-top'),
            count: Number((node.querySelector('.vcard-badge')?.textContent || '')
                .replace('×', '')) || 1
        })),
        choice_picture: document.querySelectorAll('#actions .deck-top-choice-card')
            .length,
        labels: state.actions.actions.filter(a => DECK_TOP_CHOICES.has(a.action_id))
            .map(a => {
                const button = document.querySelector(
                    `#actions .action-item[data-index="${a.index}"] button`);
                const copy = button.cloneNode(true);
                for (const n of copy.querySelectorAll(
                    '.irreversible-badge, .shortfall-badge, .strength-preview'))
                    n.remove();
                for (const n of copy.querySelectorAll('.amount'))
                    n.replaceWith(n.title);
                for (const n of copy.querySelectorAll('img'))
                    n.replaceWith(n.alt);
                return {index: a.index, text: copy.textContent.trim()};
            })
    })''')
    case.update(language=language, seat=seat)
    case['expected'] = digest(request(base, f'/games/{game}/snapshot?seat={seat}'))
    return case


def main() -> int:
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True)
    parser.add_argument('--chromium', default=os.environ.get('E2E_CHROMIUM'))
    parser.add_argument('--baseline-project', type=Path,
                        help='Run old unique/held behavior to prove regressions')
    parser.add_argument('--suite', choices=('core', 'info'), default='core')
    args = parser.parse_args()
    binary = ensure_godot(args.godot)
    directory = TMP_DIR / 'godot/parity'
    saves = directory / 'saves'
    saves.mkdir(parents=True, exist_ok=True)
    names = fixtures(saves)
    if args.suite != 'core':
        names.update(ensure_extra_saves(saves))
    labels = directory / 'labels.json'
    write_ui_data(labels)
    empty = directory / 'empty-assets'
    empty.mkdir(exist_ok=True)
    assets = PROJECT_ROOT / 'assets'
    settings = LauncherSettings(mode='local', host='127.0.0.1', port=free_port(),
                               ai_pace='instant', open_browser=False,
                               saves_dir=str(saves),
                               assets_dir=str(assets if assets.is_dir() else empty))
    server = ServerProcess(build_plan(settings, None), log_dir=directory / 'server')
    base = f'http://127.0.0.1:{settings.port}'
    cases: list[dict[str, Any]] = []
    try:
        server.start()
        server.wait_ready()
        with sync_playwright() as playwright:
            options: dict[str, Any] = {'headless': True, 'args': [
                '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, '
                'EXCLUDE localhost']}
            if args.chromium:
                options['executable_path'] = args.chromium
            else:
                options['channel'] = 'chrome'
            browser = playwright.chromium.launch(**options)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors: list[str] = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            scenarios = [
                ('unique', 'parity-basic', False), ('unique', 'parity-basic', True),
                ('multiple', 'navigation-chamber', False),
                ('graft', 'parity-graft', False), ('held', 'held-acquire', False)]
            if args.baseline_project:
                scenarios = [scenarios[0], scenarios[-1]]
            if args.suite == 'info':
                scenarios = [('deck', name, False) for name in
                             ('parity-glowglobes', 'parity-controlled')]
            for kind, name, space_first in scenarios:
                print(f'Compare {kind} (space first: {space_first})', flush=True)
                path = '/saves/' + names[name] + '/load'
                for language in ('ko', 'en') if args.suite == 'info' else ('ko',):
                    browser_game = request(base, path, {})['game_id']
                    case = (info_case(page, base, browser_game, language)
                            if args.suite == 'info' else browser_case(
                                page, base, browser_game, kind,
                                space_first=space_first))
                    case['game'] = request(base, path, {})['game_id']
                    cases.append(case)
            browser.close()
            if errors:
                raise RuntimeError('browser script error: ' + errors[0])
        scenario_file = directory / 'scenarios.json'
        scenario_file.write_text(json.dumps(cases, ensure_ascii=False),
                                 encoding='utf-8')
        project = (args.baseline_project or PROJECT).resolve()
        env = dict(os.environ, XDG_CONFIG_HOME=str(directory / 'config'),
                   XDG_DATA_HOME=str(directory / 'data'))
        log_file = directory / (
            'baseline.log' if args.baseline_project else 'native.log')
        script = 'info_parity_test.gd' if args.suite == 'info' else 'parity_test.gd'
        with log_file.open('wb') as output:
            result = subprocess.run([
                str(binary), '--headless', '--path', str(project),
                '--script', script, '--log-file',
                str(directory / 'engine.log'), '--', f'--server={base}',
                f'--labels={labels}', f'--scenarios={scenario_file}',
            ], cwd=PROJECT_ROOT, env=env, stdout=output,
                stderr=subprocess.STDOUT, timeout=150, check=False)
        log = log_file.read_text(encoding='utf-8')
        if result.returncode or 'GODOT_PARITY_OK' not in log or 'ERROR:' in log:
            print(log, file=sys.stderr)
            return 1
        for case in cases:
            path = f'/games/{case["game"]}/snapshot?seat={case["seat"]}'
            actual = digest(request(base, path))
            if actual != case['expected']:
                raise RuntimeError(
                    'resulting gameplay snapshot differs: ' + case['kind'])
        count = log.split('GODOT_PARITY_OK ')[1].splitlines()[0]
        print(f'Browser/native parity verified: {len(cases)} identical gameplay '
              f'snapshots; {count} native checks.')
    finally:
        stopped = server.stop()
        if not stopped.port_free:
            raise RuntimeError('parity server did not release its port')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
