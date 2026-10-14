"""Bounded legal walks for private-information and quantity UI comparisons."""

from pathlib import Path
from typing import Any

from dune_imperium.agents import HeuristicAgent
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager


def ensure_extra_saves(directory: Path) -> dict[str, str]:
    store = SaveStore(directory)
    found = {str(row['name']): str(row['save_id']) for row in store.list()}

    def save(manager: Any, game: str, name: str) -> None:
        if name not in found:
            saved = store.write(manager.save_game(game, name=name))
            found[name] = str(saved['save_id'])

    wanted = {'parity-glowglobes', 'parity-controlled', 'parity-deploy',
              'parity-bid', 'parity-call', 'parity-zero-bid', 'parity-zero-call'}
    for seed in (21, 58, 87, 1, 3, 7, 11, 17, 24, 32, 42, 64):
        if wanted <= found.keys():
            break
        manager: Any = GameSessionManager()
        summary = manager.create_game(
            ('human',) * 4, game_seed=seed, choam_module=True,
            arrakeen_scouts=True, bloodlines=True, tech_module=True,
            promo_cards=True, leader_draft=True)
        game = str(summary['game_id'])
        agents = [HeuristicAgent(seed=9000 + seed * 4 + seat) for seat in range(4)]
        for _ in range(2400):
            if summary['finished']:
                break
            if summary['confirmation'] is not None:
                summary = manager.confirm_turn(
                    game, int(summary['confirmation']), int(summary['revision']))
                continue
            owner = int(summary['decision']['owner'])
            session = manager._get(game)
            actions = session.engine.legal_actions(session.state, owner)
            view = manager.view(game, owner)
            top = view['private'].get('peeked_card_id')
            if top and top in view['private']['deck_cards']:
                if any(a.action_id == 'put_back_top_card' for a in actions):
                    save(manager, game, 'parity-controlled')
                if 'glowglobes' in view['players'][owner].get('tech_ids', []):
                    save(manager, game, 'parity-glowglobes')
            for action_id, name in (
                ('deploy_troops', 'parity-deploy'),
                ('scouts_bid', 'parity-bid'), ('scouts_call', 'parity-call'),
            ):
                family = [a for a in actions if a.action_id == action_id]
                if len(family) >= 3:
                    save(manager, game, name)
                if len(family) == 1 and dict(family[0].arguments).get('count') == 0:
                    if action_id == 'scouts_bid':
                        save(manager, game, 'parity-zero-bid')
                    if action_id == 'scouts_call':
                        save(manager, game, 'parity-zero-call')
            if wanted <= found.keys():
                break
            # Choose only actions the engine actually offers. Steer toward
            # the two information effects without editing any game state.
            preferred = next((a for a in actions if
                (a.action_id == 'pick_leader'
                 and dict(a.arguments).get('leader_id') == 'piter_de_vries')
                or (a.action_id == 'acquire_tech'
                 and dict(a.arguments).get('tech_id') == 'glowglobes')
                or (a.action_id == 'play_intrigue'
                    and ':twisted_controlled:' in
                    str(dict(a.arguments).get('card_id', ''))
                    and dict(a.arguments).get('option', 0) == 0)
            ), None)
            piter = view['players'][owner]['leader_id'] == 'piter_de_vries'
            if preferred is None and piter:
                preferred = next((a for a in actions if
                    (a.action_id == 'agent_turn'
                     and dict(a.arguments).get('space_id') == 'espionage')
                    or a.action_id == 'use_intrigue_effect'), None)
            chosen = preferred
            if chosen is None:
                chosen = agents[owner].choose_action(
                    session.engine.observe(session.state, owner), actions)
            summary = manager.apply_action(
                game, owner, int(summary['revision']), actions.index(chosen))
    missing = wanted - found.keys()
    if missing:
        raise RuntimeError('bounded UI fixture walk missed: '
                           + ', '.join(sorted(missing)))
    return {name: found[name] for name in wanted}
