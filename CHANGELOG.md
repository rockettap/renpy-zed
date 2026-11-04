# Changelog

## 0.2.1 - 2026-11-06

- The run, lint and compile tasks now also look for `renpy-*-sdk` in
  `/Applications`, the standard macOS location, matching what the debug
  adapter already did. Previously this required exporting `RENPY_SDK`.

## 0.2.0 - 2026-11-05

- **Renamed** the extension to `renpy-zed` and the language server to
  `renpy-language-server`. The grammar repository is now
  `renpy-tree-sitter`, and the Zed extension id is `renpy`.
- Diagnostic quick fixes through `renpy-language-server` for comparison typos, stray `$`,
  leading tabs and missing labels, with a `code_actions` setting.
- Signature help through `renpy-language-server` now covers user classes, functions and
  `self.` / `Class.` methods, without showing `self` or `cls`.
- Workspace-wide symbol search through `renpy-language-server` (`workspace/symbol`), with
  exact and prefix matches ranked first and a configurable `workspace_symbols`
  setting.
- Completion can omit image and audio files found on disk through the
  `automatic_assets` setting, while declared images and audio channels remain.
- The snippet library now covers control flow, scene/show/hide, audio,
  assertions, test cases and regions.
- Seven Zed tasks: run, run-from-line, run-from-label, lint, compile, dialogue
  and `rmpersistent`, all sharing the same SDK discovery.
- Launch-only debugging through `renpy-language-server dap` and Zed's DAP integration. The
  debugger starts a project through the Ren'Py SDK, supports `sdk`, `project`,
  `warp`, `command`, `args` and `env`, streams game output into the debug
  console and stops the process on terminate or disconnect. Run tasks gain
  debug variants through a debug locator. Breakpoints, stepping, stack traces,
  variables and attach remain follow-up work.
- Warp targets are validated before launching: the script must exist under the
  project's `game/` directory (or in an `.rpa` archive) and have a label at or
  before the line, and misplaced copies get a suggested `game/...` path.
- Formatter updates through `renpy-language-server`: keyword-argument `=` is tightened and
  single-quoted strings are rewritten to double quotes (values are never
  changed; literals with an unescaped `"` are left alone). Both passes are
  configurable and can be turned off in the language-server settings. Range
  formatting converts a multi-line string only when both delimiters are in the
  selected lines.
- Completion documentation through `renpy-language-server` is now Markdown, so fenced
  signatures and inline code render as code blocks instead of literal
  backticks. Bundled reStructuredText roles and unmatched backticks are
  converted to plain Markdown first.
- Opt-in semantic tokens through `renpy-language-server`: declarations, references,
  bundled and obsolete APIs, keywords, parameters and literals with
  declaration/definition/defaultLibrary/deprecated modifiers. Controlled by the
  `semantic_tokens` setting (default `false`).
- Completion expansion through `renpy-language-server`: labels and screens in every
  statement context, images and `expression`, transforms after `at`,
  transitions after `with`, audio channels/assets/options, `renpy.*` /
  `config.*` / `gui.*` namespaces, screen elements/properties/values, dialogue
  attributes, Python expressions and callable built-ins with `name()`
  insertion.
- Configurable diagnostics through `renpy-language-server`: per-rule `error` / `warning` /
  `off` severity, open-file or whole-workspace modes, and rules for tabs,
  filenames, variable names, comparisons, stray `$`, obsolete APIs, unknown
  images and labels, undefined screens and persistent/store variables, and
  duplicate labels. Newer rules default to `off`.
- Outline and navigation now include Python classes, functions, methods,
  properties, fields, stores, persistent variables, test cases and
  translations. Class and store members are nested in the outline.
- Go to definition and hover follow unambiguous member access (`self.x`,
  `Class.x`, `persistent.x`, `store.x`) and class base names.
- Completion lists class members after `Class.` / `self.`, persistent fields
  after `persistent.`, and variables after `store.`.
- Go to definition through `renpy-language-server` for labels, screens, transforms, images,
  layered images, characters, styles and variables, including local labels.
- Find references across the workspace, with `includeDeclaration` respected.
- Signature help for Ren'Py built-ins and for labels and screens declared with
  parameters.
- Hover through `renpy-language-server` for declarations, references, automatic images and
  Ren'Py built-ins, including signatures, comment documentation and source
  locations.
- Occurrence highlighting through `renpy-language-server`: declarations and references are
  shaded under the cursor and during rename.
- Rename through `renpy-language-server` for labels (global and local), screens, transforms,
  images, characters, styles and `define` / `default` variables, including
  cross-file references and dialogue interpolation. Ren'Py syntax, dialogue
  attributes and screen-local variables are left untouched.
- Added a feature roadmap.

## 0.1.0

- Initial Zed extension for Ren'Py.
- Tree-sitter grammar pinned to `rockettap/renpy-tree-sitter`.
- Highlighting, outline, indentation and Python injection queries.
- Language server launcher for `renpy-language-server` through settings, `PATH`, `uvx`,
  `uv tool run` or `python -m renpy_language_server`.
- Formatting, diagnostics, go to definition, document symbols, completion,
  folding ranges and selection formatting through `renpy-language-server`.
- CI validates Rust, the grammar and every query.
