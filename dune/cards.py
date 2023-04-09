from dune.status import Imperium, AgentIcon


start_cards = {
    'Convincing Argument': Imperium(
        name='Convincing Argument',
        starting=True,
        reveal_persuation=2,
    ),
    'Dagger': Imperium(
        name='Dagger',
        agent_icons=[AgentIcon.LANDSRAAD],
        starting=True,
        reveal_swords=1,
    ),
    'Diplomacy': Imperium(
        'Diplomacy',
        agent_icons=[AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD, AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN],
        starting=True,
        reveal_persuation=1,
    ),
    'Dune, The Desert Planet': Imperium(
        'Dune, The Desert Planet',
        agent_icons=[AgentIcon.SPICE_TRADE],
        starting=True,
        reveal_persuation=1,
    ),
    'Reconnaissance': Imperium(
        'Reconnaissance',
        agent_icons=[AgentIcon.CITY],
        starting=True,
        reveal_persuation=1,
    ),
    'Seek Allies': Imperium(
        'Seek Allies',
        agent_box=[], #TODO: add
        agent_icons=[AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD, AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN],
        starting=True,
    ),
    'Signet Ring': Imperium(
        'Signet Ring',
        agent_box=[], #TODO: add
        agent_icons=[AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE],
        starting=True,
        reveal_persuation=1,
    ),
    'Control the Spice': Imperium(
        'Control the Spice',
        agent_box=[], #TODO: add
        reveal_box=[], #TODO: add
        agent_icons=[AgentIcon.SPICE_TRADE],
        starting=True,
        reveal_persuation=1,
    ),
}


if __name__ == '__main__':
    print(start_cards)