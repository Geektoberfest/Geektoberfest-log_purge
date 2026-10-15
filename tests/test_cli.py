import os
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


def test_exclude_protects_files(tmp_path):
    keep = make_old(tmp_path / "important.keep")
    old = make_old(tmp_path / "old.log")
    assert cli.main([
        str(tmp_path), "-d", "30", "--yes", "--exclude", "*.keep"
    ]) == 0
    assert keep.exists()
    assert not old.exists()


def test_exclude_short_flag(tmp_path):
    keep = make_old(tmp_path / "important.keep")
    old = make_old(tmp_path / "old.log")
    assert cli.main([str(tmp_path), "-d", "30", "--yes", "-e", "*.keep"]) == 0
    assert keep.exists()
    assert not old.exists()


def test_exclude_multiple_patterns(tmp_path):
    keep1 = make_old(tmp_path / "a.keep")
    keep2 = make_old(tmp_path / "b.bak")
    old = make_old(tmp_path / "c.log")
    assert cli.main([
        str(tmp_path), "-d", "30", "--yes",
        "--exclude", "*.keep", "--exclude", "*.bak",
    ]) == 0
    assert keep1.exists()
    assert keep2.exists()
    assert not old.exists()


def test_exclude_dry_run_preserves_files(tmp_path, capsys):
    keep = make_old(tmp_path / "important.keep")
    old = make_old(tmp_path / "old.log")
    assert cli.main([
        str(tmp_path), "-d", "30", "--dry-run", "--exclude", "*.keep"
    ]) == 0
    out = capsys.readouterr().out
    assert "Would delete 1" in out
    assert keep.exists()
    assert old.exists()



