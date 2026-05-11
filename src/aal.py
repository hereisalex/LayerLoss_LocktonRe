"""Annual Aggregate Limit (AAL) bookkeeping.

After per-claim cessions are computed, this module applies the annual
aggregate cap for each (year, layer) group, processing claims in
chronological order.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["apply_aal"]


def apply_aal(pre_aal_df: pd.DataFrame) -> pd.DataFrame:
    """Apply Annual Aggregate Limits to pre-AAL cession amounts.

    Claims are processed in chronological order within each ``(year,
    layer_name)`` group.  Ties on ``date`` are broken by ``claim_id``
    ascending.  Once the cumulative ceded amount reaches the layer's
    ``aal``, subsequent claims in that year cede zero.

    Parameters
    ----------
    pre_aal_df : pd.DataFrame
        Must contain columns:
        ``year``, ``layer_name``, ``date``, ``claim_id``,
        ``ceded_pre_aal``, ``aal``.

    Returns
    -------
    pd.DataFrame
        A copy of the input with an added ``ceded`` column containing the
        post-AAL ceded amount for each claim-layer pair.
    """
    df = pre_aal_df.copy()
    df = df.sort_values(["year", "layer_name", "date", "claim_id"])

    ceded_values: list[float] = []

    for (_year, _layer), group in df.groupby(
        ["year", "layer_name"], sort=False
    ):
        aal = group["aal"].iloc[0]
        paid_so_far = 0.0

        for ceded_pre_aal in group["ceded_pre_aal"]:
            remaining_aal = aal - paid_so_far
            ceded = min(ceded_pre_aal, max(remaining_aal, 0.0))
            paid_so_far += ceded
            ceded_values.append(ceded)

    df["ceded"] = ceded_values
    return df
