"""Unit tests for src.validation — input validation."""

import pandas as pd
import pytest

from src.validation import validate_claims, validate_layers


class TestValidateClaims:
    def _valid(self) -> pd.DataFrame:
        return pd.DataFrame({
            "claim_id": ["C1", "C2"],
            "date": ["2023-01-01", "2023-06-15"],
            "loss": [1_000_000.0, 500_000.0],
            "alae": [100_000.0, 50_000.0],
        })

    def test_valid_no_error(self):
        validate_claims(self._valid())

    def test_missing_column(self):
        with pytest.raises(ValueError, match="missing required columns"):
            validate_claims(self._valid().drop(columns=["loss"]))

    def test_null_values(self):
        df = self._valid()
        df.loc[0, "loss"] = None
        with pytest.raises(ValueError, match="null values"):
            validate_claims(df)

    def test_duplicate_claim_id(self):
        df = self._valid()
        df.loc[1, "claim_id"] = "C1"
        with pytest.raises(ValueError, match="duplicate claim_id"):
            validate_claims(df)

    def test_negative_loss(self):
        df = self._valid()
        df.loc[0, "loss"] = -100
        with pytest.raises(ValueError, match="negative"):
            validate_claims(df)

    def test_negative_alae(self):
        df = self._valid()
        df.loc[0, "alae"] = -50
        with pytest.raises(ValueError, match="negative"):
            validate_claims(df)

    def test_unparseable_date(self):
        df = self._valid()
        df.loc[0, "date"] = "not-a-date"
        with pytest.raises(ValueError, match="unparseable"):
            validate_claims(df)


class TestValidateLayers:
    def _valid(self) -> pd.DataFrame:
        return pd.DataFrame({
            "layer_name": ["L1", "L2"],
            "attachment": [1_000_000.0, 2_000_000.0],
            "limit": [1_000_000.0, 3_000_000.0],
            "aal": [2_000_000.0, 5_000_000.0],
            "alae_treatment": ["pro_rata", "part_of"],
        })

    def test_valid_no_error(self):
        validate_layers(self._valid())

    def test_missing_column(self):
        with pytest.raises(ValueError, match="missing required columns"):
            validate_layers(self._valid().drop(columns=["aal"]))

    def test_negative_attachment(self):
        df = self._valid()
        df.loc[0, "attachment"] = -100
        with pytest.raises(ValueError, match="negative"):
            validate_layers(df)

    def test_zero_limit(self):
        df = self._valid()
        df.loc[0, "limit"] = 0
        with pytest.raises(ValueError, match="must be > 0"):
            validate_layers(df)

    def test_zero_aal(self):
        df = self._valid()
        df.loc[0, "aal"] = 0
        with pytest.raises(ValueError, match="must be > 0"):
            validate_layers(df)

    def test_invalid_alae_treatment(self):
        df = self._valid()
        df.loc[0, "alae_treatment"] = "included"
        with pytest.raises(ValueError, match="invalid values"):
            validate_layers(df)

    def test_null_layer_name(self):
        df = self._valid()
        df.loc[0, "layer_name"] = None
        with pytest.raises(ValueError, match="null values"):
            validate_layers(df)
