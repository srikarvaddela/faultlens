"""Read archived result CSVs as data. Never import or execute archive scripts."""
import csv
from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path, PurePosixPath
import zipfile

from .database import ResearchImport
from .answer_audit import attach_audits
from .leakage import attach_leakage


def boolean(value):
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in ("true", "1", "yes"):
        return True
    if normalized in ("false", "0", "no"):
        return False
    raise ValueError("Invalid archived boolean; refusing to guess")


def summarize_rows(rows):
    paired = [row for row in rows if row["single"] is not None and row["chain"] is not None]
    count = len(paired)
    return {
        "rows": len(rows), "paired": count,
        "single_accuracy": sum(row["single"] for row in paired) / count if count else None,
        "chain_accuracy": sum(row["chain"] for row in paired) / count if count else None,
        "single_only": sum(row["single"] and not row["chain"] for row in paired),
        "chain_only": sum(row["chain"] and not row["single"] for row in paired),
        "leak_known": sum(row["fn_leak"] is not None for row in rows),
    }


def parse_run(name, data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    if len(set(fields)) != len(fields):
        raise ValueError(f"Duplicate CSV columns in {name}")
    single_key = "single_localized" if "single_localized" in fields else "single"
    chain_key = "chain_localized" if "chain_localized" in fields else "chain"
    if not {"project", "bug_id", single_key, chain_key}.issubset(fields):
        raise ValueError(f"Unsupported result schema in {name}")
    rows = []
    for row in reader:
        if None in row:
            raise ValueError(f"Malformed CSV row in {name}")
        if not row.get("project") or not row.get("bug_id"):
            raise ValueError(f"Missing case identity in {name}")
        rows.append({
            "project": row["project"][:100], "bug_id": row["bug_id"][:100],
            "source": row.get("source") or ("real" if row.get("real") == "True" else "unspecified"),
            "operator": (row.get("operator") or "")[:30],
            "single": boolean(row.get(single_key)), "chain": boolean(row.get(chain_key)),
            "fn_leak": boolean(row.get("fn_leak")),
            "real_evidence": boolean(row.get("real_evidence")),
            "chain_step1": boolean(row.get("chain_step1")),
            "chain_step2": boolean(row.get("chain_step2")),
            "chain_step3": boolean(row.get("chain_step3")),
            "ground_truth": {
                "functions": [name for name in (row.get("gt_functions") or row.get("gt_function") or "").split("|") if name],
                "line": int(row["gt_line"]) if row.get("gt_line") else None,
            },
        })
        if len(rows) > 20_000:
            raise ValueError("Run exceeds 20,000 row limit")
    return {
        "filename": name, "sha256": hashlib.sha256(data).hexdigest(), "rows": rows,
        "model_label": "GPT-5 (filename label; snapshot unrecorded)" if name.startswith("results_gpt5") else "Model not recorded in CSV",
        "summary": summarize_rows(rows),
    }


def read_archive(path, name="Research archive"):
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Archive exceeds 64 MB limit")
    archive_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    runs = []
    names = set()
    seen_hashes = {}
    raw_files = {}
    capture_files = {}
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 5000 or sum(entry.file_size for entry in entries) > 128 * 1024 * 1024:
            raise ValueError("Archive exceeds entry or uncompressed size limit")
        for entry in sorted(entries, key=lambda entry: entry.filename):
            filename = PurePosixPath(entry.filename.replace('\\', '/')).name
            if 'real_errors' in PurePosixPath(entry.filename.replace('\\', '/')).parts and filename.endswith('.json'):
                if filename in capture_files or entry.file_size > 256 * 1024:
                    raise ValueError("Ambiguous or oversized capture file")
                capture_files[filename] = archive.read(entry)
                continue
            if filename.startswith("raw_answers_") and filename.endswith(".jsonl"):
                if filename in raw_files or entry.file_size > 8 * 1024 * 1024:
                    raise ValueError("Ambiguous or oversized raw-answer file")
                raw_files[filename] = archive.read(entry)
                continue
            if not filename.startswith("results") or not filename.endswith(".csv"):
                continue
            if filename in names:
                raise ValueError("Ambiguous duplicate result filename")
            names.add(filename)
            if entry.file_size > 4 * 1024 * 1024:
                raise ValueError("Result CSV exceeds 4 MB limit")
            run = parse_run(filename, archive.read(entry))
            run["duplicate_of"] = seen_hashes.get(run["sha256"])
            seen_hashes.setdefault(run["sha256"], filename)
            runs.append(run)
    if not runs:
        raise ValueError("No supported result CSVs found")
    audit_summary = attach_audits(runs, raw_files)
    capture_evidence, leakage_summary = attach_leakage(runs, capture_files)
    return {
        "id": archive_hash, "name": name[:100], "imported_at": datetime.now(timezone.utc).isoformat(),
        "mode": "archived_results", "runs": runs, "run_count": len(runs),
        "observation_count": sum(len(run["rows"]) for run in runs),
        "importer_version": "3.1.0", "audit_summary": audit_summary,
        "capture_evidence": capture_evidence, "leakage_summary": leakage_summary,
        "notes": [
            "Imported recorded outcomes, not new inference or independently rescored answers.",
            "Localization means the archive's function-or-line hit, not coverage Top-1 or MRR.",
            "Missing function-leakage labels remain unknown; they are not clean cases.",
            "Repeated runs and overlapping result files remain separate; no pooled significance claim.",
            "Saved final answers are linked only by exact run filename and case identity; missing answers remain unavailable.",
            "Audit flags are review heuristics, not corrected scores. Capture-derived labels are separate from recorded labels.",
            "Archived captures are not verified as the exact historical prompt inputs; derived strata do not reproduce the original leakage-controlled study.",
        ],
    }


def save_import(session, payload):
    existing = session.get(ResearchImport, payload["id"])
    if existing:
        if existing.payload.get("importer_version") != payload.get("importer_version"):
            # The archive hash is unchanged; retain its separately produced audit.
            upgraded = dict(payload)
            if existing.payload.get('real_validation'):
                upgraded['real_validation'] = existing.payload['real_validation']
            existing.payload = upgraded
            session.commit()
        return existing.id
    session.add(ResearchImport(id=payload["id"], name=payload["name"], created_at=payload["imported_at"], payload=payload))
    session.commit()
    return payload["id"]
