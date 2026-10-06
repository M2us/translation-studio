"""Command-line interface shared with game build pipelines."""
import argparse
import sys
from pathlib import Path
from . import __version__
from .core import Project, StudioError, read_json, source_revision, json_bytes, asset_candidates, safe_path
from .schemas import export


def main(argv=None):
    parser = argparse.ArgumentParser(description="Translation Studio: validate, hash, export schemas")
    parser.add_argument("--version", action="version", version=f"Translation Studio {__version__}")
    parser.add_argument("--ui-language", choices=["en", "ru"], default="en")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("project")
    validate.add_argument("--language")
    validate.add_argument("--complete", action="store_true")
    validate.add_argument("--media", action="store_true")
    validate.add_argument("--strict-relations", action="store_true")
    hashed = sub.add_parser("source-hash")
    hashed.add_argument("catalog")
    schemas = sub.add_parser("export-schemas")
    schemas.add_argument("directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "source-hash":
            doc = read_json(args.catalog)
            print(source_revision(doc))
            return 0
        if args.command == "export-schemas":
            export(args.directory)
            return 0
        project = Project(args.project)
        if args.language and args.language not in project.config["targetLanguages"]:
            raise StudioError("languages", path=str(project.root))
        issues = project.issues(language=args.language, complete=args.complete)
        for issue in project.relation_issues:
            issue.severity = "error" if args.strict_relations else "warning"
            issues.append(issue)
        if args.media:
            languages = [project.config["sourceLanguage"], args.language] if args.language else [
                project.config["sourceLanguage"], *project.config["targetLanguages"]]
            for tab_id, tab in project.tabs.items():
                if tab_id in project.tab_errors:
                    continue
                if tab["type"] == "text":
                    for entry in project.documents[tab_id]["entries"]:
                        for shot in entry.get("screenshots", []):
                            try:
                                path = safe_path(project.root, shot["path"])
                                with path.open("rb") as stream:
                                    if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                                        raise StudioError("image_error", path=str(path))
                            except OSError:
                                issues.append(StudioError("missing_file", path=shot["path"]).issue)
                            except StudioError as error:
                                issues.append(error.issue)
                    continue
                for entry in project.documents[tab_id]["entries"]:
                    for language in languages:
                        if entry["assets"][language] is None and not args.complete:
                            continue
                        for candidate in asset_candidates(entry["assets"][language]) or [None]:
                            try:
                                path, stale = project.media_side(tab_id, entry["id"], language,
                                                                 candidate.get("id") if candidate else None)
                                if tab["type"] == "audio":
                                    project.audio_queue(tab_id, entry["id"], language)
                                else:
                                    with path.open("rb") as stream:
                                        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                                            raise StudioError("image_error", path=str(path))
                                if stale:
                                    from .core import Issue
                                    issues.append(Issue("stale_preview", {"path": str(path)}, "warning", tab_id, entry["id"]))
                            except StudioError as error:
                                issues.append(error.issue)
                            except OSError:
                                issues.append(StudioError("missing_file", path=str(path)).issue)
        ok = not any(issue.severity == "error" for issue in issues)
        output = {"ok": ok, "project": project.config["name"],
                  "issues": [issue.as_dict(args.ui_language) for issue in issues]}
        sys.stdout.write(json_bytes(output).decode("utf-8"))
        return 0 if ok else 1
    except StudioError as error:
        sys.stdout.write(json_bytes({"ok": False, "issues": [error.issue.as_dict(args.ui_language)]}).decode("utf-8"))
        return 1
    except (OSError, KeyError, TypeError, ValueError) as error:
        sys.stderr.write(str(error) + "\n")
        return 2
