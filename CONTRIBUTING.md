# Contributing

## Layout

The extension, grammar and server are separate repositories:

- `renpy-zed` (this repository): Zed extension, queries and launcher
- `renpy-tree-sitter`: grammar, parser tests and examples
- `renpy-language-server`: language server and formatter

## Local checks

Extension:

```bash
cargo fmt --check
cargo clippy --target wasm32-wasip2 -- -D warnings
cargo test --lib
cargo build --release --target wasm32-wasip2
```

Declarative assets and runnable tasks:

```bash
python3 tests/test_extension_assets.py
python3 tests/test_tasks.py
```

Queries against the pinned grammar:

```bash
scripts/check-grammar.sh
# or, with a local grammar checkout:
RENPY_GRAMMAR_DIR=../renpy-tree-sitter scripts/check-grammar.sh
```

Grammar:

```bash
cd ../renpy-tree-sitter
npx --yes tree-sitter-cli@0.25.10 generate
npx --yes tree-sitter-cli@0.25.10 test
npx --yes tree-sitter-cli@0.25.10 parse examples/smoke.rpy
```

Server:

```bash
cd ../renpy-language-server
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyright
```

## Changing the grammar

1. Land the grammar change in `renpy-tree-sitter` and commit the regenerated
   `src/`.
2. Update the `rev` in `extension.toml` to that commit.
3. Update `languages/renpy/*.scm` if node names or fields changed.
4. Run `scripts/check-grammar.sh` and the Rust build.

A stale node name makes an entire query file fail to compile; Zed then shows no
highlighting at all.

## Pull requests

Keep changes focused. Include the commands you ran and, for query changes, the
fixture or project that exercises the change.
