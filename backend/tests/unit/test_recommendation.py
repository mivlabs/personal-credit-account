from app.domain.enums import PurposeCategory
from app.domain.recommendation import load_recommendation_config


def test_rules_cover_every_category():
    assert set(load_recommendation_config().purposes) == set(PurposeCategory)
