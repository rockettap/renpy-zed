; A run button beside every label. The label name reaches tasks.json as
; $ZED_CUSTOM_renpy_label, and $ZED_ROW points at the label line, so the
; renpy-label task can warp straight to it.
(
  (label_statement
    "label" @run
    name: (label_name) @renpy_label)
  (#set! tag renpy-label)
)
