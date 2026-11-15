---
name: data-validation
description: Add or change data quality checks - schema, ranges, categories, missing values, duplicates, leakage, training-serving skew guards - and the tests that prove them. Use when data looks wrong, validation fails, a new data source or feature is added, or a monitoring alert should become a blocking check.
---

# Data validation and the data contract

The contract for each dataset is `configs/<dataset>.yaml`: `keys`, `features`, `leakage`, `checks.ranges`, `checks.categories` and `facts`. The checks are in `pipeline/validate.py` (`check()`), which returns `{"rows", "errors", "warnings", "passed"}`. Any error stops the pipeline and marks the `validate` run FAILED in MLflow.

## Checks that exist

1. Leakage guard: features ∩ (`leakage` ∪ target) must be empty.
2. Required columns are present.
3. No missing values in required columns.
4. No duplicate rows on `keys`.
5. Numeric ranges (`checks.ranges`) and allowed categories (`checks.categories`).
6. Labels are 0/1. A warning, not an error, flags a season with an unusual positive rate.

`validate` runs on the history (with labels) and on the 2026 provisional season (without labels).

## Add a check

- **A range or category:** edit `configs/<dataset>.yaml`. The column dictionary is in the dataset repo's README (`source.repo`, `source.folder`). Derive bounds from the domain, not only from the current data: a range that only fits today's data blocks tomorrow's.
- **A new kind of rule** (for example, a unit-change guard): add it to `check()` as an `errors.append(...)` with a message that names the column, the count and the rule. Keep the pattern of the existing checks.
- **A test for every rule** in `tests/test_data_contract.py`: break one row with `df.loc[...]`, call `check(cfg, df)` and assert on the error text. The `cfg` fixture runs each test for both datasets.

## Training-serving skew

`work/<ds>/raw/scenarios/serving_skew_window.json` holds the same requests as the API received them (`served`) and as the training pipeline computes them (`recomputed`). In one feature the unit changed: F1 `quali_gap_ms` arrives in seconds, SPL `travel_km` in miles. A range check catches a unit change only when the ranges don't overlap. Compare the medians, or the magnitude against the reference window, and test the rule on that file with `pipeline.data.read_window`.

## Verify

```bash
./scripts/run make validate    # needs make ingest first
./scripts/run make test
```

Report which rule you added, why, and the evidence: how many rows the rule flags on the history (it should be 0) and on the bad data.
