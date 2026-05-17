import os
import sys
import tempfile
import shutil

import pytest

from app.agents.tools.file_system import FileSystemTools


@pytest.fixture
def temp_base_dir(tmp_path):
    return tmp_path


def make_case_variant(path: os.PathLike[str]) -> str:
    # Helper to exercise case-insensitive behaviour where applicable.
    s = str(path)
    if sys.platform.startswith("win"):
        return s.swapcase()
    return s


def test_resolve_inside_base_dir(temp_base_dir):
    tools = FileSystemTools(base_dir=str(temp_base_dir))
    target = temp_base_dir / "sub" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("data")

    resolved = tools._resolve("sub/file.txt")

    assert os.path.samefile(resolved, target)


def test_resolve_parent_escape_raises(temp_base_dir):
    tools = FileSystemTools(base_dir=str(temp_base_dir))

    with pytest.raises(ValueError):
        tools._resolve("../outside.txt")


def test_resolve_symlink_inside_pointing_outside_raises(temp_base_dir, tmp_path):
    tools = FileSystemTools(base_dir=str(temp_base_dir))

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_target = outside_dir / "secret.txt"
    outside_target.write_text("secret")

    link_inside = temp_base_dir / "link.txt"
    os.symlink(outside_target, link_inside)

    with pytest.raises(ValueError):
        tools._resolve("link.txt")


def test_resolve_symlink_outside_pointing_inside_allowed(tmp_path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    tools = FileSystemTools(base_dir=str(base_dir))

    inside_target = base_dir / "inside.txt"
    inside_target.write_text("ok")

    link_outside = tmp_path / "link_to_inside.txt"
    os.symlink(inside_target, link_outside)

    # Resolve relative to base_dir so this should still be inside base.
    resolved = tools._resolve("inside.txt")

    assert os.path.samefile(resolved, inside_target)


def test_resolve_base_dir_prefix_collision(tmp_path):
    base_dir = tmp_path / "base" / "dir"
    malicious_dir = tmp_path / "base" / "dir_malicious"
    malicious_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)

    tools = FileSystemTools(base_dir=str(base_dir))

    # Direct access to a file in the malicious directory should not be
    # considered inside base_dir just because of a prefix match.
    malicious_file = malicious_dir / "file.txt"
    malicious_file.write_text("evil")

    with pytest.raises(ValueError):
        tools._resolve("../dir_malicious/file.txt")


def test_resolve_case_insensitive_behaviour(tmp_path):
    base_dir = tmp_path / "CaseDir"
    base_dir.mkdir()
    tools = FileSystemTools(base_dir=make_case_variant(base_dir))

    target = base_dir / "File.txt"
    target.write_text("data")

    resolved = tools._resolve("File.txt")

    assert os.path.samefile(resolved, target)