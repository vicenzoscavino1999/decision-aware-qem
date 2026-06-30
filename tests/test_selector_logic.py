import pytest

from daqem.selectors import da_selector, mse_selector


def test_mse_selector_argmin_and_lex_tiebreak():
    assert mse_selector({"ZNE": 0.2, "Raw": 0.3}) == "ZNE"
    assert mse_selector({"ZNE": 0.2, "Raw": 0.2}) == "Raw"


def test_da_selector_uses_gri_when_valid():
    assert da_selector({"Raw": 0.3, "DA-ZNE": 0.2}, gri_valid=True) == "DA-ZNE"


def test_da_selector_fallback_uses_empirical_when_gri_invalid():
    assert (
        da_selector(
            {"Raw": 0.1, "DA-ZNE": 0.2},
            empirical_by_method={"Raw": 0.4, "DA-ZNE": 0.3},
            gri_valid=False,
        )
        == "DA-ZNE"
    )


def test_da_selector_requires_empirical_for_invalid_gri():
    with pytest.raises(ValueError):
        da_selector({"Raw": 0.1}, gri_valid=False)
