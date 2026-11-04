; Parentheses are part of the opaque `bracketed` token, so they cannot be
; matched as individual bracket tokens here. The grammar does expose [ and ].
("[" @open "]" @close)
