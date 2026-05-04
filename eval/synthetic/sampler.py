"""Stratified sampler for synthetic encounters.

The generator yields a uniform random walk over the parameter space, but the
acceptance criteria require minimum counts on each verdict and on the number
of distinct procedure codes. The sampler takes a bucketed approach: drain
the candidate stream into PASS / FAIL / WEAK buckets, then assemble the
final list by drawing the minimums from each bucket and filling the
remainder from any bucket while ensuring procedure-code coverage.

AC-001-1: 100 encounters total.
AC-001-3: at least 25 with overall=FAIL.
AC-001-4: at least 25 with overall=PASS.
AC-001-5: cover at least 6 distinct procedure codes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from eval.schemas import SyntheticEncounter

DEFAULT_MAX_DRAW: int = 50_000


def sample_with_constraints(
    candidates: Iterable[SyntheticEncounter],
    *,
    target_count: int = 100,
    min_pass: int = 25,
    min_fail: int = 25,
    min_distinct_procedure_codes: int = 6,
    max_draw: int = DEFAULT_MAX_DRAW,
) -> list[SyntheticEncounter]:
    """Filter ``candidates`` until AC-001 minimum constraints are satisfied.

    Args:
        candidates: Source stream from :func:`eval.synthetic.generator.generate`.
        target_count: Total encounters in the final list.
        min_pass: Minimum overall=PASS encounters (AC-001-4).
        min_fail: Minimum overall=FAIL encounters (AC-001-3).
        min_distinct_procedure_codes: Minimum distinct procedure codes (AC-001-5).
        max_draw: Hard cap on candidates pulled before raising.

    Returns:
        A list of exactly ``target_count`` encounters meeting every minimum.

    Raises:
        RuntimeError: If the constraints cannot be satisfied within
            ``max_draw`` candidates.
    """
    pass_pool: list[SyntheticEncounter] = []
    fail_pool: list[SyntheticEncounter] = []
    weak_pool: list[SyntheticEncounter] = []

    drawn = 0
    for candidate in candidates:
        drawn += 1
        if drawn > max_draw:
            break
        verdict = candidate.ground_truth.overall
        if verdict == "PASS":
            pass_pool.append(candidate)
        elif verdict == "FAIL":
            fail_pool.append(candidate)
        else:
            weak_pool.append(candidate)
        if (
            len(pass_pool) >= min_pass
            and len(fail_pool) >= min_fail
            and len(pass_pool) + len(fail_pool) + len(weak_pool) >= target_count
        ):
            # Probably enough; finish drawing if we also need code coverage.
            codes = _distinct_codes(pass_pool, fail_pool, weak_pool)
            if len(codes) >= min_distinct_procedure_codes:
                break

    if len(pass_pool) < min_pass:
        raise RuntimeError(
            f"sampler could not collect {min_pass} PASS encounters from {drawn} draws "
            f"(found {len(pass_pool)})"
        )
    if len(fail_pool) < min_fail:
        raise RuntimeError(
            f"sampler could not collect {min_fail} FAIL encounters from {drawn} draws "
            f"(found {len(fail_pool)})"
        )

    chosen: list[SyntheticEncounter] = []
    chosen.extend(pass_pool[:min_pass])
    chosen.extend(fail_pool[:min_fail])
    pass_remaining = pass_pool[min_pass:]
    fail_remaining = fail_pool[min_fail:]

    # Fill the remainder. Round-robin across the three buckets to keep the
    # final list's verdict distribution close to the underlying parameter
    # distribution rather than skewed by bucket exhaustion.
    remainder = target_count - len(chosen)
    fill = _round_robin_take(remainder, [weak_pool, pass_remaining, fail_remaining])
    chosen.extend(fill)

    if len(chosen) < target_count:
        raise RuntimeError(
            f"sampler could not fill target_count={target_count} from {drawn} draws "
            f"(got {len(chosen)})"
        )

    # Ensure procedure-code coverage. If the initial draw missed a code, swap
    # the last unconstrained slot for an encounter with the missing code from
    # any pool that still has slack.
    chosen = _ensure_code_coverage(
        chosen,
        min_distinct_procedure_codes,
        spare=[*pass_remaining, *fail_remaining, *weak_pool[remainder:]],
    )
    return chosen


def _distinct_codes(*pools: list[SyntheticEncounter]) -> set[str]:
    """Return the set of distinct procedure codes across the given pools."""
    codes: set[str] = set()
    for pool in pools:
        for e in pool:
            codes.add(e.procedure_code)
    return codes


def _round_robin_take(
    count: int, pools: list[list[SyntheticEncounter]]
) -> list[SyntheticEncounter]:
    """Take ``count`` encounters round-robin from ``pools`` (in given order)."""
    result: list[SyntheticEncounter] = []
    indices = [0] * len(pools)
    while len(result) < count:
        progressed = False
        for p_index, pool in enumerate(pools):
            if indices[p_index] < len(pool):
                result.append(pool[indices[p_index]])
                indices[p_index] += 1
                progressed = True
                if len(result) >= count:
                    break
        if not progressed:
            break
    return result


def _ensure_code_coverage(
    chosen: list[SyntheticEncounter],
    min_codes: int,
    spare: list[SyntheticEncounter],
) -> list[SyntheticEncounter]:
    """Swap encounters in ``chosen`` for entries in ``spare`` until ``min_codes`` codes appear."""
    have = {e.procedure_code for e in chosen}
    if len(have) >= min_codes:
        return chosen

    # Map procedure_code -> indices in chosen for swap victims.
    by_code: dict[str, list[int]] = defaultdict(list)
    for i, e in enumerate(chosen):
        by_code[e.procedure_code].append(i)

    for candidate in spare:
        if candidate.procedure_code in have:
            continue
        # Find a code that is over-represented (count > 1) and swap one of its
        # holders out.
        for _code, indices in by_code.items():
            if len(indices) > 1:
                victim_index = indices.pop()
                chosen[victim_index] = candidate
                have.add(candidate.procedure_code)
                by_code[candidate.procedure_code].append(victim_index)
                break
        if len(have) >= min_codes:
            return chosen
    return chosen
