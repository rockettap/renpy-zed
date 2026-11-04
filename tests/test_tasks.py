#!/usr/bin/env python3
"""Run languages/renpy/tasks.json against a fake Ren'Py SDK.

Zed substitutes ``$ZED_*`` variables and then pastes the command and every
argument into one shell line without additional quoting. This replay keeps that
behaviour, so paths with spaces and apostrophes are exercised under every POSIX
shell available on the machine.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
TASKS = json.loads(
    (HERE.parent / "languages" / "renpy" / "tasks.json").read_text(encoding="utf-8")
)

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"{status}: {label}{suffix}")
    if not condition:
        failures.append(label)


def substitute(text: str, variables: dict[str, str]) -> str:
    return re.sub(r"\$(ZED_[A-Za-z_]+)", lambda match: variables[match.group(1)], text)


def run(
    shell: str,
    task: dict[str, object],
    variables: dict[str, str],
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    command = substitute(str(task["command"]), variables)
    args = [substitute(str(arg), variables) for arg in task["args"]]
    line = " ".join([command, *args])
    return subprocess.run(
        [shell, "-c", line],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def expected_args(mode: str, project: pathlib.Path, relative: str, row: int) -> list[str]:
    if mode == "run":
        return [str(project), "run"]
    if mode == "warp":
        return [str(project), "run", "--warp", f"{relative}:{row}"]
    if mode == "lint":
        return [str(project), "lint"]
    if mode == "compile":
        return [str(project), "compile"]
    if mode == "dialogue":
        return [str(project), "dialogue", "None"]
    return [str(project), "rmpersistent"]


work = pathlib.Path(tempfile.mkdtemp(prefix="renpy-tasks-"))
try:
    sdk = work / "renpy-8.9.9-sdk"
    sdk.mkdir()
    (sdk / "renpy.sh").write_text(
        '#!/bin/sh\nfor arg in "$@"; do echo "ARG:$arg"; done\n', encoding="utf-8"
    )
    (sdk / "renpy.sh").chmod(0o755)

    shells = [name for name in ("sh", "bash", "zsh", "dash") if shutil.which(name)]
    check("a POSIX shell is available", bool(shells), "install sh")

    # Regression: macOS installs the SDK into /Applications, so discovery must
    # look there as well as in the user's home directories.
    for task in TASKS:
        scripts = [str(task["command"]), *(str(arg) for arg in task["args"])]
        check(
            f"{task['label']} searches /Applications",
            any(" /Applications " in script for script in scripts),
        )

    projects = [work / "proj", work / "Ren'Py games" / "my game"]
    for project in projects:
        script = project / "game" / "chapter one.rpy"
        script.parent.mkdir(parents=True)
        script.write_text("label start:\n    return\n", encoding="utf-8")
        for shell in shells:
            env = dict(os.environ, RENPY_SDK=str(sdk))
            for task in TASKS:
                mode = str(task["env"]["RENPY_ZED_TASK"])  # type: ignore[index]
                row = 3 if "label" in str(task["label"]) else 1
                variables = {
                    "ZED_FILE": str(script),
                    "ZED_ROW": str(row),
                    "ZED_CUSTOM_renpy_label": "start",
                }
                result = run(shell, task, variables, env)
                got = [line[4:] for line in result.stdout.splitlines() if line.startswith("ARG:")]
                expected = expected_args(mode, project, "game/chapter one.rpy", row)
                check(
                    f"{shell}: {substitute(str(task['label']), variables)} in {project.name!r}",
                    result.returncode == 0 and got == expected,
                    f"exit {result.returncode}, args {got}, stderr {result.stderr.strip()[-200:]}",
                )

    # RENPY_SDK may point at renpy.sh itself.
    script = projects[0] / "game" / "chapter one.rpy"
    variables = {"ZED_FILE": str(script), "ZED_ROW": "1", "ZED_CUSTOM_renpy_label": "start"}
    result = run(
        "sh",
        TASKS[0],
        variables,
        dict(os.environ, RENPY_SDK=str(sdk / "renpy.sh")),
    )
    got = [line[4:] for line in result.stdout.splitlines() if line.startswith("ARG:")]
    check(
        "RENPY_SDK may name renpy.sh",
        result.returncode == 0 and got == [str(projects[0]), "run"],
        result.stderr.strip()[-200:],
    )

    # Discovery: newest renpy-*-sdk under HOME wins when RENPY_SDK is unset.
    home = work / "home"
    older = home / "renpy-8.9-sdk"
    newer = home / "Downloads" / "renpy-8.10-sdk"
    for directory in (older, newer):
        directory.mkdir(parents=True)
        (directory / "renpy.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (directory / "renpy.sh").chmod(0o755)
    env = {"PATH": os.environ["PATH"], "HOME": str(home)}
    result = run("sh", TASKS[0], variables, env)
    check(
        "discovery picks the newest SDK",
        result.returncode == 0,
        result.stderr.strip()[-200:],
    )

    # Missing SDK and invalid paths explain themselves. Swap the system-wide
    # /Applications for an empty directory so a real SDK on this machine does
    # not turn the "missing" case into a success.
    empty_home = work / "empty-home"
    empty_home.mkdir()
    empty_applications = work / "empty-applications"
    empty_applications.mkdir()
    no_sdk_task = {
        **TASKS[0],
        "args": [
            str(arg).replace(" /Applications ", f" {empty_applications} ")
            for arg in TASKS[0]["args"]  # type: ignore[index]
        ],
    }
    result = run(
        "sh",
        no_sdk_task,
        variables,
        {"PATH": os.environ["PATH"], "HOME": str(empty_home)},
    )
    check(
        "a missing SDK is reported",
        result.returncode == 1 and "Ren-Py SDK not found" in result.stderr,
        result.stderr.strip()[-200:],
    )

    result = run("sh", TASKS[0], variables, dict(os.environ, RENPY_SDK=str(work / "nope")))
    check(
        "an invalid RENPY_SDK is reported",
        result.returncode == 1 and "RENPY_SDK is set" in result.stderr,
        result.stderr.strip()[-200:],
    )

    outside = work / "outside.rpy"
    outside.write_text("label start:\n    return\n", encoding="utf-8")
    result = run(
        "sh",
        TASKS[0],
        {"ZED_FILE": str(outside), "ZED_ROW": "1", "ZED_CUSTOM_renpy_label": "start"},
        dict(os.environ, RENPY_SDK=str(sdk)),
    )
    check(
        "a file outside game/ is reported",
        result.returncode == 1 and "is not inside a game/ folder" in result.stderr,
        result.stderr.strip()[-200:],
    )
finally:
    shutil.rmtree(work, ignore_errors=True)

if failures:
    print(f"\n{len(failures)} FAILURE(S)")
    sys.exit(1)
print("\nALL CHECKS PASSED")
