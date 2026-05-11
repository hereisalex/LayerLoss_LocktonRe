"""Integration tests for src.allocator — end-to-end allocation."""

import pandas as pd
import pytest

from src.allocator import allocate_claims

# ── Expected output columns and dtypes ──────────────────────────────────
_EXPECTED_COLUMNS = ["year", "layer_name", "ceded_amount"]


class TestSanityCheck1:
    """Sanity check #1 from the assignment: per-claim layer math, no AAL binding."""

    def setup_method(self):
        self.claims = pd.DataFrame({
            "claim_id": ["C1"],
            "date": ["2023-01-15"],
            "loss": [4_000_000.0],
            "alae": [500_000.0],
        })
        self.layers = pd.DataFrame({
            "layer_name": ["L1", "L2", "L3"],
            "attachment": [1_000_000.0, 2_000_000.0, 5_000_000.0],
            "limit": [1_000_000.0, 3_000_000.0, 5_000_000.0],
            "aal": [2_000_000.0, 5_000_000.0, 5_000_000.0],
            "alae_treatment": ["pro_rata", "part_of", "excluded"],
        })

    def test_expected_cessions(self):
        result = allocate_claims(self.claims, self.layers)
        expected = {
            ("L1",): 1_125_000.0,
            ("L2",): 2_500_000.0,
            ("L3",): 0.0,
        }
        for row in result.itertuples():
            key = (row.layer_name,)
            assert row.ceded_amount == pytest.approx(expected[key]), (
                f"Mismatch for {key}: got {row.ceded_amount}, "
                f"expected {expected[key]}"
            )

    def test_all_rows_year_2023(self):
        result = allocate_claims(self.claims, self.layers)
        assert (result["year"] == 2023).all()

    def test_row_count(self):
        result = allocate_claims(self.claims, self.layers)
        assert len(result) == 3  # 1 year × 3 layers


class TestSanityCheck2:
    """Sanity check #2: AAL exhaustion and annual reset."""

    def setup_method(self):
        self.claims = pd.DataFrame({
            "claim_id": ["C1", "C2", "C3"],
            "date": ["2023-01-01", "2023-02-01", "2024-01-01"],
            "loss": [2_000_000.0, 2_000_000.0, 2_000_000.0],
            "alae": [0.0, 0.0, 0.0],
        })
        self.layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [0.0],
            "limit": [1_000_000.0],
            "aal": [1_500_000.0],
            "alae_treatment": ["excluded"],
        })

    def test_expected_cessions(self):
        result = allocate_claims(self.claims, self.layers)
        result = result.sort_values("year").reset_index(drop=True)
        assert result.loc[0, "ceded_amount"] == pytest.approx(1_500_000.0)
        assert result.loc[1, "ceded_amount"] == pytest.approx(1_000_000.0)

    def test_row_count(self):
        result = allocate_claims(self.claims, self.layers)
        assert len(result) == 2  # 2 years × 1 layer


class TestOutputSchema:
    """Verify the output DataFrame has exactly the specified columns."""

    def test_output_columns(self):
        claims = pd.DataFrame({
            "claim_id": ["C1"],
            "date": ["2023-01-01"],
            "loss": [1_000_000.0],
            "alae": [0.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [0.0],
            "limit": [1_000_000.0],
            "aal": [5_000_000.0],
            "alae_treatment": ["excluded"],
        })
        result = allocate_claims(claims, layers)
        assert list(result.columns) == _EXPECTED_COLUMNS

    def test_year_column_is_int(self):
        claims = pd.DataFrame({
            "claim_id": ["C1"],
            "date": ["2023-06-15"],
            "loss": [500_000.0],
            "alae": [0.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [0.0],
            "limit": [1_000_000.0],
            "aal": [5_000_000.0],
            "alae_treatment": ["excluded"],
        })
        result = allocate_claims(claims, layers)
        assert result["year"].dtype in ("int64", "int32")

    def test_ceded_amount_is_float(self):
        claims = pd.DataFrame({
            "claim_id": ["C1"],
            "date": ["2023-06-15"],
            "loss": [500_000.0],
            "alae": [0.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [0.0],
            "limit": [1_000_000.0],
            "aal": [5_000_000.0],
            "alae_treatment": ["excluded"],
        })
        result = allocate_claims(claims, layers)
        assert result["ceded_amount"].dtype == "float64"


class TestEdgeCases:
    """Edge cases not covered by the sanity checks."""

    def test_zero_loss_zero_alae(self):
        claims = pd.DataFrame({
            "claim_id": ["C1"],
            "date": ["2023-01-01"],
            "loss": [0.0],
            "alae": [0.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [0.0],
            "limit": [1_000_000.0],
            "aal": [1_000_000.0],
            "alae_treatment": ["excluded"],
        })
        result = allocate_claims(claims, layers)
        assert result["ceded_amount"].iloc[0] == 0.0

    def test_zero_loss_nonzero_alae_pro_rata(self):
        """Pro-rata with zero loss: no division by zero, cession = 0."""
        claims = pd.DataFrame({
            "claim_id": ["C1"],
            "date": ["2023-01-01"],
            "loss": [0.0],
            "alae": [500_000.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [0.0],
            "limit": [1_000_000.0],
            "aal": [1_000_000.0],
            "alae_treatment": ["pro_rata"],
        })
        result = allocate_claims(claims, layers)
        assert result["ceded_amount"].iloc[0] == 0.0

    def test_zero_loss_nonzero_alae_part_of(self):
        """Part-of with zero loss: ALAE alone can hit the layer."""
        claims = pd.DataFrame({
            "claim_id": ["C1"],
            "date": ["2023-01-01"],
            "loss": [0.0],
            "alae": [2_000_000.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [1_000_000.0],
            "limit": [3_000_000.0],
            "aal": [5_000_000.0],
            "alae_treatment": ["part_of"],
        })
        result = allocate_claims(claims, layers)
        assert result["ceded_amount"].iloc[0] == pytest.approx(1_000_000.0)

    def test_multiple_layers_multiple_years(self):
        """Ensure all (year, layer) combos appear, even with zero cessions."""
        claims = pd.DataFrame({
            "claim_id": ["C1", "C2"],
            "date": ["2023-01-01", "2024-01-01"],
            "loss": [100.0, 100.0],
            "alae": [0.0, 0.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1", "L2"],
            "attachment": [0.0, 1_000_000.0],
            "limit": [1_000_000.0, 1_000_000.0],
            "aal": [5_000_000.0, 5_000_000.0],
            "alae_treatment": ["excluded", "excluded"],
        })
        result = allocate_claims(claims, layers)
        # 2 years × 2 layers = 4 rows
        assert len(result) == 4

    def test_multi_layer_aal_binding_interaction(self):
        """One layer's AAL binds while another does not — layers are independent."""
        claims = pd.DataFrame({
            "claim_id": ["C1", "C2"],
            "date": ["2023-01-01", "2023-06-01"],
            "loss": [3_000_000.0, 3_000_000.0],
            "alae": [0.0, 0.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1", "L2"],
            "attachment": [0.0, 0.0],
            "limit": [2_000_000.0, 2_000_000.0],
            "aal": [3_000_000.0, 10_000_000.0],
            "alae_treatment": ["excluded", "excluded"],
        })
        result = allocate_claims(claims, layers)
        result = result.set_index("layer_name")
        # L1 AAL=3M: C1 cedes 2M, C2 cedes min(2M, 1M remaining) = 1M → 3M total
        assert result.loc["L1", "ceded_amount"] == pytest.approx(3_000_000.0)
        # L2 AAL=10M: C1 cedes 2M, C2 cedes 2M → 4M total, well under AAL
        assert result.loc["L2", "ceded_amount"] == pytest.approx(4_000_000.0)

    def test_empty_claims(self):
        """Empty claims DataFrame produces an empty result (no crash)."""
        claims = pd.DataFrame({
            "claim_id": pd.Series([], dtype="str"),
            "date": pd.Series([], dtype="str"),
            "loss": pd.Series([], dtype="float64"),
            "alae": pd.Series([], dtype="float64"),
        })
        layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [0.0],
            "limit": [1_000_000.0],
            "aal": [1_000_000.0],
            "alae_treatment": ["excluded"],
        })
        result = allocate_claims(claims, layers)
        assert len(result) == 0
        assert list(result.columns) == _EXPECTED_COLUMNS

    def test_invalid_claims_raises(self):
        claims = pd.DataFrame({
            "claim_id": ["C1"],
            "date": ["2023-01-01"],
            "loss": [-100.0],
            "alae": [0.0],
        })
        layers = pd.DataFrame({
            "layer_name": ["L1"],
            "attachment": [0.0],
            "limit": [1_000_000.0],
            "aal": [1_000_000.0],
            "alae_treatment": ["excluded"],
        })
        with pytest.raises(ValueError):
            allocate_claims(claims, layers)
