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


def test_cli_min_size_filter(tmp_path):
    small = tmp_path / "small.log"
    small.write_text("a" * 10)
    t = time.time() - 40 * DAY
    os.utime(small, (t, t))

    large = tmp_path / "large.log"
    large.write_text("b" * 1000)
    os.utime(large, (t, t))

    assert cli.main([str(tmp_path), "-d", "30", "--yes", "--min-size", "500B"]) == 0
    assert small.exists()
    assert not large.exists()


def test_cli_max_size_filter(tmp_path):
    small = tmp_path / "small.log"
    small.write_text("a" * 10)
    t = time.time() - 40 * DAY
    os.utime(small, (t, t))

    large = tmp_path / "large.log"
    large.write_text("b" * 1000)
    os.utime(large, (t, t))

    assert cli.main([str(tmp_path), "-d", "30", "--yes", "--max-size", "500B"]) == 0
    assert not small.exists()
    assert large.exists()


def test_cli_both_size_filters(tmp_path):
    f1 = tmp_path / "1.log"
    f1.write_text("a" * 10)
    f2 = tmp_path / "2.log"
    f2.write_text("b" * 100)
    f3 = tmp_path / "3.log"
    f3.write_text("c" * 1000)
    t = time.time() - 40 * DAY
    for f in (f1, f2, f3):
        os.utime(f, (t, t))

    assert cli.main([
        str(tmp_path), "-d", "30", "--yes",
        "--min-size", "50B", "--max-size", "500B"
    ]) == 0
    assert f1.exists()
    assert not f2.exists()
    assert f3.exists()


def test_cli_invalid_size_exit_code_2(tmp_path, capsys):
    assert cli.main([str(tmp_path), "-d", "30", "--min-size", "invalid_size"]) == 2
    captured = capsys.readouterr()
    assert "error: invalid --min-size" in captured.err

    assert cli.main([str(tmp_path), "-d", "30", "--max-size", "invalid_size"]) == 2
    captured = capsys.readouterr()
    assert "error: invalid --max-size" in captured.err


def test_cli_min_greater_than_max_exit_code_2(tmp_path, capsys):
    assert cli.main([
        str(tmp_path), "-d", "30",
        "--min-size", "10MB", "--max-size", "5MB"
    ]) == 2
    captured = capsys.readouterr()
    assert "error: --min-size cannot be greater than --max-size" in captured.err
