"""Verify the manuscript's quantitative tables against the public aggregate reports."""
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent / "implementation/reports/qamc_contextual_match_v2_20261112"


def markdown_rows(text):
    for line in text.splitlines():
        if line.startswith("|"):
            yield [cell.strip().replace("**", "") for cell in line.strip("|").split("|")]


def latex_rows(paper, name):
    label = rf"\label{{tab:{name}}}"
    if paper.count(label) != 1:
        raise ValueError(f"Expected one table label {name!r}")
    table = paper.split(label, 1)[0].rsplit(r"\begin{tabular}", 1)[1]
    body = table.split(r"\midrule", 1)[1].split(r"\bottomrule", 1)[0]
    for line in body.strip().splitlines():
        line = re.sub(r"\\textbf\{([^{}]+)\}", r"\1", line)
        yield [cell.strip() for cell in line.removesuffix("\\\\").split("&")]


def require(actual, expected, label):
    if actual != expected:
        raise ValueError(f"{label}: manuscript {actual!r} differs from source {expected!r}")


def count(s):
    return int(s.replace(",", ""))


def check(root=REPORTS, manuscript=HERE / "paper.tex"):
    paper = manuscript.read_text()
    common = (root / "native_residual_v1/COMMON_COMPARISON_CLOSURE.md").read_text()
    endpoint = (root / "ipe_c_two_endpoint_completion_v1/READOUT.md").read_text()
    comparison = json.loads((root / "persist_selected_gepa_completion_v1/CONTROLS.json").read_text())

    strata = {"Overall": "All paired", "All A": "All A", "Only B": "Only B present",
              "Contains C": "Contains C", "Unflagged": "Exclude any known grading flag"}
    public_rpe = {r[0]: r[1:] for r in markdown_rows(endpoint) if r[0] in strata.values()}
    seen_strata = set()
    for first, positions, *points in latex_rows(paper, "rpe"):
        stratum, tasks = re.fullmatch(r"(.+) \((\d+)\)", first).groups()
        source = public_rpe[strata[stratum]]
        expected = tuple(map(count, [*source[0].split("/"), *source[1:]]))
        require(tuple(map(count, [tasks, positions, *points])), expected, f"RPEval {stratum}")
        seen_strata.add(stratum)
    require(seen_strata, strata.keys(), "RPEval strata")

    six_method = common.split("## Adding the always-task endpoint", 1)[1].split("## BenchPreS", 1)[0]
    public_external = {r[0]: tuple(map(count, r[1:5])) for r in list(markdown_rows(six_method))[2:]}
    seen_external = set()
    for method, *points in latex_rows(paper, "external"):
        source_name = method.replace(" reconstructed", " reconstruction").replace(" adapted", " adaptation")
        require(tuple(map(count, points)), public_external[source_name], f"RPEval {method}")
        seen_external.add(source_name)
    require(seen_external, public_external.keys(), "RPEval comparison methods")

    whole_task = json.loads((root / "paper_rpe_paired_uncertainty_v1/SUMMARY.json").read_text())
    overall = whole_task["subsets"]["overall"]
    match = re.search(
        r"Whole-task Match is (\d+)/(\d+), versus (\d+)/(\d+) without history and (\d+)/(\d+) with full history\.",
        paper,
    )
    expected = tuple(v for label in ("IPE_C", "TASK_ONLY", "RPR_PAPER_FULL")
                     for v in (overall["scores"][label]["exact_all_positions"], overall["tasks"]))
    require(tuple(map(count, match.groups())) if match else None, expected, "RPEval whole-task abstract")
    full = overall["paired"]["RPR_PAPER_FULL"]["micro"]
    match = re.search(
        r"Neither endpoint is exact on (\d+) of the (\d+) tasks\..*?\[([\d.]+), ([\d.]+)\] percentage "
        r"points \((\d+) observed groups\).*? between (\d+) and (\d+) positions\.",
        paper,
        re.S,
    )
    expected = (overall["exact_endpoint_opportunities"]["neither_exact"], overall["tasks"],
                *[round(x, 2) for x in full["resampled_source_group_interval_pp"]], full["group_count"],
                *whole_task["missing_sensitivity_delta_count"]["RPR_PAPER_FULL"]["micro"])
    require(tuple(map(float, match.groups())) if match else None, expected, "RPEval source sensitivity")

    behavior = json.loads((root / "paper_rpe_behavior_alignment_v1/SUMMARY.json").read_text())
    measured = re.search(
        r"On (\d+) exposed source groups, .*?realization at (\d+)/(\d+), (\d+)/(\d+), and (\d+)/(\d+)"
        r".*?together for (\d+), (\d+), and (\d+) of the (\d+) tasks\.",
        paper,
        re.S,
    )
    names = ("IPE_C", "TASK_ONLY", "RPR_PAPER_FULL")
    expected = (behavior["groups"], *(x for a in names for x in
                (behavior["scores"][a]["REALIZED"], behavior["C_positions"])),
                *(behavior["scores"][a]["joint_C_realized"] for a in names), behavior["tasks"])
    require(tuple(map(count, measured.groups())) if measured else None, expected, "RPEval execution-side audit")

    reservation = json.loads((root / "rpe_constraint_reservation_v1/SUMMARY.json").read_text())
    reserved = reservation["comparisons"]["RESERVED/TOP_NEXT"]["all"]
    positions = reserved["match"]["positions"]
    primary = (
        reserved["allocation"]["tasks"], reserved["match"]["first"], positions,
        reserved["match"]["second"], positions, reserved["match"]["tasks"],
        reserved["severity"]["FM"]["second"], reserved["severity"]["FM"]["first"],
        reserved["severity"]["OPB"]["second"], reserved["severity"]["OPB"]["first"],
    )
    reservation_pattern = (
        r"On (\d+) triggered tasks, .* obtains (\d+)/(\d+) vs\.\\ (\d+)/(\d+) Match on "
        r"(\d+) pairs, lowering feasibility severity from (\d+) to (\d+) while increasing "
        r"overuse from (\d+) to (\d+)\."
    )
    match = re.search(reservation_pattern, paper)
    require(tuple(map(count, match.groups())) if match else None, primary, "RPEval reserved slot")
    reserved_ipe = reservation["comparisons"]["RESERVED/IPE_C"]["all"]["match"]
    match = re.search(r"IPE-C scores (\d+)/(\d+) on these pairs\.", paper)
    require(tuple(map(count, match.groups())) if match else None,
            (reserved_ipe["second"], reserved_ipe["positions"]), "RPEval reserved-slot IPE-C control")

    tracks = {"Overall": "all", "Sycophancy": "sycophancy", "Cross-domain": "cross_domain",
              "Strict beneficial use": "beneficial_memory_usage"}
    seen_tracks = set()
    for track, reference, candidate in latex_rows(paper, "persist"):
        pair = comparison[f"PB_RUBRIC/{tracks[track]}"]
        expected = [f"{pair[k]}/{pair['common']}" for k in ("reference_pass", "selected_pass")]
        require([reference, candidate], expected, f"PersistBench {track}")
        seen_tracks.add(track)
    require(seen_tracks, tracks.keys(), "PersistBench tracks")

    risk = json.loads((root / "persist_equal_cap_safety_v1/SUMMARY.json").read_text())
    risk_tracks = {"Sycophancy": "sycophancy", "Cross-domain": "cross_domain"}
    seen_risk_tracks = set()
    for track, *observed in latex_rows(paper, "persist_risk"):
        track_result = risk["splits"][risk_tracks[track]]["both"]
        expected = [f"{track_result['methods'][arm]['states'].get('FAIL', 0)}/{track_result['tasks']}"
                    for arm in ("ROUTED", "EMPTY", "FULL")]
        require(observed, expected, f"Equal-cap risk {track}")
        seen_risk_tracks.add(track)
    require(seen_risk_tracks, risk_tracks.keys(), "Equal-cap PersistBench tracks")

    bench_line, = (r[1] for r in markdown_rows(common) if r[0].startswith("BenchPreS, Strong Gate"))
    mr, aar, nonbold = (
        re.search(pattern, bench_line).groups()[::-1]
        for pattern in (r"MR (\d+/\d+) vs (\d+/\d+)", r", AAR (\d+/\d+) vs (\d+/\d+)",
                        r"Non-bold AAR is (\d+/\d+) vs (\d+/\d+)")
    )
    completeness = re.search(r"both completeness (\d+\.\d+)", bench_line)[1]
    public_bench = {"MR": mr, "AAR": aar, "Non-bold AAR": nonbold,
                    "Mean completeness": (completeness, completeness)}
    seen_metrics = set()
    for label, *pair in latex_rows(paper, "bench"):
        metric = label.split("$", 1)[0].strip()
        require(tuple(pair), public_bench[metric], f"BenchPreS {metric}")
        seen_metrics.add(metric)
    require(seen_metrics, public_bench.keys(), "BenchPreS metrics")
    return 5 + sum(map(len, (seen_strata, seen_external, seen_tracks, seen_risk_tracks, seen_metrics)))


if __name__ == "__main__":
    print(f"Verified {check()} manuscript comparisons against the public evidence")
