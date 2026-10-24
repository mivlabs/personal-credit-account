from app.domain.enums import FINAL_STATUSES, ApplicationStatus
from app.domain.state_machine import (
    TRANSITIONS,
    find_transition,
    render_state_machine_md,
    targets_from,
)
from app.scripts.export_state_machine import DEFAULT_OUTPUT

S = ApplicationStatus
ALL = list(ApplicationStatus)


def test_final_statuses_have_no_outgoing_transitions():
    for status in FINAL_STATUSES:
        assert targets_from(status) == []


def test_every_status_is_reachable_from_draft():
    reached, queue = {S.DRAFT}, [S.DRAFT]
    while queue:
        for nxt in targets_from(queue.pop()):
            if nxt not in reached:
                reached.add(nxt)
                queue.append(nxt)
    assert reached == set(ALL)


def test_transition_table_has_no_duplicates():
    pairs = [(t.source, t.target) for t in TRANSITIONS]
    assert len(pairs) == len(set(pairs))
    assert find_transition(S.DRAFT, S.ISSUED) is None


def test_state_machine_doc_matches_code():
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_state_machine_md(), (
        "docs/state-machine.md разошёлся с кодом: uv run python -m app.scripts.export_state_machine"
    )


def test_external_check_always_goes_through_scoring():
    assert targets_from(S.EXTERNAL_CHECK) == [S.SCORING]
    assert find_transition(S.EXTERNAL_CHECK, S.MANUAL_REVIEW) is None
