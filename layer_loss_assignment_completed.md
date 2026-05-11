# Assignment Completion: Layered Loss Allocation

This document walks through every requirement and evaluation criterion from the original assignment, with direct references to the implementing code, reasoning for design decisions, and verification of expected outputs.

---

## Context

> *You'll produce a year-by-layer cession report from a portfolio of claims.*

The complete pipeline lives in [allocator.py](src/allocator.py#L18-L112), which orchestrates validation → normalisation → cross-join → per-claim math → AAL capping → aggregation → zero-fill, producing the required `(year, layer_name, ceded_amount)` output.

> ***AI tools:** Use any AI coding assistant you'd like. Explain in the README how you used it.*

Disclosed in [README.md](README.md#L65-L73) under "AI Tool Usage". Documents five phases of AI assistance: analysis, implementation planning, code generation, test design, and self-review.

---

## Setup

> *Python 3.11+ / `pandas` is expected*

- [requirements.txt](requirements.txt) specifies `pandas>=2.0` and `pytest>=7.0`.
- All source files use `from __future__ import annotations` for forward-reference syntax available in 3.11+.
- Setup instructions in [README.md](README.md#L5-L10).

---

## Part 1 — The Function

> *Implement:*
> ```python
> def allocate_claims(claims_df: pd.DataFrame, layers_df: pd.DataFrame) -> pd.DataFrame:
> ```

Implemented at [allocator.py:L18-L21](src/allocator.py#L18-L21) with exact signature match. Full NumPy-style docstring at [allocator.py:L22-L48](src/allocator.py#L22-L48) documenting parameters, return value, and `ValueError` contract.

### Inputs

> ***`claims_df`** — `claim_id` (str, unique), `date` (date), `loss` (float ≥ 0), `alae` (float ≥ 0)*

Validated by [validate_claims](src/validation.py#L25-L67):
- Required columns checked at [L36](src/validation.py#L36) against `{"claim_id", "date", "loss", "alae"}` defined at [L14](src/validation.py#L14).
- Null checks at [L38-L45](src/validation.py#L38-L45).
- `claim_id` uniqueness enforced at [L47-L55](src/validation.py#L47-L55).
- Date parseability verified at [L57-L63](src/validation.py#L57-L63) using ISO 8601 format.
- `loss ≥ 0` and `alae ≥ 0` enforced at [L65-L67](src/validation.py#L65-L67) via the `_check_numeric_non_negative` helper.

> ***`layers_df`** — `layer_name` (str), `attachment` (float ≥ 0), `limit` (float > 0), `aal` (float > 0), `alae_treatment` (str ∈ {part_of, pro_rata, excluded})*

Validated by [validate_layers](src/validation.py#L70-L114):
- Required columns checked at [L82](src/validation.py#L82) against the set at [L15-L21](src/validation.py#L15-L21).
- Null checks at [L84-L91](src/validation.py#L84-L91).
- `layer_name` uniqueness enforced at [L93-L101](src/validation.py#L93-L101). The spec uses `layer_name` as a grouping key for AAL; duplicates would silently produce incorrect results. This goes slightly beyond the spec to prevent a subtle bug.
- `attachment ≥ 0` at [L104](src/validation.py#L104); `limit > 0` and `aal > 0` at [L105-L106](src/validation.py#L105-L106).
- `alae_treatment` enum enforcement at [L108-L114](src/validation.py#L108-L114) against `{"excluded", "pro_rata", "part_of"}` defined at [L22](src/validation.py#L22).

> *Raise `ValueError` on invalid input.*

Both `validate_claims` and `validate_layers` raise `ValueError` with descriptive messages for every constraint violation. Tested across 15 cases in [test_validation.py](tests/test_validation.py) covering missing columns, nulls, duplicates, negative values, zero-where-positive-required, invalid enums, and unparseable dates.

### Output

> *A long-format DataFrame: `year` (int), `layer_name` (str), `ceded_amount` (float). One row per `(year, layer_name)` combination, including zero rows.*

- Output schema produced at [allocator.py:L97-L110](src/allocator.py#L97-L110): a full Cartesian product of `(year, layer_name)` is built, left-joined with aggregated results, and missing entries filled with `0.0`.
- Output column and dtype assertions in [TestOutputSchema](tests/test_allocator.py#L82-L134): verifies exact column list `["year", "layer_name", "ceded_amount"]`, `year` is int, and `ceded_amount` is float64.
- Zero-row inclusion tested in [test_multiple_layers_multiple_years](tests/test_allocator.py#L193-L210): 2 years × 2 layers = 4 rows, even when some layers have zero cessions.

---

## Part 2 — Per-Claim Layer Math

> *`clamp(x, lo, hi)` means `max(lo, min(x, hi))`.*

Implemented at [layer_math.py:L24-L42](src/layer_math.py#L24-L42) with full docstring. Tested with 5 boundary cases in [TestClamp](tests/test_layer_math.py#L10-L24).

> *Each layer applies independently to each claim. Layers do not interact with each other.*

The cross-join at [allocator.py:L71](src/allocator.py#L71) creates every claim × layer combination, and `compute_cession_pre_aal` is applied per-row at [L74-L83](src/allocator.py#L74-L83). No layer's result feeds into another's calculation. Layer independence is tested explicitly in [test_layers_independent](tests/test_aal.py#L93-L105) and [test_multi_layer_aal_binding_interaction](tests/test_allocator.py#L212-L232).

### `excluded`

> *ALAE is not covered. `ceded_pre_aal = clamp(loss - attachment, 0, limit)`*

Implemented at [layer_math.py:L45-L52](src/layer_math.py#L45-L52). The `alae` parameter is accepted for signature uniformity but not used in the calculation. This is a deliberate design choice — all three handlers share the same `(loss, alae, attachment, limit)` signature so the [dispatch table](src/layer_math.py#L91-L95) holds direct function references with no adapter lambdas.

Tested with 6 cases in [TestExcluded](tests/test_layer_math.py#L29-L86): loss below attachment, within layer, exceeds limit, ALAE ignored, zero loss, and sanity check #1 L3.

### `pro_rata`

> *`loss_in_layer = clamp(loss - attachment, 0, limit)` / `alae_in_layer = alae * (loss_in_layer / loss) if loss > 0 else 0` / `ceded_pre_aal = loss_in_layer + alae_in_layer`*

Implemented at [layer_math.py:L55-L71](src/layer_math.py#L55-L71). The division-by-zero guard (`if loss > 0.0`) at [L67-L70](src/layer_math.py#L67-L70) matches the spec exactly.

**Decision:** When `loss = 0`, the spec defines `alae_in_layer = 0` regardless of ALAE amount. This means a claim with only ALAE and no loss will cede nothing under pro-rata, which makes sense — if loss doesn't pierce the layer, there's no ratio to apply.

Tested with 5 cases in [TestProRata](tests/test_layer_math.py#L91-L143): loss below attachment, partial fill, zero-loss div-by-zero guard, sanity check #1 L1, and full layer fill.

### `part_of`

> *`ground_up = loss + alae` / `ceded_pre_aal = clamp(ground_up - attachment, 0, limit)`*

Implemented at [layer_math.py:L74-L82](src/layer_math.py#L74-L82).

Tested with 5 cases in [TestPartOf](tests/test_layer_math.py#L148-L193): ground-up below attachment, within layer, exceeds limit, sanity check #1 L2, and zero-loss with nonzero ALAE (ALAE alone can pierce the layer under this treatment).

### Dispatch Mechanism

Rather than if/elif chains, the three handlers are wired through a dispatch table at [layer_math.py:L91-L95](src/layer_math.py#L91-L95). The public entry point [compute_cession_pre_aal](src/layer_math.py#L98-L136) looks up the handler and delegates. Invalid treatment names raise `ValueError` at [L131-L135](src/layer_math.py#L131-L135), tested in [TestInvalidTreatment](tests/test_layer_math.py#L198-L205).

The treatment string is typed as `AlaeTreatment = Literal["excluded", "pro_rata", "part_of"]` at [L19](src/layer_math.py#L19), making the valid values self-documenting and statically checkable.

---

## Part 3 — Annual Aggregate Limit

> *The AAL caps how much a layer pays in total in a single accident year. AAL applies separately by `(year, layer_name)` and resets at the start of each new year.*

Implemented in [aal.py:L15-L54](src/aal.py#L15-L54).

> *Process claims in chronological order by `date`; if two claims have the same date, sort by `claim_id` ascending.*

Sorting at [aal.py:L37](src/aal.py#L37): `df.sort_values(["year", "layer_name", "date", "claim_id"])`. Tiebreaking tested in [test_same_date_tiebreak_by_claim_id](tests/test_aal.py#L79-L91).

> ```python
> remaining_aal = aal - paid_so_far
> ceded = min(ceded_pre_aal, max(remaining_aal, 0))
> paid_so_far += ceded
> ```

Directly transcribed at [aal.py:L48-L50](src/aal.py#L48-L50). The loop at [L41-L51](src/aal.py#L41-L51) groups by `(year, layer_name)` and processes claims in sorted order. Each group resets `paid_so_far = 0.0` at [L45](src/aal.py#L45), which implements the annual reset.

**Decision:** I used an explicit loop rather than a cumulative-sum approach. The spec's pseudocode is inherently sequential (each claim's cession depends on the running total of prior claims), so a loop is the natural, auditable translation. The assignment explicitly states performance/vectorization is not evaluated.

> *Once `paid_so_far >= aal`, later claims in that year cede zero to that layer.*

Tested with 8 cases in [TestApplyAAL](tests/test_aal.py#L16-L121):
- Single claim under AAL → full cession ([L17-L24](tests/test_aal.py#L17-L24))
- Two claims exactly exhausting AAL ([L26-L36](tests/test_aal.py#L26-L36))
- Partial exhaustion on second claim ([L38-L48](tests/test_aal.py#L38-L48))
- Third claim after full exhaustion → zero ([L50-L62](tests/test_aal.py#L50-L62))
- AAL resets across years ([L64-L77](tests/test_aal.py#L64-L77))
- Same-date tiebreaking ([L79-L91](tests/test_aal.py#L79-L91))
- Layer independence ([L93-L105](tests/test_aal.py#L93-L105))
- Sanity check #2 ([L107-L121](tests/test_aal.py#L107-L121))

> *After processing all claims, aggregate `ceded` by `(year, layer_name)` for the output.*

Aggregation at [allocator.py:L90-L95](src/allocator.py#L90-L95) via `groupby(["year", "layer_name"]).sum()`.

---

## Part 4 — Driver Script

> *A small script that reads `claims.csv` and `layers.csv`, calls `allocate_claims`, writes to `cessions.csv`.*

Implemented in [run.py](run.py#L1-L54).

> *Format: `python run.py --claims claims.csv --layers layers.csv --output cessions.csv`*

CLI argument parsing at [run.py:L20-L38](run.py#L20-L38) using `argparse`. All three flags (`--claims`, `--layers`, `--output`) are `required=True`.

- CSV reading at [run.py:L41-L42](run.py#L41-L42)
- Allocation call at [run.py:L45](run.py#L45)
- CSV writing at [run.py:L48](run.py#L48)

Verified by running:
```
python run.py --claims claims.csv --layers layers.csv --output cessions.csv
→ Cessions written to cessions.csv (6 rows)
```

---

## What We're Evaluating

### Correctness

> *Correctness of the three ALAE treatments and AAL handling*

All three treatments match the spec formulas exactly. Both sanity-check examples produce the expected output:

**Sanity Check #1** — tested in [TestSanityCheck1](tests/test_allocator.py#L12-L50) and per-treatment in [test_sanity_check_1_L1](tests/test_layer_math.py#L121-L131), [test_sanity_check_1_L2](tests/test_layer_math.py#L175-L183), [test_sanity_check_1_L3](tests/test_layer_math.py#L79-L86):

| year | layer_name | expected | produced |
|---|---|---:|---:|
| 2023 | L1 | 1,125,000.00 | 1,125,000.00 ✓ |
| 2023 | L2 | 2,500,000.00 | 2,500,000.00 ✓ |
| 2023 | L3 | 0.00 | 0.00 ✓ |

**Sanity Check #2** — tested in [TestSanityCheck2](tests/test_allocator.py#L53-L79) and [test_sanity_check_2](tests/test_aal.py#L107-L121):

| year | layer_name | expected | produced |
|---|---|---:|---:|
| 2023 | L1 | 1,500,000 | 1,500,000 ✓ |
| 2024 | L1 | 1,000,000 | 1,000,000 ✓ |

### Code Organization

> *Pure layer math separated from AAL bookkeeping separated from aggregation separated from I/O*

| Concern | Module | Public API |
|---|---|---|
| Per-claim layer math | [layer_math.py](src/layer_math.py) | `compute_cession_pre_aal`, `clamp` |
| AAL bookkeeping | [aal.py](src/aal.py) | `apply_aal` |
| Input validation | [validation.py](src/validation.py) | `validate_claims`, `validate_layers` |
| Orchestration + aggregation | [allocator.py](src/allocator.py) | `allocate_claims` |
| CLI I/O | [run.py](run.py) | `main` |

Each module has a single responsibility and is independently testable. The orchestrator reads like a recipe: validate → normalise → cross-join → compute → cap → aggregate → fill zeros.

### Type Hints and Clear Function Contracts

> *Type hints and clear function contracts*

- All public functions have full type annotations: [allocate_claims](src/allocator.py#L18-L21), [compute_cession_pre_aal](src/layer_math.py#L98-L104), [apply_aal](src/aal.py#L15), [validate_claims](src/validation.py#L25), [validate_layers](src/validation.py#L70).
- `AlaeTreatment = Literal["excluded", "pro_rata", "part_of"]` at [layer_math.py:L19](src/layer_math.py#L19) makes the valid treatment values self-documenting rather than hiding them behind a bare `str`.
- Every module declares `__all__` ([layer_math.py:L21](src/layer_math.py#L21), [aal.py:L12](src/aal.py#L12), [validation.py:L11](src/validation.py#L11), [allocator.py:L15](src/allocator.py#L15)) to explicitly define the public API surface.
- Private helpers are prefixed with `_` (e.g., `_ceded_excluded`, `_check_required_columns`).

### Documentation

> *Docstrings and README*

- **README**: [README.md](README.md) with setup, run, and test commands ([L5-L22](README.md#L5-L22)), project structure ([L24-L45](README.md#L24-L45)), design decisions with rationale ([L47-L59](README.md#L47-L59)), and AI tool usage ([L65-L73](README.md#L65-L73)).
- **Module docstrings**: Every module has a top-level docstring explaining its purpose and scope (e.g., [layer_math.py:L1-L12](src/layer_math.py#L1-L12) lists all three treatments).
- **Function docstrings**: NumPy-style with Parameters, Returns, and Raises sections. Example: [allocate_claims](src/allocator.py#L22-L48) (26 lines), [compute_cession_pre_aal](src/layer_math.py#L105-L128) (23 lines), [apply_aal](src/aal.py#L16-L34) (18 lines).
- **Inline comments**: Section headers in the orchestrator (`# ── 1. Validate ──`, etc.) make the pipeline steps scannable at a glance.
- **Treatment formulas**: Each private handler's docstring includes the spec formula for cross-reference (e.g., [L48-L51](src/layer_math.py#L48-L51), [L58-L64](src/layer_math.py#L58-L64), [L77-L79](src/layer_math.py#L77-L79)).

### Tests

> *Tests*

**60 tests across 4 test files**, all passing:

| File | Tests | Scope |
|---|:---:|---|
| [test_layer_math.py](tests/test_layer_math.py) | 22 | `clamp`, 3 ALAE treatments × multiple scenarios, invalid treatment |
| [test_aal.py](tests/test_aal.py) | 8 | Under/exact/partial/full AAL exhaustion, year reset, tiebreaking, layer independence, sanity check #2 |
| [test_allocator.py](tests/test_allocator.py) | 15 | Both sanity checks, output schema (columns + dtypes), 7 edge cases including empty input |
| [test_validation.py](tests/test_validation.py) | 15 | Missing columns, nulls, duplicates (claim_id + layer_name), negative values, zero limits, bad enums, bad dates |

Tests mirror the source module structure (1:1 mapping). Test docstrings explain intent where non-obvious. `pytest.approx` used throughout for floating-point comparisons.

### Edge Case Handling

> *Edge case handling*

| Edge Case | Implementation | Test |
|---|---|---|
| `loss = 0` with `pro_rata` (div-by-zero) | Guard at [layer_math.py:L67-L70](src/layer_math.py#L67-L70) | [test_zero_loss_with_alae](tests/test_layer_math.py#L112-L119) |
| `loss = 0` with `part_of` (ALAE-only cession) | `ground_up = 0 + alae` at [L81](src/layer_math.py#L81) | [test_zero_loss_nonzero_alae](tests/test_layer_math.py#L185-L193) |
| AAL partial exhaustion | `min(ceded_pre_aal, max(remaining, 0))` at [L49](src/aal.py#L49) | [test_aal_partial_exhaustion](tests/test_aal.py#L38-L48) |
| AAL fully exhausted → zero | Same formula, remaining goes to 0 | [test_aal_fully_exhausted_third_claim_zero](tests/test_aal.py#L50-L62) |
| AAL resets across years | `groupby(["year", "layer_name"])` at [L41](src/aal.py#L41) | [test_aal_resets_across_years](tests/test_aal.py#L64-L77) |
| Same-date tiebreaking | `sort_values([..., "date", "claim_id"])` at [L37](src/aal.py#L37) | [test_same_date_tiebreak_by_claim_id](tests/test_aal.py#L79-L91) |
| Layers independent under AAL | `groupby` isolates each layer | [test_layers_independent](tests/test_aal.py#L93-L105), [test_multi_layer_aal_binding_interaction](tests/test_allocator.py#L212-L232) |
| Zero-cession `(year, layer)` rows | Full-index left join at [allocator.py:L97-L107](src/allocator.py#L97-L107) | [test_multiple_layers_multiple_years](tests/test_allocator.py#L193-L210) |
| Empty claims DataFrame | Early return at [allocator.py:L56-L58](src/allocator.py#L56-L58) | [test_empty_claims](tests/test_allocator.py#L234-L251) |
| Duplicate `claim_id` | Validation at [validation.py:L47-L55](src/validation.py#L47-L55) | [test_duplicate_claim_id](tests/test_validation.py#L31-L35) |
| Duplicate `layer_name` | Validation at [validation.py:L93-L101](src/validation.py#L93-L101) | [test_duplicate_layer_name](tests/test_validation.py#L103-L108) |
| Negative loss/alae | Validation at [validation.py:L65-L67](src/validation.py#L65-L67) | [test_negative_loss](tests/test_validation.py#L37-L41), [test_negative_alae](tests/test_validation.py#L43-L47) |
| `limit = 0` or `aal = 0` | Validation at [validation.py:L105-L106](src/validation.py#L105-L106) | [test_zero_limit](tests/test_validation.py#L79-L83), [test_zero_aal](tests/test_validation.py#L85-L89) |
| Invalid `alae_treatment` | Validation at [validation.py:L108-L114](src/validation.py#L108-L114) + runtime at [layer_math.py:L131-L135](src/layer_math.py#L131-L135) | [test_invalid_alae_treatment](tests/test_validation.py#L91-L95), [test_unknown_treatment_raises](tests/test_layer_math.py#L199-L205) |

---

## What We're NOT Evaluating

> *Performance / vectorization tricks (loops are fine if correct)*

Loops are used intentionally for AAL tracking ([aal.py:L47-L51](src/aal.py#L47-L51)) where the stateful, sequential nature of the algorithm makes vectorization non-trivial to get right. `.apply()` is used for per-row layer math ([allocator.py:L74-L83](src/allocator.py#L74-L83)) for clarity.

> *Reinsurance features beyond the spec*

Not implemented. No reinstatements, FX, participation, or cascading cessions.

> *Plotting or reporting beyond the CSV output*

Not implemented. Output is CSV only.

---

## Sanity-Check Example #1: Per-claim layer math

> *Given a single claim of `loss = 4,000,000`, `alae = 500,000` in 2023*

**L1 (pro_rata, att=1M, lim=1M):**
- `loss_in_layer = clamp(4M - 1M, 0, 1M) = 1,000,000`
- `alae_in_layer = 500K × (1M / 4M) = 125,000`
- `ceded = 1,125,000` ✓

**L2 (part_of, att=2M, lim=3M):**
- `ground_up = 4M + 500K = 4,500,000`
- `ceded = clamp(4.5M - 2M, 0, 3M) = 2,500,000` ✓

**L3 (excluded, att=5M, lim=5M):**
- `ceded = clamp(4M - 5M, 0, 5M) = 0` ✓

Tested end-to-end in [TestSanityCheck1](tests/test_allocator.py#L12-L50) and per-treatment in [test_sanity_check_1_L1](tests/test_layer_math.py#L121-L131), [test_sanity_check_1_L2](tests/test_layer_math.py#L175-L183), [test_sanity_check_1_L3](tests/test_layer_math.py#L79-L86).

---

## Sanity-Check Example #2: AAL exhaustion and annual reset

> *C1 (2023-01-01, 2M), C2 (2023-02-01, 2M), C3 (2024-01-01, 2M) against L1 (att=0, lim=1M, aal=1.5M, excluded)*

**2023:**
- C1: `ceded_pre_aal = clamp(2M, 0, 1M) = 1M` → `ceded = min(1M, 1.5M) = 1M`, `paid = 1M`
- C2: `ceded_pre_aal = 1M` → `ceded = min(1M, 0.5M) = 500K`, `paid = 1.5M`
- Year total: **1,500,000** ✓

**2024 (AAL resets):**
- C3: `ceded_pre_aal = 1M` → `ceded = min(1M, 1.5M) = 1M`
- Year total: **1,000,000** ✓

Tested end-to-end in [TestSanityCheck2](tests/test_allocator.py#L53-L79) and at the AAL level in [test_sanity_check_2](tests/test_aal.py#L107-L121).

---

## Submission

> *Git repo (preferred)*

Git repository with incremental commits:
```
feda7e1 Initial implementation: layered loss allocation calculator
5e2b931 Add reinsurance cession engine: 3 ALAE treatments, AAL bookkeeping, validation
b723db3 Tighten types, add empty-input/duplicate-layer guards, expand to 60 tests
1f3ddf3 docs: add comprehensive assignment completion report
4d0a16c docs: reference assignment completion report in README
```

> *`README.md` with: setup, run, test commands; a short note on tradeoffs and AI tool usage*

[README.md](README.md) contains all required sections: Setup ([L5-L10](README.md#L5-L10)), Run ([L12-L16](README.md#L12-L16)), Test ([L18-L22](README.md#L18-L22)), Design Decisions ([L47-L59](README.md#L47-L59)), AI Tool Usage ([L65-L73](README.md#L65-L73)).

> *Sample input CSVs are provided; `run.py` should reproduce a `cessions.csv` against them*

[claims.csv](claims.csv) and [layers.csv](layers.csv) are included. Running the driver script produces the verified [cessions.csv](cessions.csv) with 6 rows (2 years × 3 layers).
