import io
import zipfile

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, ResearchImport
from app.research import read_archive, parse_run, save_import, summarize_rows


def archive(tmp_path, data):
    path = tmp_path / "study.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("study/code/results_run.csv", data)
        z.writestr("study/code/danger.py", "raise RuntimeError('must never execute')")
        z.writestr("study/code/raw_answers.jsonl", '{"secret":"not imported"}')
    return path


def test_import_preserves_unknown_labels_and_recorded_outcomes(tmp_path):
    path = archive(tmp_path, "project,bug_id,single_localized,chain_localized\nexample,1,True,False\nexample,2,False,True\n")
    report = read_archive(path)
    assert report["run_count"] == 1
    assert report["observation_count"] == 2
    run = report["runs"][0]
    assert run["summary"]["single_accuracy"] == 0.5
    assert run["summary"]["chain_accuracy"] == 0.5
    assert run["summary"]["leak_known"] == 0
    assert all(row["fn_leak"] is None for row in run["rows"])
    assert "secret" not in str(report)


def test_missing_outcomes_are_excluded_from_paired_denominator():
    run = parse_run("results.csv", b"project,bug_id,single_localized,chain_localized\nx,1,True,\nx,2,False,True\n")
    assert run["summary"]["rows"] == 2
    assert run["summary"]["paired"] == 1
    assert run["summary"]["single_accuracy"] == 0
    assert run["summary"]["chain_accuracy"] == 1


def test_drift_labels_and_steps_are_preserved():
    run = parse_run("results_drift.csv", b"project,bug_id,single_localized,chain_localized,fn_leak,chain_step1,chain_step2,chain_step3\nx,1,True,False,False,True,False,False\n")
    row = run["rows"][0]
    assert row["fn_leak"] is False
    assert row["chain_step1"] is True
    assert row["chain_step2"] is False


@pytest.mark.parametrize("data", [
    b"project,bug_id,single,chain\nx,1,maybe,True\n",
    b"project,bug_id,single,chain\nx,1,True,False,extra\n",
    b"project,bug_id,single,single,chain\nx,1,True,False,True\n",
])
def test_ambiguous_data_is_rejected(data):
    with pytest.raises(ValueError):
        parse_run("results.csv", data)


def test_import_is_idempotent_and_survives_database_reopen(tmp_path):
    report = read_archive(archive(tmp_path, "project,bug_id,single,chain\nx,1,True,False\n"))
    url = f"sqlite:///{(tmp_path / 'research.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        assert save_import(session, report) == report["id"]
        assert save_import(session, report) == report["id"]
    engine.dispose()
    reopened = create_engine(url)
    with sessionmaker(bind=reopened)() as session:
        imports = session.scalars(select(ResearchImport)).all()
        assert len(imports) == 1
        assert imports[0].payload["runs"][0]["rows"][0]["single"] is True
    reopened.dispose()


def test_identical_files_are_flagged_without_pooling(tmp_path):
    path = tmp_path / "duplicates.zip"
    data = "project,bug_id,single,chain\nx,1,True,False\n"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("results_a.csv", data)
        z.writestr("results_b.csv", data)
    report = read_archive(path)
    assert report["runs"][1]["duplicate_of"] == "results_a.csv"
    assert "single_accuracy" not in report
