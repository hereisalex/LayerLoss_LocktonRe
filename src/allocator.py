"""Orchestrator — wires validation, layer math, AAL, and aggregation.

This module exposes the main ``allocate_claims`` function required by the
assignment specification.
"""

from __future__ import annotations

import pandas as pd

from src.aal import apply_aal
from src.layer_math import compute_cession_pre_aal
from src.validation import validate_claims, validate_layers


def allocate_claims(
    claims_df: pd.DataFrame,
    layers_df: pd.DataFrame,
) -> pd.DataFrame:
    """Produce a year-by-layer cession report from a portfolio of claims.

    Parameters
    ----------
    claims_df : pd.DataFrame
        One row per claim with columns:
        ``claim_id`` (str), ``date`` (date-like), ``loss`` (float ≥ 0),
        ``alae`` (float ≥ 0).
    layers_df : pd.DataFrame
        One row per layer with columns:
        ``layer_name`` (str), ``attachment`` (float ≥ 0),
        ``limit`` (float > 0), ``aal`` (float > 0),
        ``alae_treatment`` (str ∈ {excluded, pro_rata, part_of}).

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with columns ``year`` (int),
        ``layer_name`` (str), ``ceded_amount`` (float).
        One row per ``(year, layer_name)`` combination, including
        zero-cession rows where no claims hit a layer in a given year.

    Raises
    ------
    ValueError
        If either input DataFrame is malformed.
    """
    # ── 1. Validate ─────────────────────────────────────────────────────
    validate_claims(claims_df)
    validate_layers(layers_df)

    # ── 2. Normalise types ──────────────────────────────────────────────
    claims = claims_df.copy()
    claims["date"] = pd.to_datetime(claims["date"])
    claims["year"] = claims["date"].dt.year
    claims["loss"] = claims["loss"].astype(float)
    claims["alae"] = claims["alae"].astype(float)

    layers = layers_df.copy()
    layers["attachment"] = layers["attachment"].astype(float)
    layers["limit"] = layers["limit"].astype(float)
    layers["aal"] = layers["aal"].astype(float)

    # ── 3. Cross-join claims × layers ───────────────────────────────────
    cross = claims.merge(layers, how="cross")

    # ── 4. Compute per-claim, per-layer cession (pre-AAL) ──────────────
    cross["ceded_pre_aal"] = cross.apply(
        lambda r: compute_cession_pre_aal(
            loss=r["loss"],
            alae=r["alae"],
            attachment=r["attachment"],
            limit=r["limit"],
            alae_treatment=r["alae_treatment"],
        ),
        axis=1,
    )

    # ── 5. Apply AAL per (year, layer) ──────────────────────────────────
    post_aal = apply_aal(
        cross[["year", "layer_name", "date", "claim_id", "ceded_pre_aal", "aal"]]
    )

    # ── 6. Aggregate ceded amounts by (year, layer_name) ────────────────
    aggregated = (
        post_aal.groupby(["year", "layer_name"], as_index=False)["ceded"]
        .sum()
        .rename(columns={"ceded": "ceded_amount"})
    )

    # ── 7. Ensure all (year, layer) combos exist (include zero rows) ───
    all_years = sorted(claims["year"].unique())
    all_layers = layers["layer_name"].tolist()

    full_index = pd.DataFrame(
        [(y, l) for y in all_years for l in all_layers],
        columns=["year", "layer_name"],
    )

    result = full_index.merge(aggregated, on=["year", "layer_name"], how="left")
    result["ceded_amount"] = result["ceded_amount"].fillna(0.0)

    # Sort for deterministic output
    result = result.sort_values(["year", "layer_name"]).reset_index(drop=True)

    return result
