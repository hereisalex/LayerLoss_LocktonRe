# Layered Loss Allocation

A reinsurance cession calculator that allocates insurance claims to reinsurance layers based on attachment points, per-occurrence limits, annual aggregate limits, and three ALAE (Allocated Loss Adjustment Expense) treatments.

## Setup

```bash
# Python 3.11+ required
pip install -r requirements.txt
```

## Run

```bash
python run.py --claims claims.csv --layers layers.csv --output cessions.csv
```

## Test

```bash
python -m pytest tests/ -v
```

## Project Structure

```
├── src/
│   ├── layer_math.py    # Per-claim cession: 3 ALAE treatments (excluded, pro_rata, part_of)
│   ├── aal.py           # Annual Aggregate Limit bookkeeping
│   ├── validation.py    # Input validation with descriptive error messages
│   └── allocator.py     # Orchestrator: validate → compute → cap → aggregate
├── tests/
│   ├── test_layer_math.py   # Unit tests for each ALAE treatment
│   ├── test_aal.py          # Unit tests for AAL exhaustion and reset
│   ├── test_validation.py   # Unit tests for input validation
│   └── test_allocator.py    # Integration tests (sanity checks + edge cases)
├── run.py               # CLI driver script
├── claims.csv           # Sample claims input
├── layers.csv           # Sample layers input
└── requirements.txt     # pandas, pytest
```

## Design Decisions

- **Separation of concerns** — The core math (`layer_math.py`), AAL bookkeeping (`aal.py`), validation (`validation.py`), and orchestration (`allocator.py`) each live in their own module with clear interfaces. This makes each piece independently testable and easier to reason about.

- **Clarity over cleverness** — The assignment spec explicitly says performance and vectorization tricks are not evaluated. I used straightforward loops for AAL tracking where chronological ordering is essential, and `.apply()` for per-row layer math. Both are easy to read, audit, and debug.

- **Dispatch table for ALAE treatments** — Rather than an if/elif chain, `layer_math.py` uses a dictionary mapping treatment names to handler functions. All three handlers share a uniform `(loss, alae, attachment, limit)` signature, so the dispatch table holds direct function references with no lambda adapters. Adding a new treatment is a one-line change.

- **Comprehensive validation** — `validation.py` checks for missing columns, null values, type errors, out-of-range values, duplicate claim IDs, duplicate layer names, and invalid enum values, all with descriptive error messages. This is designed to fail fast with helpful messages rather than produce silently wrong results.

- **Zero-cession rows** — The spec requires a row for every `(year, layer_name)` combination, including years where a layer had no claims. The orchestrator creates a full index of all year/layer combinations and left-joins the aggregated results, filling missing entries with zero.

- **Type-safe contracts** — Public APIs use `Literal["excluded", "pro_rata", "part_of"]` (via the `AlaeTreatment` type alias) rather than bare `str`, making the valid inputs self-documenting and statically checkable. Each module exports an `__all__` to declare its public surface.

## AI Tool Usage

I used an AI coding assistant (Antigravity / Claude) as a pair-programming partner throughout this project. Specifically:

- **Analysis** — I had the AI review the assignment spec and job posting together to produce a detailed breakdown of inputs, outputs, requirements, and evaluation criteria before writing any code.
- **Implementation planning** — The AI helped design the module structure and phased execution order to ensure clean separation of concerns.
- **Code generation** — Implementation code was generated collaboratively, with me reviewing and validating each module against the spec's sanity-check examples.
- **Test design** — The AI helped identify edge cases (division-by-zero guards, AAL tiebreaking, zero-cession rows) and generated comprehensive test coverage.
- **Self-review** — After the initial implementation, I had the AI simulate an evaluation of the submission against the assignment rubric (correctness, code organization, type hints, documentation, tests, edge cases). This identified several concrete improvements: uniform handler signatures for the dispatch table, `Literal` typing for treatment strings, `__all__` declarations, duplicate `layer_name` validation, empty-input handling, output schema tests, and removal of linting artifacts. These improvements were then applied in a follow-up pass.

All code was reviewed against the assignment's two sanity-check examples and passes all 60 tests.
