import os
import re
import time

from log_purge import cli

DAY = 86_400


def make_old(path, age_days=40):
    path.write_text("data")
    t = time.time() - age_days * DAY
    os.utime(path, (t, t))
    return path


def test_dry_run_deletes_nothing(tmp_path, capsys):
    f = make_old(tmp_path / "a.log")
    assert cli.main([str(tmp_path), "-d", "30", "--dry-run"]) == 0
    assert f.exists()
    assert "Would delete 1" in capsys.readouterr().out


def test_yes_deletes(tmp_path):
    f = make_old(tmp_path / "a.log")
    assert cli.main([str(tmp_path), "-d", "30", "--yes"]) == 0
    assert not f.exists()


def test_prompt_declined_keeps_files(tmp_path, monkeypatch):
    f = make_old(tmp_path / "a.log")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert cli.main([str(tmp_path), "-d", "30"]) == 0
    assert f.exists()


def test_prompt_accepted_deletes(tmp_path, monkeypatch):
    f = make_old(tmp_path / "a.log")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert cli.main([str(tmp_path), "-d", "30"]) == 0
    assert not f.exists()


def test_non_interactive_without_yes_is_refused(tmp_path, monkeypatch):
    f = make_old(tmp_path / "a.log")
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert cli.main([str(tmp_path), "-d", "30"]) == 2
    assert f.exists()


def test_bad_directory_and_root(tmp_path):
    assert cli.main([str(tmp_path / "nope"), "-d", "1"]) == 2
    assert cli.main([os.path.abspath(os.sep), "-d", "1", "--yes"]) == 2


def test_quiet_mode_deletes_silently(tmp_path, capsys):
    f = make_old(tmp_path / "a.log")
    assert cli.main([str(tmp_path), "-d", "30", "--yes", "--quiet"]) == 0
    assert not f.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_mode_short_flag(tmp_path, capsys):
    f = make_old(tmp_path / "a.log")
    assert cli.main([str(tmp_path), "-d", "30", "--yes", "-q"]) == 0
    assert not f.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_mode_dry_run(tmp_path, capsys):
    f = make_old(tmp_path / "a.log")
    assert cli.main([str(tmp_path), "-d", "30", "--dry-run", "-q"]) == 0
    assert f.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_mode_nothing_to_delete(tmp_path, capsys):
    assert cli.main([str(tmp_path), "-d", "30", "-q"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_mode_errors_still_printed(tmp_path, capsys):
    assert cli.main([str(tmp_path / "nope"), "-d", "1", "-q"]) == 2
    captured = capsys.readouterr()
    assert "error: not a directory" in captured.err


def test_quiet_mode_deletion_failures_printed_to_stderr(tmp_path, capsys, monkeypatch):
    make_old(tmp_path / "a.log")

    def fake_unlink(self):
        raise PermissionError("Permission denied")

    monkeypatch.setattr("pathlib.Path.unlink", fake_unlink)
    assert cli.main([str(tmp_path), "-d", "30", "--yes", "-q"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "could not be deleted" in captured.err


def test_log_file_records_deletions(tmp_path):
    f = make_old(tmp_path / "a.log")
    log_file = tmp_path / "audit.log"
    assert cli.main([str(tmp_path), "-d", "30", "--yes", "--log-file", str(log_file)]) == 0
    assert not f.exists()
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    timestamp_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z "
    assert re.match(timestamp_pattern + r"DELETED .*a\.log 4 bytes", lines[0])
    assert re.match(timestamp_pattern + r"SUMMARY Deleted 1 file\(s\), freed 4 B\.", lines[1])


def test_log_file_dry_run_records_would_delete(tmp_path):
    f = make_old(tmp_path / "a.log")
    log_file = tmp_path / "audit.log"
    assert cli.main(
        [str(tmp_path), "-d", "30", "--dry-run", "--log-file", str(log_file)]
    ) == 0
    assert f.exists()
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    timestamp_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z "
    summary_pattern = (
        timestamp_pattern + r"SUMMARY \[dry-run\] Would delete 1 file\(s\), freeing 4 B\."
    )
    assert re.match(summary_pattern, lines[1])




def test_log_file_appends_to_existing(tmp_path):
    log_file = tmp_path / "audit.log"
    log_file.write_text("existing audit entry\n", encoding="utf-8")
    make_old(tmp_path / "a.log")
    assert cli.main([str(tmp_path), "-d", "30", "--yes", "--log-file", str(log_file)]) == 0
    content = log_file.read_text(encoding="utf-8")
    assert content.startswith("existing audit entry\n")
    assert "DELETED " in content
    assert "SUMMARY " in content


def test_log_file_unwritable_path_exits_2_and_leaves_files(tmp_path, capsys):
    f = make_old(tmp_path / "a.log")
    bad_log = tmp_path / "nonexistent_dir" / "audit.log"
    assert cli.main([str(tmp_path), "-d", "30", "--yes", "--log-file", str(bad_log)]) == 2
    captured = capsys.readouterr()
    assert "error: cannot open log file" in captured.err
    assert f.exists()


def test_log_file_deletion_failure_records_failed(tmp_path, monkeypatch):
    make_old(tmp_path / "a.log")
    log_file = tmp_path / "audit.log"

    def fake_unlink(self):
        raise PermissionError("Permission denied")

    monkeypatch.setattr("pathlib.Path.unlink", fake_unlink)
    assert cli.main([str(tmp_path), "-d", "30", "--yes", "--log-file", str(log_file)]) == 1
    content = log_file.read_text(encoding="utf-8")
    assert "FAILED " in content
    assert "Permission denied" in content
    assert "SUMMARY " in content


def test_log_file_nothing_to_delete(tmp_path):
    log_file = tmp_path / "audit.log"
    assert cli.main([str(tmp_path), "-d", "30", "--log-file", str(log_file)]) == 0
    content = log_file.read_text(encoding="utf-8")
    assert "SUMMARY Nothing to delete: no files older than 30 day(s)." in content



