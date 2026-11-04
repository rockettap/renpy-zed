#!/usr/bin/env python3
"""Static checks for the declarative Zed extension assets."""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LANGUAGE = ROOT / "languages" / "renpy"

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"{'PASS' if condition else 'FAIL'}: {label}{suffix}")
    if not condition:
        failures.append(label)


snippets_path = ROOT / "snippets" / "ren'py.json"
check("the snippet file uses the Ren'Py scope name", snippets_path.is_file())
snippets = json.loads(snippets_path.read_text(encoding="utf-8"))

required_snippets = {
    "Label",
    "Menu",
    "Character",
    "Screen",
    "Text button",
    "Image button",
    "Layered image",
    "Transform / ATL",
    "Style",
    "Translate",
    "Python block",
    "Init block",
    "Jump",
    "If / else",
    "Assert",
    "Testcase",
    "Region",
}
check("required snippets exist", required_snippets <= set(snippets), str(required_snippets - set(snippets)))

prefixes: list[str] = []
for name, snippet in snippets.items():
    prefix = snippet.get("prefix")
    prefixes.extend(prefix if isinstance(prefix, list) else [prefix])
    body = snippet.get("body")
    check(f"snippet {name!r} has a string prefix", isinstance(prefix, (str, list)))
    check(f"snippet {name!r} has a body", isinstance(body, (str, list)))
    lines = [body] if isinstance(body, str) else body
    check(f"snippet {name!r} has a final cursor", any("$0" in line for line in lines))
    for line in lines:
        for match in re.finditer(r"\$", line):
            index = match.start()
            escaped = index > 0 and line[index - 1] == "\\"
            placeholder = index + 1 < len(line) and line[index + 1] in "0123456789{"
            check(
                f"snippet {name!r} escapes literal dollars",
                escaped or placeholder,
                line,
            )
check("snippet prefixes are unique", len(prefixes) == len(set(prefixes)), str(prefixes))

manifest = (ROOT / "extension.toml").read_text(encoding="utf-8")
check(
    "the snippet file is registered",
    'snippets = ["./snippets/ren\'py.json"]' in manifest,
)
check("the grammar revision is still pinned", re.search(r"^rev = \"[0-9a-f]{40}\"$", manifest, re.M) is not None)

config = (LANGUAGE / "config.toml").read_text(encoding="utf-8")
check("Markdown fences use the renpy name", 'code_fence_block_name = "renpy"' in config)
check(
    "the renpy suffix resolves Markdown fences",
    re.search(r'path_suffixes = \[[^\]]*"renpy"', config) is not None,
)
check("Ren'Py word characters include $ and _", 'word_characters = ["_", "$"]' in config)
check("string overrides are configured", "[overrides.string]" in config)
check(
    "string completion keeps dots and hyphens",
    'completion_query_characters = [".", "-"]' in config,
)

for prefix in ("r", "R", "u", "U", "f", "F", "b", "B"):
    double = f'{{ start = "{prefix}\\"", end = "\\""'
    single = f'{{ start = "{prefix}\'", end = "\'"'
    check(f"auto-closing pair {prefix}\" exists", double in config)
    check(f"auto-closing pair {prefix}' exists", single in config)
check('auto-closing pair "`" exists', '{ start = "`", end = "`"' in config)
check('triple-double-quote pair exists', '{ start = "\\"\\"\\"", end = "\\"\\"\\""' in config)
check("single-quote triple pair exists", '{ start = "\'\'\'", end = "\'\'\'"' in config)

for query in (
    "textobjects.scm",
    "overrides.scm",
    "runnables.scm",
):
    check(f"{query} exists", (LANGUAGE / query).is_file())

textobjects = (LANGUAGE / "textobjects.scm").read_text(encoding="utf-8")
for capture in ("@class.around", "@class.inside", "@function.around", "@function.inside"):
    check(f"text objects use {capture}", capture in textobjects)

overrides = (LANGUAGE / "overrides.scm").read_text(encoding="utf-8")
check("comments are an inclusive override", "(comment) @comment.inclusive" in overrides)
check("strings are an override", "(string) @string" in overrides)

runnables = (LANGUAGE / "runnables.scm").read_text(encoding="utf-8")
check("labels are runnable", '"label" @run' in runnables)
check("the label runnable is tagged", "(#set! tag renpy-label)" in runnables)
check("the label name is exposed", "@renpy_label" in runnables)

tasks = json.loads((LANGUAGE / "tasks.json").read_text(encoding="utf-8"))
check("seven tasks are declared", len(tasks) == 7, str(len(tasks)))
labels = [task["label"] for task in tasks]
for expected in (
    "run game",
    "run from line",
    "run from label",
    "lint",
    "compile",
    "dialogue",
    "remove persistent",
):
    check(f"a {expected} task exists", any(expected in label for label in labels), str(labels))
check(
    "the label task is bound to the runnable",
    any("renpy-label" in task.get("tags", []) for task in tasks),
)
check(
    "every task uses sh",
    all(task["command"] == "sh" for task in tasks),
)
check(
    "every task documents its mode",
    all(
        task["env"]["RENPY_ZED_TASK"]
        in {"run", "warp", "lint", "compile", "dialogue", "rmpersistent"}
        for task in tasks
    ),
)
check(
    "warp tasks pass --warp",
    all(
        "--warp" in " ".join(task["args"])
        for task in tasks
        if task["env"]["RENPY_ZED_TASK"] == "warp"
    ),
)

check("the Ren'Py debugger is registered", 'debuggers = ["renpy"]' in config)
check("the debug adapter is declared", "[debug_adapters.renpy]" in manifest)
check("the debug locator is declared", "[debug_locators.renpy]" in manifest)
schema_path = ROOT / "debug_adapter_schemas" / "renpy.json"
check("the debug adapter schema exists", schema_path.is_file())
schema = json.loads(schema_path.read_text(encoding="utf-8"))
check("the schema requires a request", schema.get("required") == ["request"])
check(
    "the schema only allows launch",
    schema["properties"]["request"].get("enum") == ["launch"],
)
for field in ("sdk", "project", "warp", "command", "args", "env"):
    check(f"the schema documents {field}", field in schema["properties"])

ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
check("CI runs the asset test", "tests/test_extension_assets.py" in ci)
check("CI runs the task test", "tests/test_tasks.py" in ci)

if failures:
    print(f"\n{len(failures)} FAILURE(S)")
    sys.exit(1)
print("\nALL CHECKS PASSED")
