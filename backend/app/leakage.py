"""Derived name matches in archived captures, NOT verified historical inputs."""
from collections import Counter
import hashlib
import json
import re

from .answer_audit import SECRET

VERSION = "1.1.0"
RUNNER_UNAVAILABLE = re.compile(r"\b(?:tox|pytest|python(?:\d(?:\.\d+)?)?)\s*:\s*command not found\b|No module named [\"']?(?:pytest|tox)[\"']?(?:\s|$)", re.I)


def parse_captures(files):
    captures = {}
    for filename, data in files.items():
        record = json.loads(data.decode("utf-8-sig"))
        if not isinstance(record, dict) or not isinstance(record.get("project"), str) or "bug_id" not in record:
            raise ValueError("Invalid capture identity")
        key = (record["project"], str(record["bug_id"]))
        if key in captures:
            raise ValueError("Ambiguous duplicate capture identity")
        # Mirror the inspected archive's capture-eligibility rule, explicitly.
        reproduced = record.get("reproduced") if "reproduced" in record else type(record.get("exit")) is int and record["exit"] != 0
        if "reproduced" in record and type(reproduced) is not bool:
            raise ValueError("Capture reproduced flag must be a boolean")
        error, trace = record.get("error_message"), record.get("stack_trace")
        valid_text = isinstance(error, str) and isinstance(trace, str) and bool(error.strip()) and bool(trace.strip())
        evidence = f"{error}\n{trace}" if valid_text else ""
        captures[key] = {
            "id": filename, "filename": filename,
            "capture_sha256": hashlib.sha256(data).hexdigest(),
            "evidence_sha256": hashlib.sha256(evidence.encode()).hexdigest() if valid_text else None,
            "reproduced": reproduced is True, "valid_text": valid_text,
            "placeholder": '<run the failing test' in evidence.lower(),
            "runner_unavailable": bool(RUNNER_UNAVAILABLE.search(evidence)),
            "error_message": SECRET.sub('[REDACTED CREDENTIAL]', error) if isinstance(error, str) else '',
            "stack_trace": SECRET.sub('[REDACTED CREDENTIAL]', trace) if isinstance(trace, str) else '',
            "original_evidence": evidence,
        }
    return captures


def derive(row, capture):
    result = {"version": VERSION, "fn_leak": None, "reason": None, "matches": [], "evidence_id": capture["id"] if capture else None, "historical_input_verified": False}
    reason = (
        'not_real_case' if row.get('source') != 'real' else
        'placeholder_evidence' if row.get('real_evidence') is False else
        'ambiguous_case_identity' if row.get('audit_status') == 'ambiguous_case_identity' else
        'ground_truth_conflict' if row.get('audit') and 'csv_raw_ground_truth_disagreement' in row['audit']['flags'] else
        'missing_capture' if capture is None else
        'capture_not_reproduced' if not capture['reproduced'] else
        'missing_error_or_trace' if not capture['valid_text'] else
        'placeholder_evidence' if capture['placeholder'] else None
    )
    if reason is None and capture['runner_unavailable']:
        reason = 'runner_unavailable'
    functions = [name for name in row.get('ground_truth', {}).get('functions', []) if name and name.lower() != '<module>']
    if reason is None and not functions:
        reason = 'missing_function_ground_truth'
    if reason:
        result['reason'] = reason
        return result
    evidence = capture['original_evidence']
    matches = []
    for name in dict.fromkeys(functions):
        pattern = re.compile(rf'(?<!\w){re.escape(name)}(?!\w)', re.I)
        match = pattern.search(evidence)
        if match:
            start = evidence.rfind('\n', 0, match.start()) + 1
            end = evidence.find('\n', match.end())
            excerpt = evidence[start:end if end != -1 else len(evidence)]
            matches.append({'function': name, 'excerpt': SECRET.sub('[REDACTED CREDENTIAL]', excerpt)[:500]})
    result['matches'] = matches
    result['fn_leak'] = bool(matches)
    result['reason'] = 'function_name_match' if matches else 'no_function_name_match'
    return result


def attach_leakage(runs, capture_files):
    captures = parse_captures(capture_files)
    counts = Counter()
    for run in runs:
        identities = Counter((row['project'], row['bug_id']) for row in run['rows'])
        for row in run['rows']:
            if identities[(row['project'], row['bug_id'])] > 1:
                row['audit_status'] = 'ambiguous_case_identity'
            derived = derive(row, captures.get((row['project'], row['bug_id'])))
            row['derived_leakage'] = derived
            counts['match' if derived['fn_leak'] is True else 'no_match' if derived['fn_leak'] is False else 'unknown'] += 1
        run['derived_strata'] = {key: summarize_stratum(run['rows'], value) for key, value in [('match', True), ('no_match', False), ('unknown', None)]}
    evidence = {capture['id']: {key: value for key, value in capture.items() if key != 'original_evidence'} for capture in captures.values()}
    return evidence, {"version": VERSION, "counts": dict(counts), "historical_input_verified": False}


def summarize_stratum(rows, value):
    selected = [row for row in rows if row['derived_leakage']['fn_leak'] is value]
    paired = [row for row in selected if row['single'] is not None and row['chain'] is not None]
    count = len(paired)
    return {"rows": len(selected), "paired": count, "single_accuracy": sum(row['single'] for row in paired) / count if count else None, "chain_accuracy": sum(row['chain'] for row in paired) / count if count else None}
