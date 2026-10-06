"""Offline import: python -m app.import_research PATH.zip --name 'Research archive'."""
import argparse
import json

from .database import initialize_database, SessionLocal
from .research import read_archive, save_import


def main():
    parser = argparse.ArgumentParser(description="Import archived result CSVs without executing code or calling models")
    parser.add_argument("archive")
    parser.add_argument("--name", default="Research archive")
    args = parser.parse_args()
    payload = read_archive(args.archive, args.name)
    initialize_database()
    with SessionLocal() as session:
        identity = save_import(session, payload)
    print(json.dumps({"id": identity, "runs": payload["run_count"], "observations": payload["observation_count"]}))


if __name__ == "__main__":
    main()
