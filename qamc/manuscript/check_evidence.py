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
    secondary = json.loads((root / "rpe_external_whole_task_v1/RESULTS.json").read_text())["all"]
    method_keys = {'IPE-C': 'IPE_C', 'Always-Task': 'TASK_ONLY', 'RP-Reasoner reconstructed': 'RPR_PAPER_FULL', 'Des2Gen reconstructed': 'DES2GEN_FULL', 'MemAdapter adapted': 'MEMADAPTER_FULL', 'Strong Gate': 'GEPA_SELECTED_BOUNDS'}
    seen_external = set()
    for method, *points in latex_rows(paper, "external"):
        source_name = method.replace(" reconstructed", " reconstruction").replace(" adapted", " adaptation")
        source = secondary[method_keys[method]]
        require(tuple(map(count, points)), (*public_external[source_name], source["exact"], source["severity"]), f"RPEval {method}")
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

    group_out = (root / "native_residual_v1/BENCH_GROUP_OUT_RESULTS.md").read_text()
    allocation = re.search(r"All (\d+) exposed cases across seven profiles were common\.", group_out)
    controls = {r[0]: r[1:] for r in markdown_rows(group_out) if r[0] in ("Direct generation", "Content-first")}
    direct, content = controls["Direct generation"], controls["Content-first"]
    claim = re.search(
        r"replication on (\d+) tasks across seven profiles .*?realization from (\d+/\d+) to (\d+/\d+)"
        r" and total completeness from (\d+/\d+) to (\d+/\d+)\. Both versions have (\d+/\d+) misapplications",
        paper,
    )
    require(direct[2], content[2], "BenchPreS replication matched MR")
    expected = (allocation[1], direct[1], content[1], direct[3], content[3], direct[2])
    require(claim.groups() if claim else None, expected, "BenchPreS profile-disjoint replication")
    repeat_root = root / "benchpres_repeat_matched_v1"
    repeat = json.loads((repeat_root / "FINAL_REPLAY.json").read_text())
    misuse = json.loads((repeat_root / "FINAL_MISUSE_TRACE.json").read_text())
    fieldwise = json.loads((repeat_root / "FINAL_FIELDWISE.json").read_text())
    prior_waves = json.loads((repeat_root / "WAVES01234_REPLAY.json").read_text())
    require(repeat["full_allocation_terminal"], True, "BenchPreS terminal replay")
    paired = repeat["available_pairs"]
    expected = [str(v) for v in (paired["task_draw_pairs"], paired["tasks"], repeat["allocated_tasks"])]
    for name in ("MR", "AAR", "nonbold_AAR"):
        metric = paired["metrics"][name]
        expected.extend(f"{metric[key]}/{metric['denominator']}"
                        for key in ("gate_numerator", "selectivity_numerator"))
    nicknames = misuse["methods"]["PAPER_SELECTIVITY"]["by_attribute"]["nickname"]["judge_follow_literal_yes"]
    other_rates = []
    for arm in ("GEPA_SELECTED_BOUNDS", "PAPER_SELECTIVITY"):
        categories = misuse["methods"][arm]["by_attribute"]
        other = [group for name, group in categories.items() if name != "nickname"]
        hits = sum(group["judge_misuses"] for group in other)
        denominator = sum(group["inappropriate_positions"] for group in other)
        other_rates.append(f"{hits}/{denominator}")
    totals_key = "receipts_in_terminal_waves"
    late_timeouts = repeat[totals_key]["unknown_usage"] - prior_waves[totals_key]["unknown_usage"]
    expected.extend((str(nicknames), *other_rates, str(late_timeouts)))
    for name in ("MR", "AAR", "bold_AAR"):
        expected.extend(map(str, fieldwise["fieldwise_diagnostic_only"][name]["full_allocation_delta_numerator_bounds"]))
    claim = re.search(
        r"On (\d+) paired draws from (\d+) of the (\d+) allocated tasks, .*?MR (\d+/\d+) and (\d+/\d+), "
        r"AAR (\d+/\d+) and (\d+/\d+), and non-bold AAR (\d+/\d+) and (\d+/\d+), respectively\. "
        r"Exact nicknames account for (\d+) Selectivity misuse labels\. Outside nickname positions, MR is "
        r"(\d+/\d+) and (\d+/\d+)\. .*?after (\d+) transport timeouts\. "
        r".*?\$\[(-?\d+),(-?\d+)\]\$ MR positions, \$\[(-?\d+),(-?\d+)\]\$ AAR positions, "
        r"and \$\[(-?\d+),(-?\d+)\]\$ bold AAR positions",
        paper,
    )
    require(list(claim.groups()) if claim else None, expected, "BenchPreS repeat evidence and missing bounds")
    census = json.loads((repeat_root / "NONBOLD_CENSUS_RESULTS.json").read_text())
    common_census = census["paired_both_evaluators"]
    all_census = census["model_bounds"]["all_planned"]
    methods = ("GEPA_SELECTED_BOUNDS", "PAPER_SELECTIVITY")
    expected = [common_census["positions"], *(common_census[j][m] for j in ("Qwen", "GPT4.1") for m in methods),
                all_census["common_observed"], *(all_census["common_observed_sum"][m] for m in methods),
                census["frozen_nonbold_allocation"], *all_census["full_allocation_delta_numerator_bounds"]]
    match = re.search(
        r"On (\d+) common non-bold positions, Qwen gives Gate and Selectivity (\d+) and (\d+) reflected preferences, "
        r"and a masked GPT-4.1 single-attribute diagnostic gives (\d+) and (\d+)\..*?"
        r"Over all (\d+) paired GPT-4.1 positions, the counts are (\d+) and (\d+)\. "
        r"The full (\d+)-position missing-outcome bounds span \$\[(-?\d+),(-?\d+)\]\$",
        paper, re.S,
    )
    require([count(t) for t in match.groups()] if match else None, expected, "BenchPreS fixed-answer evaluator census")
    fr3 = json.loads((root / "persist_exposure_fr3_v1/SETTLEMENT_AUDIT.json").read_text())
    tracks = ("sycophancy", "cross_domain", "beneficial_memory_usage")
    policies = {"Selected": "SELECTED", "Switch": "GROUP", "Full": "FULL", "Empty": "EMPTY", "Rubric": "RUBRIC"}
    checked = []
    for method, *cells in latex_rows(paper, "persist_three"):
        checked.append(method)
        scores = [fr3["root_outcomes"][track][policies[method]] for track in tracks]
        values = [f"{stats.get('failure', 0)}/{stats.get('unknown', 0)}" for stats in scores]
        require(cells, values, f"Three deployments {method}")
    require(checked, list(policies), "Three deployment policies")
    feature_report = (root / "teacher_feature_actor_v1/RESULTS.md").read_text()
    feature_rows = [r for r in markdown_rows(feature_report) if r[0] in {"history_B", "history_C", "task_all_A"}]
    for subset, phrase in (
        (feature_rows, r"obtained (\d+), (\d+) and (\d+) matches out of (\d+) positions"),
        ([r for r in feature_rows if r[0] == "history_B"], r"they obtained (\d+), (\d+) and (\d+) out of (\d+)"),
        ([r for r in feature_rows if r[1] not in {"implicit/070", "explicit/089"}],
         r"the three scores were (\d+), (\d+) and (\d+) out of (\d+)"),
    ):
        totals = [sum(int(r[3].split("/")[i]) for r in subset) for i in range(3)]
        match = re.search(phrase, paper)
        require(list(map(int, match.groups())) if match else None, totals + [sum(int(r[2]) for r in subset)],
                "Direct generation illustration")
    transfer = json.loads((root / "rpe_pb_on_transfer_v1/SUMMARY.json").read_text())
    pattern = (r"Full, count-matched RP, and transfer matched (\d+), (\d+), and (\d+) of (\d+) "
               r"positions on the first draw and (\d+), (\d+), and (\d+) of (\d+) on the second")
    match = re.search(pattern, paper)
    expected = []
    for draw in ("0", "1"):
        values = transfer["draws"][draw]["assigned"]
        denoms = {values[arm]["positions"] for arm in ("FULL", "RP_K", "PB")}
        if len(denoms) != 1:
            raise ValueError("Transfer denominators differ")
        expected.extend(values[arm]["matched"] for arm in ("FULL", "RP_K", "PB"))
        expected.extend(denoms)
    require(list(map(int, match.groups())) if match else None, expected, "Transferred selector")
    folder = root / "single_external_roster_recovery_v1"
    panel = json.loads((folder / "COMPARISON_SUMMARY.json").read_text())
    bounds = json.loads((folder / "ALLOCATION.json").read_text())["v1_against"]
    scores = panel["scores"]
    for term in ("RPR_PAPER_FULL", "DES2GEN_FULL", "MEMADAPTER_FULL"):
        require(scores[term], scores["Default"], "Single-preference comparator tie")
    sentence = (f"On the {panel['strict_common']} tasks with complete strict scores, witnessed replacement "
                f"achieved {scores['V1']}/{panel['strict_common']} Match; RP, Des2Gen, MemAdapter and "
                f"ordinary selection each achieved {scores['Default']}/{panel['strict_common']}.")
    require(sentence in paper, True, "Single-preference common scores")
    require(bounds["RPR_PAPER_FULL"]["possible_net_match"], [1, 1], "All-assigned RP difference")
    require(bounds["MEMADAPTER_FULL"]["possible_net_match"], [-1, 5], "All-assigned MemAdapter bounds")
    ceiling = json.loads((root / "shared_history_activation_v1" / "PARENT_HEADROOM.json").read_text())
    strata = ("all_A", "B_only", "contains_C")
    for key, metric, expected in (("all", "possible_extra_match", [43, 12, 6]),
                                  ("neither_endpoint_flagged", "possible_extra_match", [37, 2, 6]),
                                  ("neither_endpoint_flagged", "groups_with_any_headroom", [6, 1, 1])):
        require([ceiling[s][key][metric] for s in strata], expected, "Saved endpoint opportunity")
    require("37, two, and six positions across six, one, and one source groups" in paper, True, "Endpoint ceiling prose")
    settled = list(markdown_rows((root / "shared_history_activation_v1/RESULTS.md").read_text()))
    total = next(r for r in settled if r[0] == "Total")
    require(total[1:], ["17","56/95","56/95","66/95"], "Common activation RPEval")
    require(f"both scored {total[2]} Match, compared with {total[4]} for IPE-C" in paper, True, "Activation prose")
    require(next(r for r in settled if r[0] == "Sycophancy")[1:4], ["3/3/0","3/3/0","6/0/0"], "Shared risk outcome")
    require(next(r for r in settled if r[0] == "Strict beneficial use")[1:4], ["6/0/0","6/0/0","3/0/3"], "Shared utility outcome")
    cj = json.loads((root / "persist_selected_crossjudge_fr3_v1/SUMMARY.json").read_text())["tables"]
    c = cj["sycophancy"]["both_judges"]
    require([c[k] for k in ("paired","old_net","qwen_net","same_win")], [12,7,4,4], "Two-judge sycophancy")
    c = cj["beneficial_memory_usage"]["both_judges"]
    require([c["conservative_low"],c["conservative_high"]], [-7,4], "Two-judge utility bound")
    require("seven roots under GPT-4.1 and four under Qwen" in paper, True, "Two-judge manuscript claim")
    fresh = json.loads((root / "persist_utility_fresh_deployment_v1/SUMMARY.json").read_text())
    require(fresh["assigned"], 18, "Fresh utility assignments")
    require([fresh["delivered"][a] for a in ("SELECTED","FULL","RUBRIC")], [18,18,17], "New deliveries")
    for judge, want in (("GPT",[18,18,17]), ("Qwen",[14,18,14])):
        require([fresh["tables"][judge][a]["pass"] for a in ("SELECTED","FULL","RUBRIC")], want, judge + " fresh strict passes")
    require(fresh["pairs"]["Qwen"]["SELECTED vs FULL"]["high"], -3, "Fresh utility best-case net")
    require("lost at least three strict utility passes" in paper, True, "New utility interpretation")
    direct = json.loads((root / "persist_query_rubric_pair_v1/SUMMARY.json").read_text())
    paired = direct["comparisons"]["beneficial_memory_usage"]["Qwen"]
    require([paired[k] for k in ("win","loss","tie","unknown")], [2,1,13,2], "Author defense utility pairs")
    require(direct["either_grader_bounds"]["beneficial_memory_usage"], {"low":-1,"high":4}, "Utility judge sensitivity")
    partition = json.loads((root / "persist_query_rubric_pair_v1/PARTITION.json").read_text())
    require(sum(row.get("tie",0) for row in partition.values()), 10, "Partition paired ties")
    require("ten of 11 common roots tied" in paper, True, "Partition manuscript claim")
    binary = json.loads((root / "persist_query_binary_replay_v1/SUMMARY.json").read_text())
    utility = binary["beneficial_memory_usage"]["outcomes"]
    totals = utility["QUERY_BINARY"]
    expected = f"{totals['pass']} passes, {totals['fail']} failures and {totals['unknown']} missing"
    require(expected in paper, True, "Query-only switch utility")
    bound = totals["pass"] + totals["unknown"]
    require(f"at most {bound} passes against {utility['FULL']['pass']} observed" in paper, True, "Utility bound")
    diagnostic = json.loads((root / "rpe_indexed_grade_pair_v1/SUMMARY.json").read_text())
    scopes = ("all_A", "contains_B", "contains_C", "all")
    expected = []
    for scope in scopes:
        cells = diagnostic["tables"][scope]
        expected.append([f"{cells[a]['match']}/{cells[a]['positions']}" for a in ("archive","original","indexed")])
    require([r[1:] for r in latex_rows(paper,"grade_index")], expected, "Score presentation table")
    flips = diagnostic["directions"]["all"]
    require(f"on {flips['original_indexed_down']} tasks, raised it on none and left {flips['original_indexed_tie']} unchanged" in paper and not flips.get("original_indexed_up"), True, "Index direction")
    rep = json.loads((root / "bench_header_repeat_v1/SUMMARY.json").read_text())["stats"]
    before, after = (rep["completeness"][key] for key in ("original_net_edit","replicate_net_edit"))
    require(f"from ${before}$ to ${after:+}$ total points" in paper, True, "Completeness replication")
    agreement = json.loads((root / "persist_released_grade_agreement_v1/ORDINAL.json").read_text())
    for row in agreement:
        counts = row["counts"]
        n = sum(cell["n"] for cell in counts)
        passes = {}
        for side in ("released", "project"):
            passes[side] = sum(cell["n"] for cell in counts if (
                cell[side] == 3 if row["category"] == "beneficial_memory_usage" else cell[side] < 3))
        for value in passes.values():
            require(f"{value}/{n}" in paper.split("To test whether the project grader")[1].split("\\section")[0],
                    True, f"Released answer bridge {row['category']}")
    fresh_dir = root / "rpe_ipe_fresh_repeat_v1"
    fresh = json.loads((fresh_dir / "VERIFICATION.json").read_text())["deployments"]
    for dep in fresh:
        methods = dep["all_complete"]["methods"]
        values = [methods[m]["match"] for m in ("IPE_C", "TASK_ONLY", "RP_FULL")]
        phrase = f"{values[0]}, {values[1]} and {values[2]} out of {methods['IPE_C']['positions']}"
        require(phrase in paper, True, f"Fresh IPE-C deployment {dep['deployment']}")
    utility = json.loads((root / "persist_memadapter_release_v1/UTILITY.json").read_text())
    require(utility["allocated"], 20, "Strict utility allocation")
    names = {"MemAdapter": "MEMADAPTER", "SELECTED": "SELECTED", "Query breadth": "BREADTH"}
    rows = list(latex_rows(paper, "utilityrelease"))
    require([r[0] for r in rows], list(names), "Utility methods")
    for method, delivered, gpt, qwen in rows:
        arm = utility["methods"][names[method]]
        require(int(delivered), arm["delivered"], f"{method} delivered")
        for j, text in (("GPT", gpt), ("Qwen", qwen)):
            require(text, f"{arm[j+'_pass']}/{utility['allocated']-arm[j+'_missing']}", f"{method} {j}")
    composition = json.loads((root / "rpe_ipe_des2gen_composition_v1/RESULTS.json").read_text())["common"]["overall"]
    switch = json.loads((root / "rpe_ipe_des2gen_composition_v1/AGREEMENT.json").read_text())["history_on"]["switch"]
    oracle = json.loads((root / "persist_exposure_fr3_v1/ENDPOINT_ORACLE.json").read_text())
    joint = json.loads((root / "bench_joint_delivery_v1/RESULTS.json").read_text())["5"]
    c = joint["counts"]
    ruled_out = sum(row["strict_win_ruled_out"] for key, row in oracle.items() if key.endswith("/both"))
    repeats = json.loads((root / "bench_enrollment_repeat_v1/RESULTS.json").read_text())["fresh"]
    paired = [f"{r['original']}/{r['corrected']}" for r in repeats]
    phrases = [
        f"original/corrected pairs of {paired[0]}, {paired[1]} and {paired[2]}",
        f"{composition['tasks']} tasks with comparable Des2Gen and IPE-C records ({composition['positions']:,} positions)",
        f"scored {composition['IPE_Match']}, {composition['DES_Match']} and {composition['COMPOSED_Match']} matches",
        f"{switch['tasks']} affected tasks, Match declined from {switch['IPE_Match']} to {switch['Des2Gen_Match']} of {switch['positions']}",
        f"decreased from {switch['IPE_UPB']} to {switch['Des2Gen_UPB']} while overuse increased from {switch['IPE_OPB']} to {switch['Des2Gen_OPB']}",
        f"ruled out this pattern on {ruled_out} sources",
        f"{c['T_passes']}, {c['H_passes']} and {c['G_passes']} of these {c['comparable']}",
    ]
    gate = {r[3]: r for r in markdown_rows((root / "rpe_deployable_history_gate_v1/RESULTS.md").read_text()) if r[0] == "all"}
    oracle, = [r for r in markdown_rows((root / "ipe_endpoint_behavior_gpt41_v1/QUERY_ORACLE.md").read_text()) if r[0] == "All"]
    correction = (root / "rpe_soft_endpoint_opportunity_v1/RESULTS.md").read_text()
    soft, = [r for r in markdown_rows(correction) if r[0] == "memory"]
    phrases.extend([
        f"{gate['query'][5]}, {gate['memory'][5]}, {gate['IPE-C'][5]} and {gate['full'][5]} of {gate['full'][2]} positions",
        f"underuse severity from {gate['query'][7]} to {gate['memory'][7]}",
        f"overuse severity from {gate['query'][6]} to {gate['memory'][6]}",
        f"obtains {oracle[8]}/{int(oracle[2]):,} Match, compared with {oracle[7]}/{int(oracle[2]):,} for IPE-C",
        f"In {oracle[4]} groups the preferred endpoint reverses",
        f"all four policies scored {soft[1]} on it",
    ])
    reopening = {r[0]: r for r in markdown_rows((root / "query_specific_reopening_v1/RESULTS.md").read_text())}
    base, candidate = reopening["IPE-C"], reopening["Across queries"]
    original_match, positions = base[6].split("/")
    phrases.extend([
        f"reduced Match from {original_match} to {candidate[6].split('/')[0]} of {int(positions):,}",
        f"Underuse severity fell from {base[8]} to {candidate[8]} while overuse rose from {base[7]} to {candidate[7]}",
    ])
    diagnostic = (root / "spanish_app_joint_diagnostic_v1/RESULTS.md").read_text()
    saved = re.search(r"full endpoints: ([^.]*)", diagnostic).group(1).split(", ")
    joint_score = re.search(r"M1\+M3 wire scored (\d+/\d+)", diagnostic).group(1)
    phrases.extend([", ".join(saved[:-1]) + " and " + saved[-1], f"recognized both behaviors yet gave {joint_score}"])
    replay = list(markdown_rows((root / "persist_routed_revision_replay_v1/RESULTS.md").read_text()))[2:]
    utility = {"3776469a", "7b03625e", "eccea61e", "ef273934"}
    require({r[0] for r in replay}, utility | {"0029f020", "a47fceb8"}, "six revision sources")
    columns = {"Original": 4, "Review all": 5, "Routed review": 6, "Routed direct": 8}
    revision = list(latex_rows(paper, "routedrevision"))
    require([r[0] for r in revision], list(columns), "revision arms")
    for name, gpt, qwen, risk in revision:
        col = columns[name]
        def fraction(is_utility, judge):
            values = [int(r[col].split("/")[judge]) for r in replay if (r[0] in utility) == is_utility]
            good = sum(v == 3 if is_utility else v < 3 for v in values)
            return f"{good}/{len(values)}"
        require([gpt, qwen, risk], [fraction(True, 0), fraction(True, 1),
                " / ".join(fraction(False, j) for j in (0, 1))], name)
    external_text = (root / "bench_profile_external_stability_v1/RESULTS.md").read_text()
    source_rows = list(markdown_rows(external_text.split("## Pairwise eligible")[0]))[2:]
    aliases = {"Strong Gate": "GEPA_SELECTED_BOUNDS", "Des2Gen": "DES2GEN_FULL",
               "MemAdapter": "MEMADAPTER_FULL", "Selectivity": "PAPER_SELECTIVITY",
               "RP reconstructed": "RPR_PAPER_FULL"}
    by_method = {r[0]: r[1:] for r in source_rows}
    joint_rows = list(latex_rows(paper, "benchjoint"))
    require({r[0] for r in joint_rows}, set(aliases), "joint delivery methods")
    for name, *numbers in joint_rows:
        a, m, c, j = by_method[aliases[name]]
        require(numbers, [f.split("/")[0] for f in (a,m,c,j)], name+" joint panel")
        require([f.split("/")[1] for f in (a,m,c,j)], ["63","122","37","37"], "common panel denominators")
    common_text = external_text.split("## Common five-method panel")[1]
    selectivity = next(r for r in markdown_rows(common_text) if r[0]=="PAPER_SELECTIVITY")
    low, high = selectivity[-1].replace("+","").split(" to ")
    hybrid = (root / "bench_joint_nonbold_judge_swap_v1/RESULTS.md").read_text()
    sample = next(r for r in markdown_rows(hybrid) if r[0]=="All complete")
    g0,g1 = sample[4].split("/")
    s0,s1 = sample[5].split("/")
    limit = re.search(r"all (\d+) assigned draws: \[\+(\d+), \+(\d+)\]",hybrid)
    phrases.extend([f"between {low} and {high} percentage points",
                    f"On {sample[1]} paired draws", f"from {g0} to {g1} for Gate and from {s0} to {s1} for Selectivity",
                    f"Across all {limit[1]} assigned pairs", f"by {limit[2]} to {limit[3]} joint passes"])
    residual = list(markdown_rows((root / "rpe_endpoint_residual_v1/RESULTS.md").read_text()))
    c_row = next(r for r in residual if r[0] == "contains C")
    bounds = list(markdown_rows((root / "rpe_endpoint_residual_v1/ATTRIBUTION.md").read_text()))
    a_bound = next(r for r in bounds if r[:3] == ["all", "better saved score", "A"])
    openings = list(markdown_rows((root / "rpe_neighbor_teacher_v1/EQUAL_OPENINGS.md").read_text()))
    equal = next(r for r in openings if r[:2] == ["72", "IPE-C"])
    neighbor = next(r for r in openings if r[:2] == ["72", "neighbor"])
    notes = json.loads((root / "rpe_exact_policy_delivery_v1/behavior_annotations.json").read_text())
    from collections import Counter
    require(Counter(n["status"] for n in notes), {"IMPLEMENTED":9, "WEAKENED":1, "CONFLICT":1, "RISK":2},
            "exact-policy reading")
    phrases.extend([f"{c_row[1]} C-bearing tasks, {int(c_row[5])+int(c_row[6])} remain",
                    f"{c_row[9]} mismatches forces at least {a_bound[4].split('–')[0]}",
                    f"author-A positions across {a_bound[5]} tasks",
                    f"opens {neighbor[0]} histories and scores {int(float(neighbor[2]))}/1,142",
                    f"an expected {equal[2]} matches",
                    "nine recommendations implement that preference, one weakens it, one conflicts",
                    "two leave an unresolved risk"])
    attainment = json.loads((root / "rpe_task_attainment_v1/RESULTS.json").read_text())
    def counts(panel, threshold, denominator=False):
        row = attainment[panel]["at_least"][threshold]
        suffix = f"/{attainment[panel]['tasks']}" if denominator else ""
        return [f"{row[key]}{suffix}" for key in ("IPE_C", "TASK_ONLY", "RPR_PAPER_FULL")]

    a, b, c = counts("common", "1/2", True)
    phrases.append(f"{a} tasks with IPE-C, {b} with empty history and {c} with full RP")
    for panel, threshold, ending in (("common", "3/4", "."), ("no_known_flags", "1/2", " at half"),
                                     ("no_known_flags", "3/4", " at three quarters")):
        a, b, c = counts(panel, threshold)
        phrases.append(f"{a}, {b} and {c}{ending}")
    default_probe = root / "decision_default_support_v1"
    generated = json.loads((default_probe / "AGGREGATE.json").read_text())["totals"]
    archived = json.loads((default_probe / "ENDPOINT_AUDIT.json").read_text())
    archived_totals = archived["totals"]
    observed = [generated[k]["primary"] for k in ("ARCHIVE", "DIRECT", "SUPPORTED_DEFAULT")]
    phrases.append(f"scored {observed[0]}, {observed[1]}, and {observed[2]} of "
                   f"{generated['ARCHIVE']['positions']} positions")
    a, b = (next(r for r in archived["rows"] if r["case"] == case)["scores"]
            for case in ("implicit/094", "implicit/142"))

    def position_score(row, method):
        return f"{row[method]['primary']}/{row[method]['positions']}"

    phrases.append(f"{position_score(a, 'TASK_ONLY')} and {position_score(b, 'TASK_ONLY')}, "
                   f"versus {position_score(a, 'IPE_C')} and {position_score(b, 'IPE_C')} with IPE-C")
    phrases.append(f"changes Match from {position_score(archived_totals, 'IPE_C')} to "
                   f"{position_score(archived_totals, 'TASK_ONLY')} and increases underuse severity "
                   f"from {archived_totals['IPE_C']['UPB']} to {archived_totals['TASK_ONLY']['UPB']}")
    figure_report = root / "rpeval_figure14_judge_v1"
    initial = json.loads((figure_report / "RAW_AGGREGATE.json").read_text())
    syntax_checked = json.loads((figure_report / "SYNTAX_DIAGNOSTIC.json").read_text())
    format_checked = json.loads((figure_report / "FORMAT_CONTROL.json").read_text())
    figure_order = ("IPE_C", "RPR_PAPER_FULL", "TASK_ONLY")
    before = [format_checked["common"][method]["adapted_match"] for method in figure_order]
    after = [format_checked["common"][method]["figure_match"] for method in figure_order]
    traces = json.loads((root / "rpeval_figure_behavior_audit_v1" / "AGGREGATE.json").read_text())["behavior_counts"]
    zero, full = (traces["all_A/" + method] for method in ("TASK_ONLY", "RPR_PAPER_FULL"))
    phrases.extend([
        f"invalid JSON on all {initial['contracts']['INVALID_JSON']} calls",
        f"leaves {syntax_checked['contracts']['OK']} valid cells",
        f"yields {format_checked['contracts']['OK']} valid cells",
        f"from {before[0]}, {before[1]}, and {before[2]} to {after[0]}, {after[1]}, and {after[2]} of "
        f"{format_checked['common']['IPE_C']['positions']} positions",
        f"{zero['A/SOFT']} of {sum(zero.values())} author-A positions in these task-only answers, "
        f"compared with {full['A/SOFT']} of {sum(full.values())} with full history",
    ])
    for phrase in phrases:
        require(phrase in paper, True, phrase)
    return 60 + len(joint_rows) + len(revision) + len(checked) + len(phrases) + sum(map(len, (seen_strata, seen_external, seen_tracks, seen_risk_tracks, seen_metrics)))


if __name__ == "__main__":
    print(f"Verified {check()} manuscript comparisons against the public evidence")
