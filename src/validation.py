"""Input validation for claims and layers DataFrames.

All validation functions raise ``ValueError`` with descriptive messages
when the input is malformed.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["validate_claims", "validate_layers"]

# ── Required schemas ────────────────────────────────────────────────────
_CLAIMS_REQUIRED_COLUMNS = {"claim_id", "date", "loss", "alae"}
_LAYERS_REQUIRED_COLUMNS = {
    "layer_name",
    "attachment",
    "limit",
    "aal",
    "alae_treatment",
}
_VALID_ALAE_TREATMENTS = {"excluded", "pro_rata", "part_of"}


def validate_claims(claims_df: pd.DataFrame) -> None:
    """Validate the claims DataFrame, raising ``ValueError`` on problems.

    Checks performed
    ----------------
    * All required columns are present.
    * No null values in required columns.
    * ``claim_id`` values are unique.
    * ``date`` is parseable as a date.
    * ``loss`` and ``alae`` are numeric and ≥ 0.
    """
    _check_required_columns(claims_df, _CLAIMS_REQUIRED_COLUMNS, "claims_df")

    # Nulls
    nulls = claims_df[list(_CLAIMS_REQUIRED_COLUMNS)].isnull().sum()
    cols_with_nulls = nulls[nulls > 0]
    if not cols_with_nulls.empty:
        raise ValueError(
            f"claims_df has null values in columns: "
            f"{dict(cols_with_nulls)}"
        )

    # Unique claim_id
    if claims_df["claim_id"].duplicated().any():
        dupes = claims_df.loc[
            claims_df["claim_id"].duplicated(keep=False), "claim_id"
        ].unique()
        raise ValueError(
            f"claims_df contains duplicate claim_id values: "
            f"{list(dupes)}"
        )

    # Date parsing
    try:
        pd.to_datetime(claims_df["date"], format='ISO8601')
    except Exception as exc:
        raise ValueError(
            f"claims_df 'date' column contains unparseable values: {exc}"
        ) from exc

    # Numeric constraints
    _check_numeric_non_negative(claims_df, "loss", "claims_df")
    _check_numeric_non_negative(claims_df, "alae", "claims_df")


def validate_layers(layers_df: pd.DataFrame) -> None:
    """Validate the layers DataFrame, raising ``ValueError`` on problems.

    Checks performed
    ----------------
    * All required columns are present.
    * No null values in required columns.
    * ``layer_name`` values are unique.
    * ``attachment`` ≥ 0.
    * ``limit`` > 0 and ``aal`` > 0.
    * ``alae_treatment`` is one of the three recognised values.
    """
    _check_required_columns(layers_df, _LAYERS_REQUIRED_COLUMNS, "layers_df")

    # Nulls
    nulls = layers_df[list(_LAYERS_REQUIRED_COLUMNS)].isnull().sum()
    cols_with_nulls = nulls[nulls > 0]
    if not cols_with_nulls.empty:
        raise ValueError(
            f"layers_df has null values in columns: "
            f"{dict(cols_with_nulls)}"
        )

    # Unique layer_name
    if layers_df["layer_name"].duplicated().any():
        dupes = layers_df.loc[
            layers_df["layer_name"].duplicated(keep=False), "layer_name"
        ].unique()
        raise ValueError(
            f"layers_df contains duplicate layer_name values: "
            f"{list(dupes)}"
        )

    # Numeric constraints
    _check_numeric_non_negative(layers_df, "attachment", "layers_df")
    _check_numeric_positive(layers_df, "limit", "layers_df")
    _check_numeric_positive(layers_df, "aal", "layers_df")

    # ALAE treatment enum
    invalid = set(layers_df["alae_treatment"].unique()) - _VALID_ALAE_TREATMENTS
    if invalid:
        raise ValueError(
            f"layers_df 'alae_treatment' contains invalid values: {invalid}. "
            f"Must be one of: {_VALID_ALAE_TREATMENTS}"
        )


# ── Helpers ─────────────────────────────────────────────────────────────

def _check_required_columns(
    df: pd.DataFrame, required: set[str], df_name: str
) -> None:
    """Raise ValueError if *df* is missing any *required* columns."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{df_name} is missing required columns: {missing}"
        )


def _check_numeric_non_negative(
    df: pd.DataFrame, column: str, df_name: str
) -> None:
    """Raise ValueError if *column* contains non-numeric or negative values."""
    try:
        values = pd.to_numeric(df[column])
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{df_name} '{column}' contains non-numeric values: {exc}"
        ) from exc
    if (values < 0).any():
        raise ValueError(
            f"{df_name} '{column}' contains negative values."
        )


def _check_numeric_positive(
    df: pd.DataFrame, column: str, df_name: str
) -> None:
    """Raise ValueError if *column* contains non-numeric or non-positive values."""
    try:
        values = pd.to_numeric(df[column])
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{df_name} '{column}' contains non-numeric values: {exc}"
        ) from exc
    if (values <= 0).any():
        raise ValueError(
            f"{df_name} '{column}' must be > 0 for all rows."
        )
