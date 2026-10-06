import json
import zipfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.answer_audit import inspect_answer, parse_answers
from app.database import Base, ResearchImport
from app.research import read_archive, save_import


def test_incidental_number_is_flagged_without_changing_recorded_score():
    audit = inspect_answer('The server returns HTTP 400. Inspect another_function.', {"functions": ["handle_request"], "line": 400}, True)
    assert audit["recorded"] is True
    assert audit["legacy_replay"] is True
    assert audit["explicit_line_hit"] is False
    assert audit["flags"] == ["unanchored_line_number"]


@pytest.mark.parametrize("answer", ['The fault is on line 400.', 'Line number: 400.', 'lineno=400'])
def test_explicit_line_references_are_recognized(answer):
    audit = inspect_answer(answer, {"functions": [], "line": 400}, True)
    assert audit["explicit_line_hit"] is True
    assert audit["flags"] == []


def test_function_boundaries_do_not_match_substrings():
    audit = inspect_answer('check_handle_request_suffix is faulty.', {"functions": ["handle_request"], "line": 400}, False)
    assert audit["matched_functions"] == []
    assert audit["legacy_replay"] is False
    assert inspect_answer('handle_request is faulty.', {"functions": ["handle_request"], "line": 400}, True)["matched_functions"] == ["handle_request"]


def test_disagreement_is_separate_from_original_outcome():
    audit = inspect_answer('Another function is faulty.', {"functions": ["handle_request"], "line": 400}, True)
    assert audit["recorded"] is True
    assert audit["legacy_replay"] is False
    assert 'recorded_replay_disagreement' in audit["flags"]


def test_missing_truth_is_not_a_miss_and_credentials_are_redacted():
    audit = inspect_answer('token sk-' + 'x' * 30, {"functions": [], "line": None}, None)
    assert audit["legacy_replay"] is None
    assert 'sk-' not in audit["answer"]
    assert len(audit["answer_sha256"]) == 64


def test_duplicate_case_keys_cannot_be_joined():
    record = {"project": "example", "bug_id": 1, "gt_functions": ["calculate"], "gt_line": 20, "single_answer": "calculate", "chain_answer": "line 20"}
    data = ('\n'.join([json.dumps(record)] * 2)).encode()
    with pytest.raises(ValueError, match='duplicate'):
        parse_answers(data)


def test_run_matching_does_not_mix_passes_and_truth_conflicts_are_flagged(tmp_path):
    path = tmp_path / 'study.zip'
    raw = {"project": "example", "bug_id": 1, "gt_functions": ["calculate"], "gt_line": 20, "single_answer": "calculate", "chain_answer": "line 20"}
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('results_run1.csv', 'project,bug_id,gt_function,gt_line,single_localized,chain_localized\nexample,1,other,21,True,True\n')
        z.writestr('results_run2.csv', 'project,bug_id,gt_function,gt_line,single_localized,chain_localized\nexample,1,calculate,20,False,False\n')
        z.writestr('raw_answers_run1.jsonl', json.dumps(raw))
    report = read_archive(path)
    first, second = report['runs']
    assert first['rows'][0]['audit']['flags'] == ['csv_raw_ground_truth_disagreement']
    assert second['rows'][0]['audit'] is None
    assert second['rows'][0]['single'] is False
    assert report['audit_summary']['linked_cases'] == 1


def test_version_one_import_upgrades_idempotently(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'upgrade.db').as_posix()}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(ResearchImport(id='hash', name='Study', created_at='2026-01-01', payload={"runs": []}))
        session.commit()
        payload = {"id": 'hash', "name": 'Study', "imported_at": '2026-02-01', "importer_version": '2.0.0', "runs": [{"rows": [{"single": True}]}]}
        save_import(session, payload)
        assert session.get(ResearchImport, 'hash').payload == payload
        save_import(session, payload)
        assert session.get(ResearchImport, 'hash').created_at == '2026-01-01'
    engine.dispose()


def test_duplicate_csv_case_identities_do_not_share_one_answer(tmp_path):
    path = tmp_path / 'ambiguous.zip'
    raw = {"project": "example", "bug_id": 1, "gt_functions": ["calculate"], "gt_line": 20, "single_answer": "calculate", "chain_answer": "line 20"}
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('results_run1.csv', 'project,bug_id,operator,single,chain\nexample,1,AOR,True,True\nexample,1,ROR,False,False\n')
        z.writestr('raw_answers_run1.jsonl', json.dumps(raw))
    report = read_archive(path)
    assert all(row['audit'] is None for row in report['runs'][0]['rows'])
    assert all(row['audit_status'] == 'ambiguous_case_identity' for row in report['runs'][0]['rows'])
