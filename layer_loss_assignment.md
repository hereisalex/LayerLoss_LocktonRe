# Assignment: Layered Loss Allocation

## Context

Reinsurance programs cede portions of a primary insurer's losses to one or more **layers**, each defined by an **attachment point**, a **per-occurrence limit**, and an **annual aggregate limit (AAL)**.

Each individual claim has a **loss** amount and an associated **ALAE** (Allocated Loss Adjustment Expense) — the legal, investigation, and defense costs tied to that specific claim. How ALAE flows into the layers depends on the contract, and you'll implement the three common treatments.

You'll produce a year-by-layer cession report from a portfolio of claims.

**AI tools:** Use any AI coding assistant you'd like. Explain in the README how you used it.

---

## Setup

- Python 3.11+
- `pandas` is expected; otherwise use whatever you'd like

---

## Part 1 — The Function

Implement:

```python
def allocate_claims(claims_df: pd.DataFrame, layers_df: pd.DataFrame) -> pd.DataFrame:
    ...
```

### Inputs

**`claims_df`** — one row per claim:

| column | type | notes |
|---|---|---|
| `claim_id` | str | unique |
| `date` | date | used to derive accident year (`date.year`) and chronological order within a year |
| `loss` | float | ≥ 0 |
| `alae` | float | ≥ 0 |

**`layers_df`** — one row per layer:

| column | type | notes |
|---|---|---|
| `layer_name` | str | e.g. `L1`, `L2`, `L3` |
| `attachment` | float | ≥ 0 |
| `limit` | float | per-occurrence limit, > 0 |
| `aal` | float | annual aggregate limit, > 0; the layer pays no more than this in any single year |
| `alae_treatment` | str | one of `part_of`, `pro_rata`, `excluded` |

Raise `ValueError` on invalid input.

### Output

A long-format DataFrame:

| column | type |
|---|---|
| `year` | int |
| `layer_name` | str |
| `ceded_amount` | float |

One row per `(year, layer_name)` combination, including zero rows where no claims hit a layer in that year.

---

## Part 2 — Per-Claim Layer Math
> `clamp(x, lo, hi)` means `max(lo, min(x, hi))`.

Each layer applies independently to each claim. Layers do not interact with each other. Exhaustion of one layer's AAL does not affect any other layer. Each layer's per-claim recovery is calculated independently using ground-up loss and ALAE.

For a single claim with `loss` and `alae` against a layer with `attachment` and per-occurrence `limit`:

### `excluded`
ALAE is not covered. The layer attaches to loss alone.

```
ceded_pre_aal = clamp(loss - attachment, 0, limit)
```

### `pro_rata`
The layer attaches to loss alone, and ALAE is recovered in the same ratio as loss recovery.

```
loss_in_layer = clamp(loss - attachment, 0, limit)
alae_in_layer = alae * (loss_in_layer / loss)   if loss > 0 else 0
ceded_pre_aal         = loss_in_layer + alae_in_layer
```

### `part_of`
ALAE is rolled into the ground-up amount the layer attaches to.

```
ground_up = loss + alae
ceded_pre_aal = clamp(ground_up - attachment, 0, limit)
```


`ceded_pre_aal` is the layer's per-claim payout *before* the AAL is applied — see Part 3.

---

## Part 3 — Annual Aggregate Limit

The AAL caps how much a layer pays in total in a single accident year. AAL applies separately by `(year, layer_name)` and resets at the start of each new year.

For each `(year, layer_name)`, process claims in chronological order by `date`; if two claims have the same date, sort by `claim_id` ascending.

For each claim:

```python
ceded_pre_aal = ...  # per Part 2
remaining_aal = aal - paid_so_far
ceded = min(ceded_pre_aal, max(remaining_aal, 0))
paid_so_far += ceded
```

Once `paid_so_far >= aal`, later claims in that year cede zero to that layer.

After processing all claims, aggregate `ceded` by `(year, layer_name)` for the output.

## Part 4 — Driver Script

A small script that:

1. Reads `claims.csv` and `layers.csv` (sample files provided).
2. Calls `allocate_claims`.
3. Writes the result to `cessions.csv`.

Format:
```
python run.py --claims claims.csv --layers layers.csv --output cessions.csv
```

---

## What We're Evaluating

- **Correctness** of the three ALAE treatments and AAL handling
- **Code organization** — pure layer math separated from AAL bookkeeping separated from aggregation separated from I/O
- **Type hints and clear function contracts**
- **Documentation**  — docstrings and README
- **Tests**
- **Edge case handling**


## What We're NOT Evaluating

- Performance / vectorization tricks (loops are fine if correct)
- Reinsurance features beyond the spec (reinstatements, FX, participation, cession on a cession, etc. — all out of scope)
- Plotting or reporting beyond the CSV output

---

## Sanity-Check Example #1: Per-claim layer math

Given a single claim of `loss = 4,000,000`, `alae = 500,000` in 2023, against:

| layer | attachment | limit | aal | alae_treatment |
|---|---|---|---|---|
| L1 | 1,000,000 | 1,000,000 | 2,000,000 | pro_rata |
| L2 | 2,000,000 | 3,000,000 | 5,000,000 | part_of  |
| L3 | 5,000,000 | 5,000,000 | 5,000,000 | excluded |

Expected output (no AAL binds — only one claim):

| year | layer_name | ceded_amount |
|---|---|---|
| 2023 | L1 | 1,125,000.00 |
| 2023 | L2 | 2,500,000.00 |
| 2023 | L3 | 0.00 |

---

## Sanity-Check Example #2: AAL exhaustion and annual reset

Claims:

| claim_id | date | loss | alae |
|---|---|---:|---:|
| C1 | 2023-01-01 | 2,000,000 | 0 |
| C2 | 2023-02-01 | 2,000,000 | 0 |
| C3 | 2024-01-01 | 2,000,000 | 0 |

Layer:

| layer_name | attachment | limit | aal | alae_treatment |
|---|---:|---:|---:|---|
| L1 | 0 | 1,000,000 | 1,500,000 | excluded |

Expected output:

| year | layer_name | ceded_amount |
|---|---|---:|
| 2023 | L1 | 1,500,000 |
| 2024 | L1 | 1,000,000 |

## Submission

- Git repo (preferred) or zipped folder
- `README.md` with: setup, run, test commands; a short note on tradeoffs and AI tool usage
- Sample input CSVs are provided; `run.py` should reproduce a `cessions.csv` against them
