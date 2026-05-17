import os
from pathlib import Path

import pytest

from app.agents.tools.file_system import FileSystemTools


@pytest.fixture()
def temp_base_dir(tmp_path: Path) -> Path:
    # Use a real directory on disk
    return tmp_path


def _touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_symlink_inside_pointing_outside_is_rejected(temp_base_dir: Path) -> None:
    base = temp_base_dir
    outside = base.parent / "outside.txt"
    _touch(outside, "outside")

    # symlink that lives inside base but targets outside
    link = base / "link-outside.txt"
    link.symlink_to(outside)

    fs = FileSystemTools(base_dir=str(base))

    with pytest.raises(ValueError):
        fs.read_file(os.fspath(link.relative_to(base)))


def test_symlink_inside_pointing_inside_is_allowed(temp_base_dir: Path) -> None:
    base = temp_base_dir
    target = base / "target.txt"
    _touch(target, "inside")

    link = base / "link-inside.txt"
    link.symlink_to(target)

    fs = FileSystemTools(base_dir=str(base))

    assert fs.read_file(os.fspath(link.relative_to(base))) == "inside"


def test_base_dir_is_symlink_behaves_correctly(tmp_path: Path) -> None:
    real_base = tmp_path / "real-base"
    real_base.mkdir()

    target = real_base / "file.txt"
    _touch(target, "data")

    base_symlink = tmp_path / "base-link"
    base_symlink.symlink_to(real_base, target_is_directory=True)

    fs = FileSystemTools(base_dir=os.fspath(base_symlink))

    # Access via path that stays within the real base
    assert fs.read_file("file.txt") == "data"

    # A symlink inside the base that escapes should still be rejected
    outside = tmp_path / "outside.txt"
    _touch(outside, "outside")
    escape_link = real_base / "escape.txt"
    escape_link.symlink_to(outside)

    with pytest.raises(ValueError):
        fs.read_file("escape.txt")


def test_absolute_and_dotdot_paths(temp_base_dir: Path) -> None:
    base = temp_base_dir
    inside = base / "dir" / "file.txt"
    _touch(inside, "content")

    fs = FileSystemTools(base_dir=str(base))

    # Relative with .. that stays inside
    rel_path = os.path.join("dir", "sub", "..", "file.txt")
    assert fs.read_file(rel_path) == "content"

    # Attempt to escape with .. should be rejected
    with pytest.raises(ValueError):
        fs.read_file(os.path.join("..", "outside.txt"))

    # Absolute path to inside file should be allowed
    assert fs.read_file(os.fspath(inside)) == "content"

    # Absolute path that escapes should be rejected
    outside = base.parent / "escape.txt"
    _touch(outside, "outside")
    with pytest.raises(ValueError):
        fs.read_file(os.fspath(outside))