#!/usr/bin/env python3
"""CLI driver for the Layered Loss Allocation calculator.

Usage
-----
    python run.py --claims claims.csv --layers layers.csv --output cessions.csv
"""

from __future__ import annotations

import argparse

import pandas as pd

from src.allocator import allocate_claims


def main(argv: list[str] | None = None) -> None:
    """Parse arguments, run allocation, and write output."""
    parser = argparse.ArgumentParser(
        description="Allocate insurance claims to reinsurance layers."
    )
    parser.add_argument(
        "--claims",
        required=True,
        help="Path to the claims CSV file.",
    )
    parser.add_argument(
        "--layers",
        required=True,
        help="Path to the layers CSV file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path for the output cessions CSV file.",
    )
    args = parser.parse_args(argv)

    # Read inputs
    claims_df = pd.read_csv(args.claims)
    layers_df = pd.read_csv(args.layers)

    # Run allocation
    result = allocate_claims(claims_df, layers_df)

    # Write output
    result.to_csv(args.output, index=False)
    print(f"Cessions written to {args.output} ({len(result)} rows)")


if __name__ == "__main__":
    main()
