import copy
from pathlib import Path
import subprocess
import sys
import time
import pytest
from translation_studio.core import Project, StudioError
from translation_studio.processes import ActionRunner

ROOT = Path(__file__).resolve().parents[1]


def wait(runner, timeout=15):
    runner.thread.join(timeout)
    if runner.thread.is_alive():
        runner.cancel()
        runner.thread.join(5)
        pytest.fail("Process timeout")
    events = []
    while not runner.events.empty():
        events.append(runner.events.get_nowait())
    return next(data for kind, data in events if kind == "done"), events


def action(project, script):
    a = copy.deepcopy(project.config["actions"][0])
    a.update(executable="python", arguments=["-u", "-c", script])
    return ActionRunner(project, a, sys.executable)


def test_utf8_exit_and_inputs(game):
    p = Project(game)
    runner = action(p, "print('Привет с пробелами', flush=True)")
    runner.start()
    result, events = wait(runner)
    assert result == {"code": 0, "cancelled": False, "changed": False}, events
    assert "Привет с пробелами" in runner.log_path.read_text(encoding="utf-8")
    failure = action(p, "raise SystemExit(7)")
    failure.start()
    assert wait(failure)[0]["code"] == 7
    changed = action(p, "from pathlib import Path; p=Path('Translation/Text/main.json'); p.write_bytes(p.read_bytes()+b'\\n')")
    changed.start()
    assert wait(changed)[0]["changed"]


def test_cancel_process_tree(game):
    p = Project(game)
    child = "import time; from pathlib import Path; Path('Work/child.started').touch(); time.sleep(2); Path('Work/child.survived').touch()"
    parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); time.sleep(20)"
    runner = action(p, parent)
    runner.start()
    deadline = time.monotonic() + 10
    while not (game / "Work/child.started").exists() and time.monotonic() < deadline:
        time.sleep(.05)
    assert (game / "Work/child.started").exists()
    runner.cancel()
    assert wait(runner)[0]["cancelled"]
    time.sleep(2.3)
    assert not (game / "Work/child.survived").exists()


@pytest.mark.parametrize("variant", ["NES", "Sega"])
def test_save_to_external_adapter(tmp_path, variant):
    import shutil
    game = tmp_path / ("Перенос " + variant)
    shutil.copytree(ROOT / "Examples" / ("Synthetic " + variant), game)
    command = [sys.executable, str(game / "Scripts/build.py"), "--sdk", str(ROOT / "Source"), "--language", "ru"]
    first = subprocess.run(command, capture_output=True)
    assert first.returncode == 0, first.stderr
    before = (game / "Builds/Patch/translation.bin").read_bytes()
    p = Project(game, editable=True)
    try:
        p.set_text("text", p.documents["text"]["entries"][0]["id"], "ru", "Пуск")
        p.save()
    finally:
        p.close()
    second = subprocess.run(command, capture_output=True)
    assert second.returncode == 0, second.stderr
    after = (game / "Builds/Patch/translation.bin").read_bytes()
    assert before != after
    assert "Пуск".encode("utf-8" if variant == "NES" else "utf-16le") in after


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1251", "cp866"])
def test_output_encoding_keeps_stdout_stderr_and_raw(game, encoding):
    phrase = "Сборка: Ёжик - файл готов\r\n"
    error_line = "Проверка ошибок: успешно\n"
    raw = phrase.encode(encoding)
    stderr = error_line.encode("utf-8" if encoding == "utf-8-sig" else encoding)
    script = ("import sys,time; "
        f"sys.stdout.buffer.write({raw[:2]!r}); sys.stdout.buffer.flush(); time.sleep(.02); "
        f"sys.stdout.buffer.write({raw[2:]!r}); sys.stdout.buffer.flush(); "
        f"sys.stderr.buffer.write({stderr!r}); sys.stderr.buffer.flush()")
    p = Project(game)
    runner = action(p, script)
    runner.action["outputEncoding"] = encoding
    runner.start()
    result, events = wait(runner)
    assert result["code"] == 0, events
    assert not any(kind == "warning" for kind, _ in events)
    saved = runner.log_path.read_text(encoding="utf-8")
    displayed = "".join(data for kind, data in events if kind == "line")
    assert phrase.strip() in saved and error_line.strip() in saved
    assert phrase.strip() in displayed and error_line.strip() in displayed
    assert "\ufffd" not in saved and "\ufffd" not in displayed
    assert runner.raw_log_path.read_bytes() == raw + stderr


def test_wrong_encoding_warns_and_preserves_bytes(game):
    raw = "Привет\nПроверка\n".encode("cp1251")
    runner = action(Project(game), f"import sys; sys.stdout.buffer.write({raw!r})")
    runner.start()
    result, events = wait(runner)
    assert result["code"] == 0
    warnings = [data for kind, data in events if kind == "warning"]
    assert len(warnings) == 1 and warnings[0].code == "log_encoding"
    assert "outputEncoding" in warnings[0].message("ru")
    saved = runner.log_path.read_text(encoding="utf-8")
    assert "\ufffd" not in saved and "\\xcf" in saved
    assert runner.raw_log_path.read_bytes() == raw


def test_action_output_encoding_schema(game):
    from translation_studio.core import read_json, atomic_write
    path = game / "Translation/project.json"
    config = read_json(path)
    config["actions"][0]["outputEncoding"] = "cp866"
    atomic_write(path, config)
    assert Project(game).config["actions"][0]["outputEncoding"] == "cp866"
    config["actions"][0]["outputEncoding"] = "unknown-codec"
    atomic_write(path, config)
    with pytest.raises(StudioError) as error:
        Project(game)
    assert error.value.issue.code == "schema"
