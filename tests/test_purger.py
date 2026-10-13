import os
import time

import pytest

from log_purge.purger import delete_files, find_old_files
from log_purge.utils import parse_size

DAY = 86_400


def make_file(path, age_days, content="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    t = time.time() - age_days * DAY
    os.utime(path, (t, t))
    return path


def test_finds_only_old_files(tmp_path):
    old = make_file(tmp_path / "old.log", 40)
    make_file(tmp_path / "new.log", 5)
    found = find_old_files(tmp_path, days=30)
    assert [c.path for c in found] == [old]


def test_recursive_and_non_recursive(tmp_path):
    top = make_file(tmp_path / "a.log", 40)
    nested = make_file(tmp_path / "sub" / "b.log", 40)
    assert {c.path for c in find_old_files(tmp_path, 30)} == {top, nested}
    assert {c.path for c in find_old_files(tmp_path, 30, recursive=False)} == {top}


def test_pattern_filter(tmp_path):
    log_file = make_file(tmp_path / "a.log", 40)
    make_file(tmp_path / "keep.txt", 40)
    assert [c.path for c in find_old_files(tmp_path, 30, "*.log")] == [log_file]


def test_symlinks_are_skipped(tmp_path):
    target = make_file(tmp_path / "outside" / "t.log", 40)
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "link.log").symlink_to(target)
    except OSError:
        pytest.skip("symlinks not supported")
    assert find_old_files(root, 30) == []


def test_delete_files_counts_and_frees(tmp_path):
    make_file(tmp_path / "a.log", 40, "hello")
    make_file(tmp_path / "b.log", 40, "world!")
    result = delete_files(find_old_files(tmp_path, 30))
    assert result.deleted == 2
    assert result.freed_bytes == 11
    assert not result.failures
    assert list(tmp_path.iterdir()) == []


def test_delete_failure_does_not_stop_run(tmp_path):
    a = make_file(tmp_path / "a.log", 40)
    b = make_file(tmp_path / "b.log", 40)
    candidates = find_old_files(tmp_path, 30)
    a.unlink()  # vanishes before deletion -> FileNotFoundError
    result = delete_files(candidates)
    assert result.deleted == 1 and len(result.failures) == 1
    assert not b.exists()


def test_invalid_inputs(tmp_path):
    with pytest.raises(ValueError):
        find_old_files(tmp_path, -1)
    with pytest.raises(NotADirectoryError):
        find_old_files(tmp_path / "missing", 1)
    with pytest.raises(ValueError):
        find_old_files(tmp_path, 1, min_size=-1)
    with pytest.raises(ValueError):
        find_old_files(tmp_path, 1, max_size=-1)
    with pytest.raises(ValueError):
        find_old_files(tmp_path, 1, min_size=100, max_size=50)


def test_parse_size():
    assert parse_size("10MB") == 10 * 1024 * 1024
    assert parse_size("10mb") == 10 * 1024 * 1024
    assert parse_size("10 MB") == 10 * 1024 * 1024
    assert parse_size("500B") == 500
    assert parse_size("1KB") == 1024
    assert parse_size("2GB") == 2 * 1024**3
    assert parse_size("1.5KB") == 1536
    assert parse_size("1024") == 1024

    for invalid in ("", "   ", "abc", "-10MB", "10XB", "MB"):
        with pytest.raises(ValueError):
            parse_size(invalid)


def test_find_old_files_size_filtering(tmp_path):
    small = make_file(tmp_path / "small.log", 40, content="a" * 10)       # 10 bytes
    medium = make_file(tmp_path / "medium.log", 40, content="b" * 100)    # 100 bytes
    large = make_file(tmp_path / "large.log", 40, content="c" * 1000)     # 1000 bytes

    # min_size alone
    assert {c.path for c in find_old_files(tmp_path, 30, min_size=100)} == {medium, large}
    # max_size alone
    assert {c.path for c in find_old_files(tmp_path, 30, max_size=100)} == {small, medium}
    # both min_size and max_size
    assert {c.path for c in find_old_files(tmp_path, 30, min_size=50, max_size=500)} == {medium}
    # boundary: exact match
    assert {c.path for c in find_old_files(tmp_path, 30, min_size=10, max_size=10)} == {small}
