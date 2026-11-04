#!/usr/bin/env bash
# Validate the Zed queries against the grammar revision pinned in extension.toml.
#
# For local development, point RENPY_GRAMMAR_DIR at a grammar checkout to skip
# the network:
#   RENPY_GRAMMAR_DIR=../renpy-tree-sitter scripts/check-grammar.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI_VERSION="0.25.10"
TS=(npx --yes "tree-sitter-cli@${CLI_VERSION}")

TMP_DIR=""
OUTPUT="$(mktemp)"
cleanup() {
    rm -f "${OUTPUT}"
    if [[ -n "${TMP_DIR}" ]]; then
        rm -rf "${TMP_DIR}"
    fi
}
trap cleanup EXIT

if [[ -n "${RENPY_GRAMMAR_DIR:-}" ]]; then
    GRAMMAR_DIR="${RENPY_GRAMMAR_DIR}"
else
    REPOSITORY="$(awk -F'"' '/^\[grammars\.renpy\]/{in_section=1; next} /^\[/{in_section=0} in_section && $1 ~ /^repository[[:space:]]*=/ {print $2; exit}' "${ROOT}/extension.toml")"
    REVISION="$(awk -F'"' '/^\[grammars\.renpy\]/{in_section=1; next} /^\[/{in_section=0} in_section && ($1 ~ /^rev[[:space:]]*=/ || $1 ~ /^commit[[:space:]]*=/) {print $2; exit}' "${ROOT}/extension.toml")"

    if [[ -z "${REPOSITORY}" || -z "${REVISION}" ]]; then
        echo "Could not read [grammars.renpy] repository/rev from extension.toml" >&2
        exit 1
    fi

    TMP_DIR="$(mktemp -d)"
    GRAMMAR_DIR="${TMP_DIR}/grammar"
    git init -q "${GRAMMAR_DIR}"
    git -C "${GRAMMAR_DIR}" remote add origin "${REPOSITORY}"
    git -C "${GRAMMAR_DIR}" fetch --quiet --depth 1 origin "${REVISION}"
    git -C "${GRAMMAR_DIR}" checkout --quiet FETCH_HEAD
fi

if [[ ! -f "${GRAMMAR_DIR}/grammar.js" ]]; then
    echo "No grammar.js in ${GRAMMAR_DIR}" >&2
    exit 1
fi

cd "${GRAMMAR_DIR}"

for fixture in "${ROOT}"/tests/fixtures/*.rpy; do
    if ! "${TS[@]}" parse "${fixture}" >"${OUTPUT}" 2>&1; then
        echo "Parse failed: ${fixture}" >&2
        cat "${OUTPUT}" >&2
        exit 1
    fi
    if grep -qE '(ERROR|MISSING)' "${OUTPUT}"; then
        echo "Parse tree contains ERROR/MISSING: ${fixture}" >&2
        cat "${OUTPUT}" >&2
        exit 1
    fi
done

for query in highlights injections indents outline brackets textobjects overrides runnables; do
    if ! "${TS[@]}" query "${ROOT}/languages/renpy/${query}.scm" \
        "${ROOT}/tests/fixtures/smoke.rpy" >/dev/null 2>"${OUTPUT}"; then
        echo "Query failed to compile: ${query}.scm" >&2
        cat "${OUTPUT}" >&2
        exit 1
    fi
done

echo "Grammar and queries OK"
