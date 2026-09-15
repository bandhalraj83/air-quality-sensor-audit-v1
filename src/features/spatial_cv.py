"""
Stage 3 -- spatial cross-validation fold assignment.

Never use random k-fold for this problem: ground stations are spatially
autocorrelated with their neighbors, so a random row-level split leaks
information between train and test and makes Stage 4's CV metrics look far
better than the model actually performs at genuinely unmonitored locations
-- which is the whole point of this project. Every function here assigns
folds by GROUP (station), so a station's rows are always entirely in the
train set or entirely in the test set, never split across both.
"""
from __future__ import annotations

import pandas as pd
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut

from . import config


def assign_spatial_folds(df: pd.DataFrame, group_col: str = None, n_splits: int = None):
    """
    Returns (fold: pd.Series aligned to df.index, strategy: str).

    Automatically falls back to leave-one-station-out when there are too
    few distinct stations for stable k-fold metrics (config.MIN_STATIONS_FOR_KFOLD) --
    relevant for exactly the sparse-network Indian cities this project is
    built around.
    """
    group_col = group_col or config.GROUP_COLUMN
    n_splits = n_splits or config.DEFAULT_N_SPLITS

    groups = df[group_col]
    n_groups = groups.nunique()

    if n_groups < 2:
        raise ValueError(
            f"Only {n_groups} distinct station(s) survive filtering -- cannot do spatial CV at all. "
            f"Check Stage 2's output and the completeness threshold in config.py."
        )

    fold = pd.Series(-1, index=df.index, dtype=int)

    if n_groups < config.MIN_STATIONS_FOR_KFOLD:
        splitter = LeaveOneGroupOut()
        strategy = f"leave-one-station-out ({n_groups} stations -> {n_groups} folds)"
    else:
        n_splits = min(n_splits, n_groups)
        splitter = GroupKFold(n_splits=n_splits)
        strategy = f"{n_splits}-fold grouped by station ({n_groups} stations)"

    for fold_idx, (_, test_idx) in enumerate(splitter.split(df, groups=groups)):
        fold.iloc[test_idx] = fold_idx

    return fold, strategy


def fold_summary(df: pd.DataFrame, fold_col: str = "cv_fold", group_col: str = None) -> pd.DataFrame:
    group_col = group_col or config.GROUP_COLUMN
    return (
        df.groupby(fold_col)
        .agg(n_rows=(group_col, "size"), n_stations=(group_col, "nunique"))
        .reset_index()
    )
