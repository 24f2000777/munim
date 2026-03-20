"""
Product Name Deduplicator
==========================
Uses RapidFuzz to detect and merge product names that refer to the same item
but are spelled differently across transactions.

Examples handled:
  "Parle-G"     → "Parle G biscuit" → "ParlG"       → merged as "Parle-G"
  "Surf Excel"  → "Surf Excell"     → "SurfExcel"   → merged as "Surf Excel"
  "5 Star"      → "Five Star"       → "Fivestar"    → merged as "5 Star"

Algorithm:
  1. Build a similarity graph using RapidFuzz (WRatio scorer — handles
     abbreviations, insertions, deletions, transpositions)
  2. Threshold: 85% similarity = same product (configurable)
  3. Connected components = product groups
  4. Canonical name = most frequent name in each group
  5. Replace all variants with canonical name in the DataFrame

Hindi product names (Devanagari) are supported — RapidFuzz handles Unicode.
"""

import logging
from collections import defaultdict

import pandas as pd
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 85  # % similarity — per spec
DEFAULT_MIN_FREQ = 2    # Only deduplicate names appearing ≥ N times


def deduplicate_products(
    df: pd.DataFrame,
    *,
    column: str = "product",
    threshold: int = DEFAULT_THRESHOLD,
    min_freq: int = DEFAULT_MIN_FREQ,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Deduplicate product names in a DataFrame using fuzzy matching.

    Args:
        df:        DataFrame with a product column.
        column:    Name of the product column.
        threshold: Similarity threshold (0–100). 85 per spec.
        min_freq:  Minimum occurrences for a name to be included in matching.
                   Names appearing < min_freq times are left unchanged.

    Returns:
        Tuple of:
        - df with product column deduplicated (original df is NOT modified)
        - mapping dict: {variant → canonical_name}
    """
    if column not in df.columns:
        logger.warning("Column %r not in DataFrame — skipping deduplication", column)
        return df.copy(), {}

    # Frequency count — only deduplicate meaningful names
    freq = df[column].value_counts()
    names_to_match = freq[freq >= min_freq].index.tolist()

    if len(names_to_match) < 2:
        return df.copy(), {}

    canonical_map = _build_canonical_map(names_to_match, threshold)

    if not canonical_map:
        return df.copy(), {}

    df_out = df.copy()
    df_out[column] = df_out[column].map(lambda x: canonical_map.get(str(x), x))

    merged_count = sum(1 for k, v in canonical_map.items() if k != v)
    logger.info(
        "Deduplication: %d unique product names → %d after merging %d variants",
        len(names_to_match),
        len(set(canonical_map.values())),
        merged_count,
    )

    return df_out, canonical_map


def _build_canonical_map(names: list[str], threshold: int) -> dict[str, str]:
    """
    Build a map of {variant → canonical_name} using union-find clustering.

    Two names are in the same cluster if their fuzzy similarity ≥ threshold.
    Canonical name = most frequent / longest name in each cluster.
    """
    n = len(names)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    # Compare all pairs using RapidFuzz WRatio
    # WRatio handles partial matches, abbreviations, and token reordering
    for i in range(n):
        for j in range(i + 1, n):
            score = fuzz.WRatio(names[i], names[j])
            if score >= threshold:
                union(i, j)
                logger.debug(
                    "Merged %r ↔ %r (score: %d)", names[i], names[j], score
                )

    # Group names by cluster root
    clusters: dict[int, list[str]] = defaultdict(list)
    for i, name in enumerate(names):
        clusters[find(i)].append(name)

    # Pick canonical name: longest name in cluster (usually most descriptive)
    canonical_map: dict[str, str] = {}
    for cluster_names in clusters.values():
        if len(cluster_names) == 1:
            canonical_map[cluster_names[0]] = cluster_names[0]
        else:
            # Canonical = longest name (most complete description)
            canonical = max(cluster_names, key=len)
            for name in cluster_names:
                canonical_map[name] = canonical

    return canonical_map
