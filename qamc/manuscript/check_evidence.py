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
    return sum(map(len, (seen_strata, seen_external, seen_tracks, seen_risk_tracks, seen_metrics)))


if __name__ == "__main__":
    print(f"Verified {check()} manuscript rows against the public evidence")
