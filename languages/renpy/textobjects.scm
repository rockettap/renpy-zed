; Text objects for Vim mode. Labels, screens and transforms are the large
; sections (`ac`, `[[`, `]]`, `[]`, `][`); their bodies are `ic`. Menus and
; Python/init blocks are the smaller sections (`af`, `[m`, `]m`) with their
; bodies as `if`.

(label_statement) @class.around
(label_statement
  (block) @class.inside)

(screen_statement) @class.around
(screen_statement
  body: (element_block) @class.inside)

(transform_statement) @class.around
(transform_statement
  body: (atl_block) @class.inside)

(layeredimage_statement) @class.around
(layeredimage_statement
  body: (element_block) @class.inside)

(testcase_statement) @class.around
(testcase_statement
  body: (element_block) @class.inside)

(style_statement
  body: (element_block) @class.inside) @class.around

(menu_statement) @function.around

(python_block) @function.around
(python_block
  (indented_block) @function.inside)

(init_statement) @function.around
(init_statement
  (indented_block) @function.inside)
