"""Commands for the additional comparison; never resumes historical training."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import time

import numpy as np
import pandas as pd

from src.baselines import baseline_scores
from src.config import BASELINE_ORDER
from src.dataset import load_partitions, validate_split_manifest
from src.gep import pack_by_scores, pack_gene
from .core import (FEATURES, MODEL_IDS, TEST_PARTITIONS, assert_separation, best_label,
                   grouped_bootstrap, instance_features, predict_r)
from .provenance import ROOT, local_path, sha256, verify_inherited, verify_v2

PACKAGE = ROOT / "revision_comparison"
RESULTS = PACKAGE / "results"
LOCK = PACKAGE / "frozen_protocol.json"


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def save_csv(frame, path):
    compression = {"method": "gzip", "mtime": 0} if str(path).endswith(".gz") else None
    frame.to_csv(path, index=False, compression=compression, float_format="%.17g")


def runtime_environment():
    pins = dict(line.strip().split("==") for line in (ROOT / "requirements.txt").read_text().splitlines() if line.strip())
    actual = {name: importlib.metadata.version(name) for name in pins}
    if pins != actual:
        raise RuntimeError(f"Pinned dependencies differ: {actual}")
    r = subprocess.check_output(["Rscript", "--vanilla", "-e",
        'cat(R.version.string,"\\nclass:",as.character(packageVersion("class")),"\\n")'], text=True).strip()
    return {"python": platform.python_version(), "packages": actual, "r": r,
            "platform": platform.platform(), "machine": platform.machine(),
            "tectonic": subprocess.check_output(["tectonic", "--version"], text=True).strip()}


def features_frame(cases):
    return pd.DataFrame([dict(name=i.name, partition=i.partition, group_id=i.group_id,
                              **instance_features(i)) for i in cases]).sort_values("name", kind="stable").reset_index(drop=True)


def outcome(instance, method, solution):
    selected = np.asarray(solution.selected)
    assert selected.dtype == bool and selected.shape == (instance.n,)
    assert solution.total_profit == sum(int(p) for p in instance.profits[selected])
    assert solution.total_weight == sum(int(w) for w in instance.weights[selected])
    feasible = 0 <= solution.total_weight <= instance.capacity
    bounded = 0 <= solution.total_profit <= instance.optimum
    assert feasible and bounded and instance.optimum > 0
    return dict(name=instance.name, partition=instance.partition, group_id=instance.group_id,
                method=method, profit=solution.total_profit, packed_weight=solution.total_weight,
                capacity=instance.capacity, optimum=instance.optimum,
                gap_ppm=1e6 * (instance.optimum - solution.total_profit) / instance.optimum,
                exact=solution.total_profit == instance.optimum, feasible=feasible,
                optimum_bound_ok=bounded, selected_items=int(selected.sum()))


def prepare():
    if LOCK.exists() or (RESULTS / "development_features_labels.csv").exists():
        raise FileExistsError("Development artifacts already exist; preserve the frozen study")
    verify_inherited()
    RESULTS.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    cases = load_partitions(ROOT / "results/split_manifest_v2.csv", ["train", "validation"])
    assert len(cases) == 1383 and len({i.group_id for i in cases}) == 461
    feature = features_frame(cases)
    rows, labels = [], []
    for case in cases:
        profits = {}
        for method, scores in baseline_scores(case).items():
            solution = pack_by_scores(case, scores, method)
            rows.append(outcome(case, method, solution))
            profits[method] = solution.total_profit
        label, ties = best_label(profits)
        labels.append({"name": case.name, "label": label, "label_ties": ties,
                       "label_tie_count": len(ties.split("|"))})
    feature = feature.merge(pd.DataFrame(labels), on="name", validate="one_to_one").sort_values("name")
    save_csv(feature, RESULTS / "development_features_labels.csv")
    save_csv(pd.DataFrame(rows), RESULTS / "development_rule_outcomes.csv.gz")
    write_json(RESULTS / "development_metadata.json", {
        "instances": len(cases), "groups": 461, "elapsed_seconds": time.perf_counter() - start,
        "label_counts": feature.label.value_counts().reindex(BASELINE_ORDER, fill_value=0).to_dict(),
        "equal_profit_label_cases": int((feature.label_tie_count > 1).sum()),
        "undefined_correlation_cases": int(feature.correlation_undefined.sum()),
        "data_access": "Only train and validation instance contents were loaded"})
    print("Prepared 1383 development cases; no test evaluation performed.")


def freeze():
    if LOCK.exists():
        raise FileExistsError("The revision protocol is already frozen")
    inherited = verify_inherited()
    environment = runtime_environment()
    write_json(PACKAGE / "environment.json", environment)
    source_paths = sorted(PACKAGE.glob("*.py")) + sorted((PACKAGE / "tests").glob("*.py"))
    source_paths += [PACKAGE / "predict.R", PACKAGE / "protocol.json", PACKAGE / "environment.json"]
    source_paths += [ROOT / "src" / name for name in ("baselines.py", "dataset.py", "gep.py")]
    inputs = ["data/knapsack.zip", "results/split_manifest_v2.csv", "results/models_v2.csv.gz",
              "results/representative_expressions_v2.csv", "results/confirmatory/evaluations_jooken_v2.csv.gz",
              "revision_comparison/results/development_features_labels.csv",
              "revision_comparison/results/development_rule_outcomes.csv.gz",
              "revision_comparison/results/development_metadata.json"]
    selected = pd.read_csv(ROOT / "results/representative_expressions_v2.csv")
    assert selected.model_id.tolist() == MODEL_IDS
    models = pd.read_csv(ROOT / "results/models_v2.csv.gz").set_index("model_id")
    for row in selected.itertuples():
        assert row.gene == models.loc[row.model_id, "gene"]
    record = {"frozen_utc": datetime.now(timezone.utc).isoformat(), "inherited_verification": inherited,
              "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in source_paths},
              "input_sha256": {p: sha256(local_path(p)) for p in inputs},
              "models": selected[["model_id", "arm", "gene", "run"]].to_dict("records"),
              "protocol": json.loads((PACKAGE / "protocol.json").read_text())}
    write_json(LOCK, record)
    print(f"Frozen before test evaluation: {sha256(LOCK)}")


def verify_frozen():
    record = json.loads(LOCK.read_text())
    verify_inherited()
    for field in ("source_sha256", "input_sha256"):
        for relative, expected in record[field].items():
            if sha256(local_path(relative)) != expected:
                raise RuntimeError(f"Frozen {field} mismatch: {relative}")
    recorded = json.loads((PACKAGE / "environment.json").read_text())
    current = runtime_environment()
    for field in ("packages", "r"):
        if current[field] != recorded[field]:
            raise RuntimeError(f"Frozen runtime differs: {field}")
    return record


def replay_original(outcomes, destination):
    columns = ["model_id", "name", "checkpoint", "permutation_index", "profit", "packed_weight", "optimum", "gap_ppm"]
    records = []
    wanted = set(MODEL_IDS) | set(BASELINE_ORDER)
    names = set(outcomes.name)
    path = ROOT / "results/confirmatory/evaluations_jooken_v2.csv.gz"
    for chunk in pd.read_csv(path, usecols=columns, chunksize=200_000):
        rows = chunk[chunk.model_id.isin(wanted) & chunk.name.isin(names) &
                     chunk.permutation_index.eq(0) &
                     (chunk.checkpoint.eq(65536) | chunk.model_id.isin(BASELINE_ORDER))]
        if len(rows):
            records.append(rows)
    original = pd.concat(records).rename(columns={"model_id": "method"})
    new = outcomes[outcomes.method.ne("kNN")]
    joined = new.merge(original, on=["name", "method"], suffixes=("_new", "_original"), validate="one_to_one")
    assert len(joined) == len(new) == 1594 * 8
    for column in ("profit", "packed_weight", "optimum"):
        assert joined[f"{column}_new"].equals(joined[f"{column}_original"]), column
    error = np.abs(joined.gap_ppm_new - joined.gap_ppm_original)
    assert error.max() < 1e-7
    report = {"pairs": len(joined), "all_integer_profits_weights_optima_equal": True,
              "max_gap_rounding_difference_ppm": float(error.max()),
              "original_file_sha256": sha256(path)}
    write_json(destination / "original_replay_verification.json", report)
    return report


def summaries(outcomes):
    frames = [outcomes, outcomes[outcomes.partition.ne("id_test")].assign(partition="ood_all")]
    frame = pd.concat(frames)
    return frame.groupby(["partition", "method"], sort=True).agg(
        instances=("name", "size"), groups=("group_id", "nunique"),
        mean_gap_ppm=("gap_ppm", "mean"), median_gap_ppm=("gap_ppm", "median"),
        exact_fraction=("exact", "mean"), all_feasible=("feasible", "all")).reset_index()


def run(destination):
    lock = verify_frozen()
    destination = local_path(destination)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation: {destination}")
    destination.mkdir(parents=True)
    start = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    train = pd.read_csv(RESULTS / "development_features_labels.csv")
    cases = load_partitions(ROOT / "results/split_manifest_v2.csv", TEST_PARTITIONS)
    assert pd.Series([i.partition for i in cases]).value_counts().to_dict() == lock["protocol"]["test_counts"]
    features = features_frame(cases)
    assert_separation(train, features)
    save_csv(features, destination / "test_features.csv")
    feature_seconds = time.perf_counter() - start
    predictions = predict_r(RESULTS / "development_features_labels.csv", destination / "test_features.csv",
                            destination / "predictions.csv", destination / "r_session.txt")
    repeat = predict_r(RESULTS / "development_features_labels.csv", destination / "test_features.csv",
                      destination / "predictions_repeat.csv", destination / "r_session_repeat.txt")
    pd.testing.assert_frame_equal(predictions, repeat)
    assert predictions.name.tolist() == features.name.tolist()
    predicted = predictions.set_index("name").prediction.to_dict()
    prediction_seconds = time.perf_counter() - start - feature_seconds
    rows, timings = [], []
    for case in cases:
        solutions = {}
        for method, scores in baseline_scores(case).items():
            stamp = time.perf_counter()
            solution = pack_by_scores(case, scores, method)
            timings.append({"name": case.name, "method": method, "decode_seconds": time.perf_counter() - stamp})
            solutions[method] = solution
            rows.append(outcome(case, method, solution))
        for model in lock["models"]:
            stamp = time.perf_counter()
            solution = pack_gene(case, model["gene"], model["arm"])
            timings.append({"name": case.name, "method": model["model_id"], "decode_seconds": time.perf_counter() - stamp})
            rows.append(outcome(case, model["model_id"], solution))
        rows.append(outcome(case, "kNN", solutions[predicted[case.name]]))
    frame = pd.DataFrame(rows)
    save_csv(frame, destination / "outcomes.csv.gz")
    save_csv(pd.DataFrame(timings), destination / "decode_timings.csv.gz")
    save_csv(frame[["name", "method", "feasible", "optimum_bound_ok", "packed_weight", "capacity", "profit", "optimum"]],
             destination / "feasibility_checks.csv.gz")
    save_csv(summaries(frame), destination / "summary.csv")
    contrasts, bootstrap, group = grouped_bootstrap(frame)
    save_csv(contrasts, destination / "id_contrasts.csv")
    save_csv(bootstrap, destination / "bootstrap_replicates.csv.gz")
    save_csv(group.reset_index(), destination / "id_group_differences.csv")
    evaluation_seconds = time.perf_counter() - start
    replay = replay_original(frame, destination)
    write_json(destination / "timing_metadata.json", {
        "started_utc": started_utc, "feature_loading_seconds": feature_seconds,
        "r_prediction_and_reproducibility_seconds": prediction_seconds,
        "evaluation_and_bootstrap_seconds": evaluation_seconds, "total_including_replay_seconds": time.perf_counter() - start,
        "knn_decode_note": "kNN reuses the chosen rule's exact packing; its decoding cost is that rule's cost. R timings exclude decoding; Python phase timings include I/O.",
        "decoder_timing_note": "Per-formula timing includes scoring and decoding; fixed-rule timing excludes baseline score-vector construction. Descriptive only; no speed superiority claim.",
        "pid": os.getpid(), "platform": platform.platform()})
    write_json(destination / "run_manifest.json", {
        "frozen_protocol_sha256": sha256(LOCK), "completed_utc": datetime.now(timezone.utc).isoformat(),
        "files": {p.name: sha256(p) for p in sorted(destination.iterdir()) if p.is_file()},
        "outcomes": len(frame), "instances": len(cases), "methods": 9,
        "prediction_reproducible": True, "undefined_test_correlations": int(features.correlation_undefined.sum()),
        "original_replay": replay})
    print(contrasts.to_string(index=False))


def verify_results(destination):
    verify_frozen()
    destination = local_path(destination)
    manifest = json.loads((destination / "run_manifest.json").read_text())
    assert manifest["frozen_protocol_sha256"] == sha256(LOCK)
    for name, expected in manifest["files"].items():
        assert sha256(destination / name) == expected, name
    frame = pd.read_csv(destination / "outcomes.csv.gz")
    assert len(frame) == 1594 * 9 and not frame.duplicated(["name", "method"]).any()
    assert frame.groupby("name").method.nunique().eq(9).all()
    assert frame.feasible.all() and frame.optimum_bound_ok.all()
    assert (frame.profit <= frame.optimum).all() and (frame.packed_weight <= frame.capacity).all()
    reference = pd.read_csv(ROOT / "results/split_manifest_v2.csv")
    wanted = reference[reference.partition.isin(TEST_PARTITIONS)]
    assert set(frame.name) == set(wanted.name)
    actual_cases = frame[["name", "partition", "group_id"]].drop_duplicates().sort_values("name").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual_cases, wanted[["name", "partition", "group_id"]].sort_values("name").reset_index(drop=True))
    validate_split_manifest(reference)
    predictions = pd.read_csv(destination / "predictions.csv").set_index("name")
    packed = frame.set_index(["name", "method"])
    for name, row in predictions.iterrows():
        for col in ("profit", "packed_weight", "gap_ppm"):
            assert packed.loc[(name, "kNN"), col] == packed.loc[(name, row.prediction), col]
    contrasts, _, _ = grouped_bootstrap(frame)
    pd.testing.assert_frame_equal(contrasts, pd.read_csv(destination / "id_contrasts.csv"), check_exact=False, rtol=1e-12)
    pd.testing.assert_frame_equal(summaries(frame), pd.read_csv(destination / "summary.csv"), check_exact=False, rtol=1e-12)
    assert_separation(pd.read_csv(RESULTS / "development_features_labels.csv"), actual_cases)
    print(f"PASS: {len(frame)} outcomes, complete coverage, feasibility, optima, seeded predictions, grouped intervals, original replay, and frozen hashes.")


def table(destination):
    destination = local_path(destination)
    summary = pd.read_csv(destination / "summary.csv").query('partition == "id_test"').set_index("method")
    expression = {
        "GEP-BASE-020": r"$\pdiv(W,P^2-P)+P(O+2W)$",
        "GEP-CAP-008": r"$W-\pdiv(W,(1-P)(K+P))$",
        "GEP-SCALE-042": r"$\pdiv(\pdiv(W,PL)-O,2W-1)$",
        "GEP-FULL-071": r"$\pdiv(1-2\pdiv(K,P),(1-L)(P+T))$",
        "MAXPW": r"$p_i/w_i$", "kNN": "Selected fixed rule"}
    lines = [r"\begin{tabular}{rlr}", r"\toprule", r"\textbf{Rule} & \textbf{Item score} & \textbf{ID ppm} \\", r"\midrule"]
    for method in MODEL_IDS + ["MAXPW", "kNN"]:
        label = method.removeprefix("GEP-")
        lines.append(f"{label} & {expression[method]} & {summary.loc[method, 'mean_gap_ppm']:,.0f}" + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    (PACKAGE / "table_iv.tex").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("command", choices=["prepare", "freeze", "run", "verify", "table", "verify-inherited", "verify-v2"])
    parser.add_argument("--output", default="revision_comparison/results/evaluation")
    parser.add_argument("--v2", type=Path)
    args = parser.parse_args()
    if args.command == "prepare": prepare()
    elif args.command == "freeze": freeze()
    elif args.command == "run": run(args.output)
    elif args.command == "verify": verify_results(args.output)
    elif args.command == "table": table(args.output)
    elif args.command == "verify-inherited": print(json.dumps(verify_inherited(), indent=2))
    elif args.command == "verify-v2":
        if not args.v2: parser.error("--v2 is required for the read-only V2 audit")
        report = verify_v2(args.v2)
        write_json(ROOT / "provenance/v2_fingerprints_after_verification.json", report)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
