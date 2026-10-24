import pytest

from app.domain.inn import SEED_INNS, InnProblem, validate_inn, with_checksum

LEGAL_ENTITY_INNS = {
    0: "7702000004",
    1: "7702000011",
    2: "7702000029",
    3: "7702000036",
    4: "7702000043",
    5: "7702000050",
    6: "7702000068",
    7: "7702000075",
    8: "7702000082",
    9: "7702000090",
}


@pytest.mark.parametrize("inn", LEGAL_ENTITY_INNS.values())
def test_valid_ten_digit_inn(inn):
    assert validate_inn(inn).valid


@pytest.mark.parametrize("digit", range(10))
def test_valid_twelve_digit_inn_has_scenario_digit_before_checksum(digit):
    inn = with_checksum(f"770200000{digit}")
    assert len(inn) == 12
    assert inn[9] == str(digit)
    assert validate_inn(inn).valid


def test_known_twelve_digit_example():
    assert with_checksum("7702000005") == "770200000523"
    assert validate_inn("770200000523").valid
    assert not validate_inn("770200000550").valid


def test_ten_digit_checksum_matches_scenario_table():
    assert {d: with_checksum(f"77020000{d}") for d in range(10)} == LEGAL_ENTITY_INNS


@pytest.mark.parametrize("inn", ["7702000051", "7702000000", "770200000551", "770200000540"])
def test_wrong_checksum(inn):
    check = validate_inn(inn)
    assert not check.valid
    assert check.problem == InnProblem.BAD_CHECKSUM
    assert check.message == "Неверная контрольная сумма ИНН"


@pytest.mark.parametrize("inn", ["77020000a4", "", "7702 00004", "٧٧٠٢٠٠٠٠٠٤", "-770200004"])
def test_not_digits(inn):
    assert validate_inn(inn).problem == InnProblem.NOT_DIGITS


@pytest.mark.parametrize("inn", ["770200000", "77020000041", "77020000050123"])
def test_wrong_length(inn):
    assert validate_inn(inn).problem == InnProblem.BAD_LENGTH


@pytest.mark.parametrize("inn", sorted(SEED_INNS))
def test_seed_inns_are_allowed_explicitly(inn):
    check = validate_inn(inn)
    assert check.valid
    assert check.seed


def test_seed_exception_covers_all_demo_clients():
    from app.seed.data import DEMO_CLIENTS

    assert {c.inn for c in DEMO_CLIENTS} <= SEED_INNS
