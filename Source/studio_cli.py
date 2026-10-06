import sys

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--worker" in sys.argv:
        from translation_studio.processes import worker
        raise SystemExit(worker())
    from translation_studio.cli import main
    raise SystemExit(main())
