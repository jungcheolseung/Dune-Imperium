"""Korean printed text for the Leader ability/Signet Ring faces (Step K5).

Korean twin of ``leaders.py``'s ``LEADER_FACE_TEXTS`` (feature decided
2026-09-25, "the leader ability text gets Korean transcribed from the
Korean print"). Unlike the engine-*generated* Korean text elsewhere in
``display/*_ko.py``, this text is a direct transcription of the printed
Korean card, the same way ``leaders.py``'s own English is a hand transcript
of the printed English card rather than a composition from
``docs/rules/glossary-ko.md`` words — so it is kept faithful to the print
even where that differs from the engine or from the English display text
(e.g. Liet Kynes' printed ability names *summoning* a sandworm "소환", which
``docs/rules/glossary-ko.md`` reserves for Agent/Spy recall; see the source
note below). No engine or English text changes with this module.

Source: ``leaders_ko.json``, the reconciliation of two independent
transcriptions (A, B) of the Korean-edition card scans
(``cards/ko/{uprising,bloodlines}/leader/*.webp``), read against the English
card and ``leaders.py`` where the two disagreed or where a print detail
needed clarifying; every disagreement and its evidence crop is logged in
``leaders_reconcile.md`` (both files produced 2026-09-25, kept with the
session's other Korean-text preparation, outside this repository). Keyed by
Leader *face* id exactly like ``LEADER_FACE_TEXTS``; a face with no Korean
scan is simply absent here (only ``reverend_mother_jessica``: "no Korean
scan: cards/ko/uprising/leader/ holds only 'Lady Jessica.webp' (front
face)" — the catalog keeps her English).

Icon tokens follow the same ``{term}``/``{term:count}`` syntax as every
other ``_ko`` display module (``static/labels.js`` ``TERMS``, expanded by
``phrase()``): a token immediately followed by a printed digit
(``leaders_ko.json``'s own convention, "a number printed inside an icon
follows the token") becomes the counted form (``{spice}1`` -> ``{spice:1}``)
and a bare printed icon (no digit) stays bare, exactly as printed — a
faithful transcription, not a render-parity match with the English line's
own ``{term:count}``/bare choice (``tokens_ko.py``'s docstring), since nine
of these eighteen faces have no matching generated-text precedent to match
at all (a Leader's ability/Signet is hand-authored prose in both
languages). The one token the transcription used that has no ``TERMS`` row
of its own, ``{spy_deep_cover}`` (Fenring's Signet), is written the same way
``display/structs.py``'s ``_spy_placed_text_ko`` already writes a Spy with
Deep Cover reward: the bare ``{spy}`` icon plus the glossary's own noun,
"(잠복 스파이)" (``Spy with Deep Cover | 잠복 스파이 | [Bloodlines p. 12]``) —
no new icon exists for it (``leaders_reconcile.md``: "which has no icons.py
key"). The seven Agent-box faction/space icons and the Spy Agent icon
(``{agent_icon_bene_gesserit}``, ``{agent_icon_city}``,
``{agent_icon_emperor}``, ``{agent_icon_fremen}``,
``{agent_icon_landsraad}``, ``{agent_icon_spacing_guild}``,
``{agent_icon_spice_trade}``, ``{agent_icon_spy}``) are new ``TERMS`` rows
added with this module, sourced from ``docs/rules/glossary-ko.md``'s "Agent
아이콘 분류" table (`` [Board Guide pp. 1-2]``) and its "Spy" row
(`` [Main p. 20]``) — the Spy Agent icon is a distinct rulebook glyph from
the plain Spy piece icon but names the same rule concept, so it reuses that
row's word rather than inventing a second one.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class LeaderFaceTextKo:
    """Korean display text for one printed Leader face.

    Mirrors ``LeaderFaceText`` (``ability_text``/``signet_text``/``notes``)
    and adds the two printed ability/Signet Ring *names* in Korean
    (``LeaderDefinition.ability_name``/``signet_name``'s counterpart), since
    the Korean UI needs both a Korean name and Korean text for each.
    """

    ability_name: str
    ability_text: str
    signet_name: str
    signet_text: str
    notes: tuple[str, ...] = ()


LEADER_FACE_TEXTS_KO: Mapping[str, LeaderFaceTextKo] = MappingProxyType(
    {
        "gurney_halleck": LeaderFaceTextKo(
            ability_name="항상 웃는 모습",
            ability_text=(
                "공개 차례: 전투 트랙에서 당신의 전투력 총합이 6* 이상이라면: "
                "{persuasion:1} (*6인 게임에서는 10)"
            ),
            signet_name="전쟁 참모",
            # Bare troop icon, no printed number or sentence (= Recruit 1
            # troop); leaders_reconcile.md row 9.
            signet_text="{troop}",
        ),
        "lady_amber_metulli": LeaderFaceTextKo(
            ability_name="사막 정찰대",
            ability_text="공개 차례: 당신의 병력 중 하나를 후퇴 가능.",
            signet_name="재원 확보",
            signet_text="{solari:1} —그리고— 동맹 팩션이 있다면: {spice:1}",
        ),
        "feyd_rautha_harkonnen": LeaderFaceTextKo(
            ability_name="교활한 힘",
            ability_text="공개 차례: {recall_spy} → {sword}{sword}",
            signet_name="개인 훈련",
            signet_text=(
                "훈련 트랙에 놓인 페이드 토큰을 오른쪽으로 1칸 옮기고, "
                "도착한 칸의 보상을 얻음."
            ),
        ),
        "lady_jessica": LeaderFaceTextKo(
            ability_name="다른 기억들",
            ability_text=(
                "당신이 에이전트를 {agent_icon_bene_gesserit} 게임판 장소로 보낼 때, "
                "당신은 모든 당신의 기억을 개인 공급처로 보내면서 그렇게 보낸 기억 1당 "
                "카드 1장을 뽑을 수 있음. 기억을 개인 공급처로 보냈을 경우, "
                "이 지도자를 뒤집음."
            ),
            signet_name="스파이스의 고통",
            signet_text=(
                "{spice:1} → {intrigue} 그리고 당신의 개인 공급처에서 게임판의 "
                "베네 게세리트 영역으로 병력 1을 옮김. 이것은 이제 당신의 기억이 됨."
            ),
        ),
        # reverend_mother_jessica: no Korean scan (only "Lady Jessica.webp"
        # exists under cards/ko/uprising/leader/); the catalog keeps English.
        "lady_margot_fenring": LeaderFaceTextKo(
            ability_name="충성심",
            ability_text=(
                "당신이 {agent_icon_bene_gesserit} 영향력 2에 도달할 때: {spice:2}"
            ),
            signet_name="아라키스 정보원",
            signet_text="{agent_icon_city} 에 {spy}",
        ),
        "muad_dib": LeaderFaceTextKo(
            ability_name="예측 불가능한 적",
            ability_text=(
                "공개 차례: 교전 칸에 당신의 모래벌레가 하나 이상 있다면: {intrigue}"
            ),
            signet_name="솔선수범",
            # Bare draw icon, no printed number or sentence (= Draw 1 card);
            # leaders_reconcile.md row 15.
            signet_text="{draw}",
        ),
        "princess_irulan": LeaderFaceTextKo(
            ability_name="타고난 권리",
            ability_text="당신이 {agent_icon_emperor} 영향력 2에 도달할 때: {intrigue}",
            signet_name="기록자의 통찰",
            signet_text=(
                "선택 가능: 비용이 {persuasion:1} 인 카드 1장 획득해서 당신의 핸드로 "
                "가져옴 —또는— 당신의 핸드에서 카드 1장 폐기. 그 카드의 비용이 "
                "{persuasion:1} 이상이라면: {spice:2}"
            ),
        ),
        "staban_tuek": LeaderFaceTextKo(
            ability_name="스파이스 밀수",
            ability_text=(
                "당신이 정탐하고 있는 메이커 게임판 장소로 다른 플레이어가 "
                "에이전트를 보낼 때마다: {spice:1}"
            ),
            signet_name="보이지 않는 망",
            signet_text=(
                "{spy}\n"
                "놓은 곳에 따라...\n"
                "{agent_icon_landsraad}: {spice:1} → {solari:3}\n"
                "{agent_icon_emperor} / {agent_icon_spacing_guild} / "
                "{agent_icon_bene_gesserit} / {agent_icon_fremen}: "
                "{solari:2} → {intrigue}"
            ),
            # The card's separate red setup box, "한정된 조력자" (Limited
            # Allies) — mirrors LEADER_FACE_TEXTS["staban_tuek"].notes.
            notes=(
                "한정된 조력자: 당신의 카드덱에서 외교를 제외한 채로 게임을 "
                "시작합니다.",
            ),
        ),
        "shaddam_corrino_iv": LeaderFaceTextKo(
            ability_name="사다우카를 거느린 자",
            ability_text=(
                "사다우카 계약 둘 모두를 따로 치워둠. 이 계약들은 게임 진행 중 "
                "당신만 획득할 수 있음."
            ),
            signet_name="알려진 우주의 황제",
            signet_text=(
                "이번 차례에는 교전 칸에 부대가 배치될 수 없음. {solari:1} {troop} "
                "—또는— {solari:3} → {influence_any}"
            ),
        ),
        # Bloodlines Leaders (card faces, 2026-09-25).
        "chani": LeaderFaceTextKo(
            ability_name="전술가",
            ability_text=(
                "당신이 교전 칸에서 병력을 후퇴시키거나 잃을 때마다, 전술 토큰을 "
                "그만큼 오른쪽으로 옮기고, 도달한 칸의 보상을 얻음. 트랙 끝에 "
                "도달하고 나면 토큰을 초기화함."
            ),
            signet_name="페다이킨의 책략",
            # SIGNET REWARD IS TWO DRAW-CARD ICONS, not troops
            # (leaders_reconcile.md finding 1, row 2): the print's icons match
            # Muad'Dib's draw icon, not the troop cube; display/leaders.py's
            # English ("Recruit 2 troops") and rules/leader_abilities.py's
            # _apply_chani_water_payment disagree with the print — that is a
            # rules question for the main session, not changed here. The
            # water icon has no printed number.
            signet_text=(
                "당신의 병력을 원하는 만큼 후퇴. —또는— {agent_icon_fremen} "
                "영향력 2: {water} → {draw}{draw}"
            ),
        ),
        "count_hasimir_fenring": LeaderFaceTextKo(
            ability_name="암살자",
            ability_text="당신이 카드 1장을 폐기할 때마다: {solari:1}",
            # SPY WITH DEEP COVER (leaders_reconcile.md finding 2, row 4): the
            # Signet's Spy icon is a gold cylinder behind a grey one, the same
            # icon as the Deliver Supplies contract's Spy with Deep Cover, not
            # the plain Spy icon the engine currently offers
            # (_leader_spy_placement_actions on EMPEROR_POST_IDS) — a rules
            # question for the main session, not changed here. No dedicated
            # icon exists for it (leaders_reconcile.md: "no icons.py key"),
            # so this follows display/structs.py's own precedent for a Spy
            # with Deep Cover reward: the bare {spy} icon plus the glossary's
            # noun.
            signet_name="코리노와의 접점",
            signet_text=(
                "당신의 플레이 영역에 놓인 카드 1장을 폐기해도 됨. —또는— "
                "{agent_icon_emperor} 에 {spy} (잠복 스파이)"
            ),
        ),
        "duncan_idaho": LeaderFaceTextKo(
            ability_name="기나즈의 소드마스터",
            ability_text=(
                "당신이 지불하는 소드마스터 게임판 장소 비용이 {solari:2} 감소."
            ),
            signet_name="전투 속으로",
            signet_text=(
                "이번 차례에 보낸 에이전트를 가져와서 전투력이 2이고 후퇴시킬 수 "
                "없는 부대로서 교전 칸에 배치할 수 있음. 당신이 소드마스터*를 "
                "보유하고 있다면, 대신 그 에이전트의 전투력이 3이 됨. "
                "(*6인 게임이라면 보너스 토큰)"
            ),
        ),
        "esmar_tuek": LeaderFaceTextKo(
            ability_name="튜엑의 시치",
            # Two side-by-side columns with no punctuation between them on
            # the print; \n marks that column break (leaders_reconcile.md
            # row 6).
            ability_text=(
                "당신*이 튜엑의 시치에 에이전트를 보낼 때마다: {solari:1}\n"
                "다른 플레이어가 튜엑의 시치에 에이전트를 보낼 때마다: {intrigue} "
                "(*6인 게임이라면 팀원도 포함)"
            ),
            signet_name="스파이스 밀수",
            signet_text=(
                "튜엑의 시치에 보너스 스파이스 1을 놓음. —또는— 메이커 게임판 "
                "장소에서 보너스 스파이스 1을 가져감."
            ),
        ),
        "gaius_helen_mohiam": LeaderFaceTextKo(
            ability_name="은밀함",
            # The ability's icon is the eye-shaped Spy Agent icon
            # (agent_icon_spy), distinct from the plain grey-cylinder Spy
            # icon used in the Signet below (leaders_reconcile.md finding
            # "Fields where A and B agreed but the print differs").
            ability_text=(
                "당신이 플레이하는 모든 카드는 {agent_icon_spy} 아이콘 보유. "
                "당신이 정보 수집을 위해 스파이를 소환할 수 있을 때마다, "
                "반드시 그래야만 함."
            ),
            signet_name="듣는 자들",
            # This card prints the separator with short hyphens "-또는-",
            # unlike the long-dash "—또는—" on every other face
            # (leaders_reconcile.md row 8/output conventions).
            signet_text="{agent_icon_landsraad} 에 {spy} -또는- {spice:1} → {spy}",
        ),
        "piter_de_vries": LeaderFaceTextKo(
            ability_name="뒤틀린 재능",
            ability_text=(
                "게임 시작: 뒤틀린 책략 카드를 잘 섞어서 덱을 만든 뒤, 당신의 "
                "근처에 뒷면이 보이도록 놓음. 라운드 시작: 뒤틀린 책략 카드 1장을 "
                "뽑음. (뒤틀린 책략 카드는 책략 카드로 간주되며, 훔쳐질 수 있음.)"
            ),
            signet_name="하코넨의 조언자",
            signet_text="{troop} 이번 차례에는 이 병력을 교전 칸에 배치할 수 없음.",
        ),
        "steersman_y_rkoon": LeaderFaceTextKo(
            # Two printed boxes (red setup "기이한 모습", tan "스파이스를
            # 갈구하다"); mirrors LEADER_FACE_TEXTS["steersman_y_rkoon"]'s
            # English "Strange Form / Hungry for Spice" structure, both
            # names and both box texts kept (leaders_reconcile.md, Structural
            # differences section).
            ability_name="기이한 모습 / 스파이스를 갈구하다",
            ability_text=(
                "기이한 모습: {water}을 보유하지 않은 채로, 그리고 당신의 카드덱에서 "
                "인장 반지를 제외한 채로 게임을 시작합니다.\n"
                "스파이스를 갈구하다: 당신이 한 번의 차례 동안 {spice:3} 이상 얻을 "
                "때마다: {draw}"
            ),
            signet_name="항로 결정",
            signet_text=(
                "게임 시작: 운항 카드를 잘 섞고 5장을 뽑음. 그중 4장을 선택해 이 "
                "지도자 위쪽에 원하는 순서로 뒷면이 보이도록 놓고, 나머지는 게임 "
                "상자에 다시 넣음. 당신이 어떤 팩션에서 영향력 2에 도달할 때마다, "
                "위쪽에서 아직 플레이하지 않은 가장 왼쪽 운항 카드를 플레이함."
            ),
        ),
        "kota_odax_of_ix": LeaderFaceTextKo(
            ability_name="비밀 프로젝트",
            ability_text=(
                "게임 시작: 각각의 기술 타일 더미 맨 아래 타일을 혼자만 확인하고, "
                "그중 1개를 여기에 뒷면으로 놓음. 당신이 기술 타일을 획득할 수 있을 "
                "때마다, 이 기술 타일을 선택해도 됨. 이 기술 타일의 비용은 "
                "{spice:1} 감소."
            ),
            signet_name="역설계",
            signet_text=(
                "{spice:1} —또는— 당신의 기술 타일 1개 폐기 → {intrigue}{draw}"
            ),
        ),
        "liet_kynes": LeaderFaceTextKo(
            ability_name="아라키스 행성학자",
            # The print's own words for summoning a sandworm are "소환"
            # (leaders_reconcile.md, Glossary notes: "The print uses 소환
            # both for recalling a Spy ... and for summoning a sandworm ...
            # The glossary only has the Recall sense") — kept faithful to
            # the print rather than corrected to the glossary's 부르다, per
            # this module's own docstring. The trash icon is bare on the
            # print (no "해도 됨"); the engine reads it as optional
            # (OQ-037).
            ability_text=(
                "시치 타브르의 영향력 조건을 무시. 당신은 모래벌레를 소환하지 "
                "않음. 모래벌레를 소환하려 할 때마다, 대신: {trash} {spice:1} "
                "{intrigue} (교전이 방어벽으로 보호받고 있을 때도 포함.)"
            ),
            signet_name="변화의 판관",
            signet_text=(
                "이번 차례에 에이전트를 보낸 장소에 따라 아래를 적용.\n"
                "{agent_icon_landsraad}: {agent_icon_emperor} 영향력 2: {water}\n"
                "{agent_icon_city}: {solari:1}\n"
                "{agent_icon_spice_trade}: {spice:1}"
            ),
        ),
    }
)
