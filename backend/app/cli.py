import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.database import SessionLocal
from app.importers.twd import extract_twd_file
from app.services.mapping_import import import_mapping_workbook
from app.services.twd_import import import_twd_file


def main() -> None:
    parser = argparse.ArgumentParser(prog="mtpulse")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect-twd")
    inspect_parser.add_argument("path", type=Path)
    import_parser = commands.add_parser("import-twd")
    import_parser.add_argument("path", type=Path)
    mapping_parser = commands.add_parser("import-mappings")
    mapping_parser.add_argument("path", type=Path)
    mapping_parser.add_argument("--effective-from", required=True, type=date.fromisoformat)
    mapping_parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.command == "inspect-twd":
        extract = extract_twd_file(args.path)
        result = {
            "data_date": extract.data_date.isoformat(),
            "checksum_sha256": extract.checksum_sha256,
            "calculated": asdict(extract.summary),
            "source_reported": asdict(extract.reported_summary),
            "reconciliation_errors": extract.reconciliation_errors,
        }
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        return
    with SessionLocal() as session:
        if args.command == "import-mappings":
            report = import_mapping_workbook(
                session,
                args.path,
                args.effective_from,
                apply=args.apply,
            )
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
            return
        batch = import_twd_file(session, args.path)
        print(json.dumps({"batch_id": batch.id, "status": batch.status}, ensure_ascii=False))


if __name__ == "__main__":
    main()
