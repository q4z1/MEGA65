; Smaragd Dash: the entry points of GDash's engine at the start of its block
; ($4000, gdengine.ld), in this order for src/gdfar.s.

.section .gdjump,"ax",@progbits
    jmp gd_start
    jmp gd_iterate
    jmp gd_time_visible
