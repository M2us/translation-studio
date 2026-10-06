"""Desktop entry point; worker mode deliberately does not import Qt."""
import sys

if __name__ == "__main__":
    if "--worker" in sys.argv:
        from translation_studio.processes import worker
        raise SystemExit(worker())
    if len(sys.argv) == 4 and sys.argv[1] == "--smoke-test":
        import traceback
        from pathlib import Path
        with Path(sys.argv[3] + ".log").open("w", encoding="utf-8") as log:
            import faulthandler
            faulthandler.enable(log)
            sys.stdout = sys.stderr = log
            print("Loading smoke verifier", flush=True)
            from translation_studio.diagnostics import start
            session = start()
            try:
                from translation_studio.smoke import main
                result = main(sys.argv[2], sys.argv[3])
            except Exception:
                traceback.print_exc()
                result = 1
            finally:
                session.close()
            raise SystemExit(result)
    from translation_studio.diagnostics import start
    try:
        session = start()
    except Exception:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,
            "Cannot open the profile. Close another instance and check write access to the Data folder.\n\n"
            "Не удалось открыть профиль. Закройте другой экземпляр программы и проверьте доступ на запись к папке Data.",
            "Translation Studio", 0x10)
        raise SystemExit(1)
    try:
        from translation_studio.gui import main
        result = main()
    except BaseException as error:
        session.exception(error, origin="startup_or_main")
        result = 1
    finally:
        session.close()
    raise SystemExit(result)
