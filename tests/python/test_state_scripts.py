"""Exercise durable-state scripts with a real, local Git remote (no credentials)."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_first_empty_save_then_checkpoint_and_restore(tmp_path):
    if os.name == "nt":
        bash = Path(shutil.which("git")).parents[1] / "bin/bash.exe"
    else:
        bash = Path(shutil.which("bash"))
    if not bash.exists():
        pytest.skip("Git Bash required")
    scripts = Path("scripts").resolve()
    env = dict(
        os.environ,
        GIT_CONFIG_GLOBAL=str(tmp_path / "no-global"),
        GIT_CONFIG_NOSYSTEM="1",
    )

    def run(args, cwd):
        return subprocess.run(
            args, cwd=cwd, env=env, text=True, capture_output=True, check=True
        )

    remote = tmp_path / "remote.git"
    run(["git", "init", "--bare", str(remote)], tmp_path)

    def checkout(name):
        root = tmp_path / name
        root.mkdir()
        run(["git", "init"], root)
        run(["git", "remote", "add", "origin", str(remote)], root)
        run([str(bash), (scripts / "prepare-state.sh").as_posix()], root)
        return root

    first = checkout("first")
    run([str(bash), (scripts / "persist-state.sh").as_posix()], first)
    (first / "data/state/status.json").write_text(
        '{"state":"running"}', encoding="utf-8"
    )
    run([str(bash), (scripts / "persist-state.sh").as_posix()], first)
    second = checkout("second")
    assert (second / "data/state/status.json").read_text() == '{"state":"running"}'
