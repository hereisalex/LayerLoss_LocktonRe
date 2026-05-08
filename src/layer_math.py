"""Per-claim layer cession calculations.

Implements the three ALAE (Allocated Loss Adjustment Expense) treatments
used in reinsurance contracts to determine how much of each claim is
ceded to a given layer, before the Annual Aggregate Limit is applied.
"""


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp *x* between *lo* and *hi* inclusive.

    Equivalent to ``max(lo, min(x, hi))``.

    Parameters
    ----------
    x : float
        The value to clamp.
    lo : float
        The lower bound.
    hi : float
        The upper bound.

    Returns
    -------
    float
    """
    return max(lo, min(x, hi))


def _ceded_excluded(loss: float, attachment: float, limit: float) -> float:
    """ALAE excluded: layer attaches to loss alone; ALAE is not covered."""
    return clamp(loss - attachment, 0.0, limit)


def _ceded_pro_rata(
    loss: float, alae: float, attachment: float, limit: float
) -> float:
    """ALAE pro-rata: layer attaches to loss, ALAE follows proportionally."""
    loss_in_layer = clamp(loss - attachment, 0.0, limit)
    if loss > 0.0:
        alae_in_layer = alae * (loss_in_layer / loss)
    else:
        alae_in_layer = 0.0
    return loss_in_layer + alae_in_layer


def _ceded_part_of(
    loss: float, alae: float, attachment: float, limit: float
) -> float:
    """ALAE part-of: ALAE is rolled into the ground-up amount."""
    ground_up = loss + alae
    return clamp(ground_up - attachment, 0.0, limit)


# ---------------------------------------------------------------------------
# Dispatch table — maps treatment name → calculation function
# ---------------------------------------------------------------------------
_TREATMENT_DISPATCH: dict[str, callable] = {
    "excluded": lambda loss, alae, att, lim: _ceded_excluded(loss, att, lim),
    "pro_rata": _ceded_pro_rata,
    "part_of": _ceded_part_of,
}


def compute_cession_pre_aal(
    loss: float,
    alae: float,
    attachment: float,
    limit: float,
    alae_treatment: str,
) -> float:
    """Compute a single claim's cession to a layer **before** AAL is applied.

    Parameters
    ----------
    loss : float
        Ground-up loss amount (≥ 0).
    alae : float
        Allocated Loss Adjustment Expense (≥ 0).
    attachment : float
        Layer attachment point (≥ 0).
    limit : float
        Per-occurrence limit for the layer (> 0).
    alae_treatment : str
        One of ``"excluded"``, ``"pro_rata"``, or ``"part_of"``.

    Returns
    -------
    float
        The ceded amount before the Annual Aggregate Limit is considered.

    Raises
    ------
    ValueError
        If *alae_treatment* is not one of the three recognised values.
    """
    handler = _TREATMENT_DISPATCH.get(alae_treatment)
    if handler is None:
        raise ValueError(
            f"Unknown alae_treatment '{alae_treatment}'. "
            f"Must be one of: {sorted(_TREATMENT_DISPATCH)}"
        )
    return handler(loss, alae, attachment, limit)
