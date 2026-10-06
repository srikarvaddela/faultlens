"""Transparent review heuristics; no replacement accuracy metric or inference."""
import hashlib
import json
import re
from collections import Counter

AUDIT_VERSION = "1.0.0"
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})")
LINE_REFERENCE = re.compile(r"\b(?:lines?(?:\s+number)?|lineno)\s*(?:[:#=]\s*)?(\d+)\b", re.I)


def truth(functions, line):
    if not isinstance(functions, list) or any(not isinstance(name, str) for name in functions):
        raise ValueError("Ground-truth functions must be a list of names")
    if line is not None and (type(line) is not int or line <= 0):
        raise ValueError("Ground-truth line must be a positive integer or null")
    return {"functions": functions, "line": line}


def inspect_answer(answer, ground_truth, recorded):
    if not isinstance(answer, str) or len(answer) > 50_000:
        raise ValueError("Invalid or oversized saved answer")
    normalized = answer.lower()
    function_hits = [name for name in ground_truth["functions"] if name and re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", normalized)]
    line = ground_truth["line"]
    line_token_hit = line is not None and bool(re.search(rf"\b{line}\b", normalized))
    explicit_lines = sorted({int(match) for match in LINE_REFERENCE.findall(answer)})
    explicit_line_hit = line is not None and line in explicit_lines
    has_truth = bool(ground_truth["functions"]) or line is not None
    replay = (bool(function_hits) or line_token_hit) if has_truth else None
    flags = []
    if not answer.strip():
        flags.append("empty_saved_answer")
    if line_token_hit and not explicit_line_hit and not function_hits:
        flags.append("unanchored_line_number")
    if recorded is not None and replay is not None and recorded != replay:
        flags.append("recorded_replay_disagreement")
    redacted = SECRET.sub("[REDACTED CREDENTIAL]", answer)
    if redacted != answer:
        flags.append("credential_pattern_redacted")
    return {
        "answer": redacted, "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
        "recorded": recorded, "legacy_replay": replay,
        "matched_functions": function_hits, "line_token_hit": line_token_hit,
        "explicit_line_hit": explicit_line_hit, "explicit_lines": explicit_lines,
        "flags": flags,
    }


def parse_answers(data):
    records = {}
    for text in data.decode("utf-8-sig").splitlines():
        if not text.strip():
            continue
        record = json.loads(text)
        if not isinstance(record, dict) or not isinstance(record.get("project"), str) or "bug_id" not in record:
            raise ValueError("Invalid raw-answer case identity")
        key = (record["project"], str(record["bug_id"]))
        if key in records:
            raise ValueError("Ambiguous duplicate raw-answer case")
        ground_truth = truth(record.get("gt_functions"), record.get("gt_line"))
        for method in ("single", "chain"):
            if not isinstance(record.get(f"{method}_answer"), str):
                raise ValueError("Missing saved answer text")
        records[key] = {"truth": ground_truth, "single": record["single_answer"], "chain": record["chain_answer"]}
        if len(records) > 20_000:
            raise ValueError("Too many saved answers")
    return records


def attach_audits(runs, raw_files):
    linked = reviewed = 0
    for run in runs:
        raw_name = run["filename"].replace("results_", "raw_answers_", 1).removesuffix(".csv") + ".jsonl"
        data = raw_files.get(raw_name)
        records = parse_answers(data) if data is not None else {}
        raw_hash = hashlib.sha256(data).hexdigest() if data is not None else None
        csv_identities = Counter((row["project"], row["bug_id"]) for row in run["rows"])
        for row in run["rows"]:
            record = records.get((row["project"], row["bug_id"]))
            row["audit"] = None
            if csv_identities[(row["project"], row["bug_id"])] > 1:
                row["audit_status"] = "ambiguous_case_identity"
                continue
            if record is None:
                row["audit_status"] = "saved_answer_unavailable"
                continue
            row["audit_status"] = "available"
            raw_truth = record["truth"]
            csv_truth = row["ground_truth"]
            truth_disagreement = (
                csv_truth["line"] is not None and csv_truth["line"] != raw_truth["line"]
                or bool(csv_truth["functions"]) and set(csv_truth["functions"]) != set(raw_truth["functions"])
            )
            answers = {method: inspect_answer(record[method], raw_truth, row[method]) for method in ("single", "chain")}
            flags = ["csv_raw_ground_truth_disagreement"] if truth_disagreement else []
            needs_review = bool(flags or any(answer["flags"] for answer in answers.values()))
            row["audit"] = {
                "version": AUDIT_VERSION, "raw_filename": raw_name, "raw_sha256": raw_hash,
                "ground_truth": raw_truth, "csv_ground_truth": csv_truth,
                "answers": answers, "flags": flags, "needs_review": needs_review,
            }
            linked += 1
            reviewed += needs_review
        run["audit_summary"] = {"linked_cases": sum(row["audit"] is not None for row in run["rows"]), "flagged_cases": sum(bool(row["audit"] and row["audit"]["needs_review"]) for row in run["rows"])}
    return {"version": AUDIT_VERSION, "linked_cases": linked, "flagged_cases": reviewed}
