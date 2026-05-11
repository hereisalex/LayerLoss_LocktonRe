"""Unit tests for src.aal — Annual Aggregate Limit bookkeeping."""

import pandas as pd
# pyrefly: ignore [missing-import]
import pytest


from src.aal import apply_aal


def _make_pre_aal_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to build a pre-AAL DataFrame from a list of dicts."""
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


class TestApplyAAL:
    def test_single_claim_under_aal(self):
        """Single claim well under AAL — ceded = ceded_pre_aal."""
        df = _make_pre_aal_df([
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "C1", "ceded_pre_aal": 500_000, "aal": 1_000_000},
        ])
        result = apply_aal(df)
        assert result["ceded"].iloc[0] == pytest.approx(500_000)

    def test_aal_exactly_exhausted(self):
        """Two claims that exactly exhaust the AAL."""
        df = _make_pre_aal_df([
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "C1", "ceded_pre_aal": 750_000, "aal": 1_500_000},
            {"year": 2023, "layer_name": "L1", "date": "2023-02-01",
             "claim_id": "C2", "ceded_pre_aal": 750_000, "aal": 1_500_000},
        ])
        result = apply_aal(df)
        ceded = result.sort_values(["date", "claim_id"])["ceded"].tolist()
        assert ceded == pytest.approx([750_000, 750_000])

    def test_aal_partial_exhaustion(self):
        """Second claim is partially capped by AAL."""
        df = _make_pre_aal_df([
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "C1", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
            {"year": 2023, "layer_name": "L1", "date": "2023-02-01",
             "claim_id": "C2", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
        ])
        result = apply_aal(df)
        ceded = result.sort_values(["date", "claim_id"])["ceded"].tolist()
        assert ceded == pytest.approx([1_000_000, 500_000])

    def test_aal_fully_exhausted_third_claim_zero(self):
        """Third claim after AAL is exhausted → ceded = 0."""
        df = _make_pre_aal_df([
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "C1", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
            {"year": 2023, "layer_name": "L1", "date": "2023-02-01",
             "claim_id": "C2", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
            {"year": 2023, "layer_name": "L1", "date": "2023-03-01",
             "claim_id": "C3", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
        ])
        result = apply_aal(df)
        ceded = result.sort_values(["date", "claim_id"])["ceded"].tolist()
        assert ceded == pytest.approx([1_000_000, 500_000, 0])

    def test_aal_resets_across_years(self):
        """AAL resets at the start of each new accident year."""
        df = _make_pre_aal_df([
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "C1", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
            {"year": 2023, "layer_name": "L1", "date": "2023-02-01",
             "claim_id": "C2", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
            {"year": 2024, "layer_name": "L1", "date": "2024-01-01",
             "claim_id": "C3", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
        ])
        result = apply_aal(df)
        ceded = result.sort_values(["year", "date", "claim_id"])["ceded"].tolist()
        # 2023: 1M + 500K = 1.5M (exhausted), 2024: 1M (reset)
        assert ceded == pytest.approx([1_000_000, 500_000, 1_000_000])

    def test_same_date_tiebreak_by_claim_id(self):
        """Claims on the same date are processed in claim_id order."""
        df = _make_pre_aal_df([
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "B_claim", "ceded_pre_aal": 800_000, "aal": 1_000_000},
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "A_claim", "ceded_pre_aal": 800_000, "aal": 1_000_000},
        ])
        result = apply_aal(df)
        result = result.sort_values(["date", "claim_id"])
        ceded = result["ceded"].tolist()
        # A_claim processed first: 800K, B_claim: min(800K, 200K) = 200K
        assert ceded == pytest.approx([800_000, 200_000])

    def test_layers_independent(self):
        """AAL for one layer does not affect another."""
        df = _make_pre_aal_df([
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "C1", "ceded_pre_aal": 1_000_000, "aal": 500_000},
            {"year": 2023, "layer_name": "L2", "date": "2023-01-01",
             "claim_id": "C1", "ceded_pre_aal": 1_000_000, "aal": 2_000_000},
        ])
        result = apply_aal(df)
        result = result.sort_values("layer_name")
        ceded = result["ceded"].tolist()
        # L1 capped at 500K, L2 fully within AAL at 1M
        assert ceded == pytest.approx([500_000, 1_000_000])

    def test_sanity_check_2(self):
        """Assignment sanity check #2: AAL exhaustion and annual reset."""
        df = _make_pre_aal_df([
            {"year": 2023, "layer_name": "L1", "date": "2023-01-01",
             "claim_id": "C1", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
            {"year": 2023, "layer_name": "L1", "date": "2023-02-01",
             "claim_id": "C2", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
            {"year": 2024, "layer_name": "L1", "date": "2024-01-01",
             "claim_id": "C3", "ceded_pre_aal": 1_000_000, "aal": 1_500_000},
        ])
        result = apply_aal(df)
        year_totals = result.groupby("year")["ceded"].sum().to_dict()
        assert year_totals[2023] == pytest.approx(1_500_000)
        assert year_totals[2024] == pytest.approx(1_000_000)
