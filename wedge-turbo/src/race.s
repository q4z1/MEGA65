; Wedge Turbo: the race logic in 45GS02 assembly - the same as ref/race.c,
; which stays the reference: tests/check_race.c checks this against it on
; the MEGA65. The comments name race.c's functions; see there for what they
; do.
;
; A player is moved in a copy at a fixed place (CUR), so every field has an
; absolute address; player_frame copies it there and back. The math unit
; multiplies (signed products: sign-extended operands, the low 32 bits) and
; divides.
;
; Scratch: llvm-mos' caller-saved registers __rc2-__rc19. Z is 0 whenever
; C code runs (llvm-mos stores zeros with STZ); the Q instructions use it,
; so every routine C calls ends with ldz #0.

.include "offsets.inc"

.global race_frame, race_picture, race_random, race_init, race_track_setup

; zero page scratch
t0 = __rc2          ; 4 bytes
t1 = __rc6          ; 4 bytes
t2 = __rc10         ; 4 bytes
t3 = __rc14         ; 4 bytes
pp = __rc18         ; pointer

; the math unit
MULTINA = $D770
MULTINB = $D774
MULTOUT = $D778
DIVOUT  = $D76C     ; integer part of MULTINA / MULTINB
MATHBUSY = $D70F    ; bit 7: the divider is busy

; the player being moved
CUR_x            = cur + P_x
CUR_pos          = cur + P_pos
CUR_speed        = cur + P_speed
CUR_steer        = cur + P_steer
CUR_curve        = cur + P_curve
CUR_u16          = cur + P_u16
CUR_in_pits      = cur + P_in_pits
CUR_slope        = cur + P_slope
CUR_stopped      = cur + P_stopped
CUR_cam_pos      = cur + P_cam_pos
CUR_cam_x        = cur + P_cam_x
CUR_x_view       = cur + P_x_view
CUR_pos_view     = cur + P_pos_view
CUR_slope_view   = cur + P_slope_view
CUR_speed_view   = cur + P_speed_view
CUR_automatic    = cur + P_automatic
CUR_push_x       = cur + P_push_x
CUR_push_steer   = cur + P_push_steer
CUR_fuel         = cur + P_fuel
CUR_place        = cur + P_place
CUR_colours      = cur + P_colours
CUR_accelerating = cur + P_accelerating
CUR_gear         = cur + P_gear
CUR_rpm          = cur + P_rpm
CUR_pit_request  = cur + P_pit_request
CUR_pit_lane     = cur + P_pit_lane
CUR_joy          = cur + P_joy
CUR_joy_new      = cur + P_joy_new
CUR_fire_accel   = cur + P_fire_accel
CUR_pit_timer    = cur + P_pit_timer

P0 = race + R_p
P1 = race + R_p + PLAYER_SIZE

JOY_LEFT  = $01
JOY_RIGHT = $02
JOY_DOWN  = $04
JOY_UP    = $08
JOY_FIRE  = $10

.section .bss.race_s,"aw",@nobits
cur:        .fill PLAYER_SIZE
cur_n:      .fill 1         ; which player is in cur
none_seg:   .fill 16        ; the "segment" in front of the course: zeros
rpm_tmp:    .fill 2         ; drive's engine speed

.section .text.race_s,"ax",@progbits

; ---------------------------------------------------------------- helpers

; seg_of: A/X = high word of a position -> A/X = segment number, $FFFF
; in front of the course (a negative position)
seg_of:
    cpx #$80
    bcs 3f
    sta t3
    stx t3 + 1
1:
    lda t3
    sec
    sbc race + R_segments
    tay
    lda t3 + 1
    sbc race + R_segments + 1
    bcc 2f
    sty t3
    sta t3 + 1
    bra 1b
2:
    lda t3
    ldx t3 + 1
    rts
3:
    lda #$FF
    tax
    rts

; seg_ptr: A/X = segment number -> pp = the segment (none_seg for $FFFF)
seg_ptr:
    cpx #$80
    bcs 1f
    sta pp
    stx pp + 1
    asl pp
    rol pp + 1
    asl pp
    rol pp + 1
    asl pp
    rol pp + 1
    asl pp
    rol pp + 1
    clc
    lda pp
    adc race_track
    tax
    lda pp + 1
    adc race_track + 1
    tay
    txa
    clc
    adc #TRACK_SEGMENTS
    sta pp
    tya
    adc #0
    sta pp + 1
    rts
1:
    lda #<none_seg
    sta pp
    lda #>none_seg
    sta pp + 1
    rts

; segment: A/X = high word of a position -> pp = its segment
segment:
    jsr seg_of
    jmp seg_ptr

; Signed 16 x 16 multiplication: set_ma / set_mb load the operands from
; A (low) and X (high), sign-extended; the product is at MULTOUT
set_ma:
    sta MULTINA
    stx MULTINA + 1
    lda #0
    cpx #$80
    bcc 1f
    lda #$FF
1:
    sta MULTINA + 2
    sta MULTINA + 3
    rts

set_mb:
    sta MULTINB
    stx MULTINB + 1
    lda #0
    cpx #$80
    bcc 1f
    lda #$FF
1:
    sta MULTINB + 2
    sta MULTINB + 3
    rts

; Unsigned: the high words 0
set_mb_u:
    sta MULTINB
    stx MULTINB + 1
    lda #0
    sta MULTINB + 2
    sta MULTINB + 3
    rts

; rpm_of: (t0 word) << 16 / (t1 word), as divu: 0 when the
; quotient does not fit (t0 >= t1) -> A/X
rpm_of:
    lda t0
    cmp t1
    lda t0 + 1
    sbc t1 + 1
    bcs 2f
    lda #0
    sta MULTINA
    sta MULTINA + 1
    sta MULTINB + 2
    sta MULTINB + 3
    lda t0
    sta MULTINA + 2
    lda t0 + 1
    sta MULTINA + 3
    lda t1
    sta MULTINB
    lda t1 + 1
    sta MULTINB + 1
1:
    bit MATHBUSY
    bmi 1b
    lda DIVOUT
    ldx DIVOUT + 1
    rts
2:
    lda #0
    tax
    rts

; ---------------------------------------------------------------- race_random

; four long words, each added with carry to the sum so far and a constant:
; ADCQ adds with the carry, through all four words
race_random:
    lda #0
    tax
    tay
    taz
    clc
    adcq mos16(race + R_random)
    adcq mos16(rnd_k)
    stq mos16(race + R_random)
    adcq mos16(race + R_random + 4)
    adcq mos16(rnd_k + 4)
    stq mos16(race + R_random + 4)
    adcq mos16(race + R_random + 8)
    adcq mos16(rnd_k + 8)
    stq mos16(race + R_random + 8)
    adcq mos16(race + R_random + 12)
    adcq mos16(rnd_k + 12)
    stq mos16(race + R_random + 12)
    ldz #0
    rts

.section .rodata.race_s,"a",@progbits
rnd_k:
    .long $7362541F, $7FBE6475, $83265984, $F0293747
.section .text.race_s,"ax",@progbits

; ---------------------------------------------------------------- seg_lookup

; seg_lookup: the course at position t2 (4 bytes) for the player in cur:
; curve, slope, u16 and the colours of the scenery 7 segments ahead
seg_lookup:
    lda t2 + 2
    ldx t2 + 3
    jsr seg_of
    sta t3 + 2              ; segment number, kept for the one 7 on
    stx t3 + 3
    jsr seg_ptr
    ; way = (pos & $FFFF) >> 4
    lda t2 + 1
    sta t1 + 1
    lda t2
    sta t1
    lsr t1 + 1
    ror t1
    lsr t1 + 1
    ror t1
    lsr t1 + 1
    ror t1
    lsr t1 + 1
    ror t1
    ; slope = -(((hill + hill as a byte) * way >> 8) + spare1 * 32)
    ldy #1
    lda (pp), y
    asl
    ldx #0
    cmp #$80
    bcc 1f
    dex
1:
    jsr set_ma
    lda t1
    ldx t1 + 1
    jsr set_mb
    ldy #13
    lda (pp), y
    jsr times32             ; -> t0 word
    clc
    lda MULTOUT + 1
    adc t0
    sta t0
    lda MULTOUT + 2
    adc t0 + 1
    sta t0 + 1
    sec
    lda #0
    sbc t0
    sta CUR_slope
    lda #0
    sbc t0 + 1
    sta CUR_slope + 1
    ; curve = curve * 2 (a word); u16 = -((curve * 2 * way >> 8) + spare0 * 32)
    ldy #0
    lda (pp), y
    ldx #0
    cmp #$80
    bcc 1f
    dex
1:
    asl
    pha
    txa
    rol
    tax
    pla
    sta CUR_curve
    stx CUR_curve + 1
    jsr set_ma
    ldy #12
    lda (pp), y
    jsr times32
    clc
    lda MULTOUT + 1
    adc t0
    sta t0
    lda MULTOUT + 2
    adc t0 + 1
    sta t0 + 1
    sec
    lda #0
    sbc t0
    sta cur + P_u16
    lda #0
    sbc t0 + 1
    sta cur + P_u16 + 1
    ; the object 7 segments on, in this quarter (pos >> 14 & 3)
    clc
    lda t3 + 2
    adc #7
    tay
    lda t3 + 3
    adc #0
    tax
    tya
    jsr seg_ptr
    lda t2 + 1
    lsr
    lsr
    lsr
    lsr
    lsr
    and #$06
    clc
    adc #2
    tay
    lda (pp), y             ; object[q].type
    beq 2f
    ; tab_object_colours + (type - $80) * 8
    sec
    sbc #$80
    sta pp
    lda #0
    sta pp + 1
    asl pp
    rol pp + 1
    asl pp
    rol pp + 1
    asl pp
    rol pp + 1
    clc
    lda pp
    adc #<tab_object_colours
    sta pp
    lda pp + 1
    adc #>tab_object_colours
    sta pp + 1
    ldy #0
    ldx #0
1:
    lda (pp), y
    iny
    ora (pp), y
    beq 3f
    dey
    lda (pp), y
    sta CUR_colours, x
    iny
    lda (pp), y
    sta CUR_colours + 1, x
3:
    iny
    inx
    inx
    cpx #8
    bne 1b
2:
    rts

; times32: t0 = A (a signed byte) * 32, as a word
times32:
    ldx #0
    cmp #$80
    bcc 1f
    dex
1:
    stx t0 + 1
    asl
    rol t0 + 1
    asl
    rol t0 + 1
    asl
    rol t0 + 1
    asl
    rol t0 + 1
    asl
    rol t0 + 1
    sta t0
    rts

; seg_here: the course where the player in cur (or its camera) is
seg_here:
    bit race + R_clock + 1
    bmi 1f
    ldz #0
    lda CUR_stopped
    ora CUR_stopped + 1
    beq 2f
    lda CUR_fuel
    ora CUR_fuel + 1
    ora CUR_fuel + 2
    ora CUR_fuel + 3
    beq 2f
    lda CUR_place + 1
    bne 2f
    lda CUR_place
    cmp #11
    bcs 2f
1:
    ldq mos16(CUR_cam_pos)
    bra 3f
2:
    ldq mos16(CUR_pos)
3:
    stq t2
    ldz #0
    jmp seg_lookup

; ---------------------------------------------------------------- small helpers

; Q from / to I/O registers byte by byte: 32-bit accesses do not reach
; the math unit's registers (not in Xemu at least)
.macro ldq_io a
    ldz \a + 3
    ldy \a + 2
    ldx \a + 1
    lda \a
.endm

.macro stq_io a
    sta \a
    stx \a + 1
    sty \a + 2
    stz \a + 3
.endm

; 16-bit increment of an absolute word
.macro inw_abs a
    inc \a
    bne .Linw\@
    inc \a + 1
.Linw\@:
.endm

; sext0: t0 + 2/3 = the sign of the word in t0
sext0:
    lda #0
    bit t0 + 1
    bpl 1f
    lda #$FF
1:
    sta t0 + 2
    sta t0 + 3
    rts

; Signed 16-bit compare of the word at addr with imm: N set if less
.macro scmp addr, imm
    lda \addr
    cmp #<(\imm)
    lda \addr + 1
    sbc #>(\imm)
    bvc .Lscmp\@
    eor #$80
.Lscmp\@:
.endm

; ---------------------------------------------------------------- move

move:
    ; pos += speed (sign-extended)
    lda CUR_speed
    sta t0
    lda CUR_speed + 1
    sta t0 + 1
    jsr sext0
    ldq mos16(CUR_pos)
    clc
    adcq t0
    stq mos16(CUR_pos)
    ldq mos16(CUR_x)
    stq t2                      ; x
    ldz #0
    lda CUR_push_x
    ora CUR_push_x + 1
    beq 1f
    jmp 9f
1:
    ; s: the speed, softened
    lda CUR_speed
    sta t1
    lda CUR_speed + 1
    sta t1 + 1
    lda CUR_accelerating
    ora CUR_accelerating + 1
    beq 2f
    lda t1 + 1
    cmp #$0A
    bcc 2f
    sec                         ; s = (s - $A00) / 2 + $A00
    sbc #$0A
    lsr
    sta t1 + 1
    ror t1
    clc
    lda t1 + 1
    adc #$0A
    sta t1 + 1
2:
    lda t1 + 1
    cmp #$0A
    bcs 3f
    clc                         ; s = (s + $A00) >> 1
    adc #$0A
    lsr
    sta t1 + 1
    ror t1
3:
    ; d = speed_view - s; if d >= 0: scrape = |d * steer| (a word) >> 5
    sec
    lda CUR_speed_view
    sbc t1
    tay
    lda CUR_speed_view + 1
    sbc t1 + 1
    bmi 4f
    tax
    tya
    jsr set_ma
    lda CUR_steer
    ldx CUR_steer + 1
    jsr set_mb
    lda MULTOUT
    ldx MULTOUT + 1
    bit MULTOUT + 3
    bpl 5f
    eor #$FF                    ; negate the word
    clc
    adc #1
    pha
    txa
    eor #$FF
    adc #0
    tax
    pla
5:
    stx t0 + 1
    lsr t0 + 1
    ror
    lsr t0 + 1
    ror
    lsr t0 + 1
    ror
    lsr t0 + 1
    ror
    lsr t0 + 1
    ror
    sta race + R_scrape
    lda t0 + 1
    sta race + R_scrape + 1
4:
    ; x += 5 * (s * steer)
    lda t1
    ldx t1 + 1
    jsr set_ma
    lda CUR_steer
    ldx CUR_steer + 1
    jsr set_mb
    ldq_io MULTOUT
    stq t0
    aslq
    aslq
    clc
    adcq t0
    clc
    adcq t2
    stq t2
    ldz #0
9:
    ; x += curve * 12 * speed
    lda CUR_curve
    sta t0
    lda CUR_curve + 1
    sta t0 + 1
    asl t0                      ; * 3 * 4: (c + 2c) << 2
    rol t0 + 1
    clc
    lda t0
    adc CUR_curve
    tay
    lda t0 + 1
    adc CUR_curve + 1
    tax
    tya
    asl
    pha
    txa
    rol
    tax
    pla
    asl
    pha
    txa
    rol
    tax
    pla
    jsr set_ma
    lda CUR_speed
    ldx CUR_speed + 1
    jsr set_mb
    ldq_io MULTOUT
    clc
    adcq t2
    stq t2
    ; x += push_x << 15
    lda #0
    tax
    ldy CUR_push_x
    ldz CUR_push_x + 1
    asrq
    clc
    adcq t2
    stq t2
    ldz #0
    ; keep x within -$180 .. $17F (the fraction's word
    ; on the left)
    scmp t2 + 2, -$180
    bpl 6f
    lda #$FF
    sta CUR_x
    sta CUR_x + 1
    lda #$80
    sta CUR_x + 2
    lda #$FE
    sta CUR_x + 3
    rts
6:
    scmp t2 + 2, $180
    bmi 7f
    lda #0
    sta CUR_x
    sta CUR_x + 1
    sta CUR_x + 3
    lda #$80
    sta CUR_x + 2
    lda #1
    sta CUR_x + 3
    rts
7:
    ldq t2
    stq mos16(CUR_x)
    ldz #0
    rts

; ---------------------------------------------------------------- burn (fuel)

burn:
    lda CUR_stopped
    ora CUR_stopped + 1
    bne 9f
    ; use = (max(rpm - 5000, 0) + rpm) << 6
    sec
    lda CUR_rpm
    sbc #<5000
    tay
    lda CUR_rpm + 1
    sbc #>5000
    bpl 1f
    lda #0
    tay
1:
    tax
    tya
    clc
    adc CUR_rpm
    sta t0
    txa
    adc CUR_rpm + 1
    sta t0 + 1
    lda #0
    sta t0 + 2
    sta t0 + 3
    ldq t0
    aslq
    aslq
    aslq
    aslq
    aslq
    aslq
    stq t0
    ldq mos16(CUR_fuel)
    sec
    sbcq t0
    bcs 2f
    lda #0
    tax
    tay
    taz
2:
    stq mos16(CUR_fuel)
    ldz #0
9:
    rts

; ---------------------------------------------------------------- pit_check

pit_check:
    lda CUR_fuel
    ora CUR_fuel + 1
    ora CUR_fuel + 2
    ora CUR_fuel + 3
    beq 1f
    lda CUR_stopped
    ora CUR_stopped + 1
    bne 9f
1:
    lda cur + P_pos_view + 2
    ldx cur + P_pos_view + 3
    jsr segment
    lda #0
    sta CUR_pit_lane
    sta CUR_pit_lane + 1
    ldy #11
    lda (pp), y                 ; variant: the wide road (pit lane)
    beq 9f
    lda #1
    sta CUR_pit_lane
    scmp CUR_x_view + 2, $E8
    bmi 9f
    scmp CUR_x_view + 2, $138
    bpl 9f
    lda CUR_speed_view
    cmp #<$42A
    lda CUR_speed_view + 1
    sbc #>$42A
    bcs 9f
    lda CUR_joy
    and #JOY_DOWN
    beq 9f
    lda CUR_pit_timer
    ora CUR_pit_timer + 1
    bne 9f
    lda #1
    sta CUR_pit_request
    lda #0
    sta CUR_pit_request + 1
    sta CUR_gear
    sta CUR_gear + 1
    sta CUR_speed
    sta CUR_speed + 1
    sta CUR_pit_timer + 1
    lda #25
    sta CUR_pit_timer
9:
    rts

; ---------------------------------------------------------------- in_pits

; the accelerator: fire or forward (fire_accel), A = its bit in joy (Z)
accel_bit:
    lda CUR_fire_accel
    ora CUR_fire_accel + 1
    beq 1f
    lda #JOY_FIRE
    rts
1:
    lda #JOY_UP
    rts

in_pits:
    jsr accel_bit
    and CUR_joy
    beq 1f
    lda CUR_pit_timer
    ora CUR_pit_timer + 1
    bne 1f
    lda #0
    sta CUR_pit_request
    sta CUR_pit_request + 1
    sta CUR_pit_timer + 1
    lda #25
    sta CUR_pit_timer
1:
    lda CUR_fuel
    ora CUR_fuel + 1
    ora CUR_fuel + 2
    ora CUR_fuel + 3
    bne 2f
    lda #0
    sta CUR_stopped
    sta CUR_stopped + 1
2:
    ; refuel: $80 onto the high word, full on overflow
    clc
    lda CUR_fuel + 2
    adc #$80
    sta CUR_fuel + 2
    lda CUR_fuel + 3
    adc #0
    sta CUR_fuel + 3
    bcc 3f
    lda #$FF
    sta CUR_fuel
    sta CUR_fuel + 1
    sta CUR_fuel + 2
    sta CUR_fuel + 3
3:
    rts

; ---------------------------------------------------------------- timers

timers:
    lda CUR_pit_timer
    ora CUR_pit_timer + 1
    beq 1f
    lda CUR_pit_timer
    bne 2f
    dec CUR_pit_timer + 1
2:
    dec CUR_pit_timer
1:
    lda CUR_pit_request + 1
    bmi 3f
    sta CUR_in_pits + 1
    lda CUR_pit_request
    sta CUR_in_pits
    lda #$FF
    sta CUR_pit_request
    sta CUR_pit_request + 1
3:
    rts

; ---------------------------------------------------------------- push

; push: a crash - push_x = strength (A/X), steer -8, both negated when the
; obstacle was on the right (side, the word at t1, >= 0); hit = 1
push:
    sta t0
    stx t0 + 1
    lda #1
    sta race + R_hit
    lda #0
    sta race + R_hit + 1
    lda #$F8
    ldx #$FF
    bit t1 + 1
    bmi 1f
    sec                         ; strength = -strength, steer = 8
    lda #0
    sbc t0
    sta t0
    lda #0
    sbc t0 + 1
    sta t0 + 1
    lda #8
    ldx #0
1:
    sta CUR_push_steer
    stx CUR_push_steer + 1
    lda t0
    sta CUR_push_x
    lda t0 + 1
    sta CUR_push_x + 1
    rts

; ---------------------------------------------------------------- hit_scenery

hit_scenery:
    lda #0
    sta race + R_hit
    sta race + R_hit + 1
    ; pos + $2000: nothing in the second half of an eighth
    clc
    lda CUR_pos + 1
    adc #$20
    sta t2 + 1
    lda CUR_pos + 2
    adc #0
    sta t2 + 2
    lda CUR_pos + 3
    adc #0
    sta t2 + 3
    lda t2 + 1
    and #$20
    beq 1f
    rts
1:
    lda t2 + 2
    ldx t2 + 3
    jsr segment
    lda t2 + 1                  ; quarter * 2 + 2: the object's type
    lsr
    lsr
    lsr
    lsr
    lsr
    and #$06
    clc
    adc #2
    tay
    lda (pp), y
    bne 2f
    rts
2:
    sta t3                      ; type
    iny
    lda (pp), y                 ; its x * 16 - px -> d (t1)
    ldx #0
    cmp #$80
    bcc 3f
    dex
3:
    stx t1 + 1
    asl
    rol t1 + 1
    asl
    rol t1 + 1
    asl
    rol t1 + 1
    asl
    rol t1 + 1
    sec
    sbc CUR_x + 2
    sta t1
    lda t1 + 1
    sbc CUR_x + 3
    sta t1 + 1
    ldx t3
    lda tab_object_width - $80, x
    bne 6f
    ; a gate: its posts at -$120 and $120
    sec
    lda #<(-$120 + $28)
    sbc CUR_x + 2
    sta t0
    lda #>(-$120 + $28)
    sbc CUR_x + 3
    cmp #0
    bne 4f
    lda t0
    cmp #$50
    bcs 4f
    sec                         ; the left post: d = -$120 - px
    lda #<(-$120)
    sbc CUR_x + 2
    sta t1
    lda #>(-$120)
    sbc CUR_x + 3
    sta t1 + 1
    jmp crash
4:
    sec
    lda #<($120 + $28)
    sbc CUR_x + 2
    sta t0
    lda #>($120 + $28)
    sbc CUR_x + 3
    bne 5f
    lda t0
    cmp #$50
    bcs 5f
    sec
    lda #<$120
    sbc CUR_x + 2
    sta t1
    lda #>$120
    sbc CUR_x + 3
    sta t1 + 1
    jmp crash
5:
    rts
6:
    ; half = (w + $40) >> 1; hit if d + half < 2 * half (unsigned)
    clc
    adc #$40
    sta t0
    lda #0
    rol
    lsr
    ror t0                      ; half (a byte: w <= 136)
    clc
    lda t1
    adc t0
    sta t0 + 2
    lda t1 + 1
    adc #0
    sta t0 + 3                  ; d + half
    lda t0
    asl
    sta t2
    lda #0
    rol
    sta t2 + 1                  ; 2 * half
    lda t0 + 2
    cmp t2
    lda t0 + 3
    sbc t2 + 1
    bcc 7f
    rts
7:
    lda t3
    cmp #$A2
    bne 8f
    ; $A2: noise and a push to the side, no loss of speed
    lda #$00
    sta race + R_scrape
    lda #$60
    sta race + R_scrape + 1
    lda CUR_push_steer
    ora CUR_push_steer + 1
    bne 9f
    lda CUR_speed + 1           ; strength (speed >> 9) + $10
    lsr
    clc
    adc #$10
    ldx #0
    jsr push
    lda #0                      ; push set hit: not for this one
    sta race + R_hit
9:
    rts
8:
    cmp #$A3
    bne crash
    ; $A3: slows down above $D55
    sec
    lda CUR_speed
    sbc #<$D55
    sta t0
    lda CUR_speed + 1
    sbc #>$D55
    bmi 9b
    lsr
    ror t0
    sta t0 + 1
    sec
    lda CUR_speed
    sbc t0
    sta CUR_speed
    lda CUR_speed + 1
    sbc t0 + 1
    sta CUR_speed + 1
    rts

; crash: half the speed, pushed away from the side in t1 with strength
; (old speed >> 9) + $10 = (new speed >> 8) + $10
crash:
    lsr CUR_speed + 1
    ror CUR_speed
    lda CUR_speed + 1
    clc
    adc #$10
    ldx #0
    jmp push

; Signed 32-bit compare of a with b (4 bytes each): N set if a < b
.macro scmp32 a, b
    lda \a
    cmp \b
    lda \a + 1
    sbc \b + 1
    lda \a + 2
    sbc \b + 2
    lda \a + 3
    sbc \b + 3
    bvc .Lscmp32\@
    eor #$80
.Lscmp32\@:
.endm

; 32-bit a += b, a -= b (a, b: addresses of 4 bytes, absolute or zero page)
.macro add32 a, b
    clc
    lda \a
    adc \b
    sta \a
    lda \a + 1
    adc \b + 1
    sta \a + 1
    lda \a + 2
    adc \b + 2
    sta \a + 2
    lda \a + 3
    adc \b + 3
    sta \a + 3
.endm

.macro sub32 a, b
    sec
    lda \a
    sbc \b
    sta \a
    lda \a + 1
    sbc \b + 1
    sta \a + 1
    lda \a + 2
    sbc \b + 2
    sta \a + 2
    lda \a + 3
    sbc \b + 3
    sta \a + 3
.endm

; ---------------------------------------------------------------- hit_opponents

hit_opponents:
    lda #0
    sta race + R_hit
    sta race + R_hit + 1
    sta t3                      ; lap = segments << 16
    sta t3 + 1
    lda race + R_segments
    sta t3 + 2
    lda race + R_segments + 1
    sta t3 + 3
    ldq mos16(CUR_pos)          ; from = pos - $2000, to = pos + $2000
    stq t0
    stq t1
    ldz #0
    sec
    lda t0 + 1
    sbc #$20
    sta t0 + 1
    bcs 1f
    lda t0 + 2
    bne 2f
    dec t0 + 3
2:
    dec t0 + 2
1:
    clc
    lda t1 + 1
    adc #$20
    sta t1 + 1
    bcc 3f
    inc t1 + 2
    bne 3f
    inc t1 + 3
3:
    ; while from >= opp[0].pos: a lap back
4:
    scmp32 t0, race + R_opp + O_pos
    bmi 5f
    sub32 t0, t3
    sub32 t1, t3
    bra 4b
5:
    ; while to < the last opponent's pos: a lap on
    lda race + R_opponents      ; pp = the last opponent
    sec
    sbc #1
    jsr opp_ptr
6:
    ldy #3
7:
    lda (pp), y
    sta t2, y
    dey
    bpl 7b
    scmp32 t1, t2
    bpl 8f
    add32 t0, t3
    add32 t1, t3
    bra 6b
8:
    ; the opponents, ahead first
    lda #0
    jsr opp_ptr
    ldx race + R_opponents
9:
    phx
    ldy #3                      ; d = its pos
10:
    lda (pp), y
    sta t2, y
    dey
    bpl 10b
    scmp32 t2, t0               ; behind the window: done
    bpl 11f
    plx
    rts
11:
    sub32 t2, t1                ; d -= to: ahead of the window -> the next
    bit t2 + 3
    bmi 12f
    clc
    lda pp
    adc #OPPONENT_SIZE
    sta pp
    bcc 13f
    inc pp + 1
13:
    plx
    dex
    bne 9b
    rts
12:
    plx
    ; dx = its x - px, only within $40
    ldy #O_x
    sec
    lda (pp), y
    sbc CUR_x + 2
    sta t1
    iny
    lda (pp), y
    sbc CUR_x + 3
    sta t1 + 1
    scmp t1, -$40
    bpl 14f
    rts
14:
    scmp t1, $40
    bmi 15f
    rts
15:
    ; d += $2000: d >= 0 and slower -> into its back
    clc
    lda t2 + 1
    adc #$20
    sta t2 + 1
    bcc 16f
    inc t2 + 2
    bne 16f
    inc t2 + 3
16:
    bit t2 + 3
    bmi side
    ldy #O_speed
    lda (pp), y
    cmp CUR_speed
    iny
    lda (pp), y
    sbc CUR_speed + 1
    bcs side
    ; into its back: pos += d - $2000, 0.625 of the speed
    sec
    lda t2 + 1
    sbc #$20
    sta t2 + 1
    bcs 17f
    lda t2 + 2
    bne 18f
    dec t2 + 3
18:
    dec t2 + 2
17:
    add32 CUR_pos, t2
    lda CUR_speed + 1           ; strength: (old speed >> 11) + $10
    lsr
    lsr
    lsr
    clc
    adc #$10
    pha
    lda CUR_speed
    ldx CUR_speed + 1
    jsr times_a000
    pla
    ldx #0
    jmp push
side:
    ; side by side: it moves away, to $40 from the car
    ldy #O_dx + 1
    lda (pp), y
    bit t1 + 1
    bmi 19f
    tax                         ; on the right: dx >= 0
    bpl 20f
    jsr neg_dx
20:
    lda #$40
    ldx #0
    bra 21f
19:
    tax                         ; on the left: dx < 0
    bmi 22f
    jsr neg_dx
22:
    lda #$C0
    ldx #$FF
21:
    clc
    adc CUR_x + 2
    ldy #O_x
    sta (pp), y
    txa
    adc CUR_x + 3
    iny
    sta (pp), y
    rts

; neg_dx: the dx of the opponent at pp negated
neg_dx:
    ldy #O_dx
    sec
    lda #0
    sbc (pp), y
    sta (pp), y
    iny
    lda #0
    sbc (pp), y
    sta (pp), y
    rts

; opp_ptr: pp = &race.opp[A]
opp_ptr:
    sta pp
    lda #0
    sta pp + 1
    lda pp                      ; * 12 = * 4 * 3
    asl
    rol pp + 1
    asl
    rol pp + 1
    sta pp
    ldx pp + 1
    asl
    rol pp + 1
    clc
    adc pp
    sta pp
    txa
    adc pp + 1
    sta pp + 1
    clc
    lda pp
    adc #<(race + R_opp)
    sta pp
    lda pp + 1
    adc #>(race + R_opp)
    sta pp + 1
    rts

; times_a000: CUR_speed = (A/X * $A000) >> 16
times_a000:
    jsr set_ma
    lda #0
    sta MULTINA + 2
    sta MULTINA + 3
    sta MULTINB
    sta MULTINB + 2
    sta MULTINB + 3
    lda #$A0
    sta MULTINB + 1
    lda MULTOUT + 2
    sta CUR_speed
    lda MULTOUT + 3
    sta CUR_speed + 1
    rts

; ---------------------------------------------------------------- hit_other

; hit_other: the other player's car (pp = that Player)
hit_other:
    lda #0
    sta race + R_hit
    sta race + R_hit + 1
    ldy #P_x + 2                ; dx = its x - px, only within $40
    sec
    lda (pp), y
    sbc CUR_x + 2
    sta t1
    iny
    lda (pp), y
    sbc CUR_x + 3
    sta t1 + 1
    scmp t1, -$40
    bpl 1f
    rts
1:
    scmp t1, $40
    bmi 2f
    rts
2:
    ; d = its pos - pos
    ldy #P_pos
    ldx #0
3:
    lda (pp), y
    sta t2, x
    iny
    inx
    cpx #4
    bne 3b
    sub32 t2, CUR_pos
    ; the segments between, modulo the course: (hi(d) + seg_bias) mod
    ; segments must be 0 (negative: the division overflows)
    lda t2 + 2
    sta t0
    lda t2 + 3
    sta t0 + 1
    jsr sext0
    add32 t0, race + R_seg_bias
    bit t0 + 3
    bpl 4f
    rts
4:
    ldq t0
    stq_io MULTINA
    lda race + R_segments
    ldx race + R_segments + 1
    jsr set_mb_u
5:
    bit MATHBUSY
    bmi 5b
    ldq_io DIVOUT               ; q * segments == v: the remainder 0
    stq_io MULTINA
    ldq_io MULTOUT
    cpq t0
    php                         ; (ldz changes the flags)
    ldz #0
    plp
    beq 6f
    rts
6:
    lda t2 + 1                  ; and the low word < $2000
    cmp #$20
    bcc 7f
    rts
7:
    ; player 2 is moved back by $2000 - d, whichever car this is
    sec
    lda t2 + 1
    sbc #$20
    sta t2 + 1
    lda #$FF
    sta t2 + 2
    sta t2 + 3
    lda cur_n
    beq 8f
    add32 CUR_pos, t2
    bra 9f
8:
    add32 P1 + P_pos, t2
9:
    lda CUR_speed
    ldx CUR_speed + 1
    jsr times_a000
    lda CUR_speed + 1           ; strength (new speed >> 10) + $10
    lsr
    lsr
    clc
    adc #$10
    ldx #0
    jmp push

; ---------------------------------------------------------------- drive

; steering, engine, gears; t1: the gear ratio, t2: speed, t3: steer
drive:
    lda CUR_steer
    sta t3
    lda CUR_steer + 1
    sta t3 + 1
    lda CUR_speed
    sta t2
    lda CUR_speed + 1
    sta t2 + 1
    lda CUR_gear
    jsr ratio_of
    lda #0
    sta CUR_accelerating
    sta CUR_accelerating + 1
    lda CUR_push_x
    ora CUR_push_x + 1
    beq 1f
    jmp 5f
1:
    lda CUR_joy
    and #JOY_LEFT
    beq 2f
    sec
    lda t3
    sbc #2
    sta t3
    bcs 2f
    dec t3 + 1
2:
    lda CUR_joy
    and #JOY_RIGHT
    beq 3f
    clc
    lda t3
    adc #2
    sta t3
    bcc 3f
    inc t3 + 1
3:
    lda t2
    sta t0
    lda t2 + 1
    sta t0 + 1
    jsr rpm_of
    cpx #>$1F40
    bcc 4f
    bne 31f
    cmp #<$1F40
    bcc 4f
31:
    lda #<$1F3F
    ldx #>$1F3F
4:
    ; the torque at rpm / 128, from the accelerating table when accelerating
    stx t0 + 1
    asl
    rol t0 + 1                  ; rpm >> 7 = (rpm << 1) >> 8: the high byte
    lda t0 + 1
    asl
    tay                         ; table index * 2
    jsr accel_bit
    and CUR_joy
    beq 41f
    lda #$FF
    sta CUR_accelerating
    sta CUR_accelerating + 1
    lda tab_torque_acc, y
    ldx tab_torque_acc + 1, y
    bra 42f
41:
    lda tab_torque, y
    ldx tab_torque + 1, y
42:
    ; t = torque * 3 << 10 (t0), speed += t / (ratio >> 1), signed
    sta t0
    stx t0 + 1
    jsr sext0
    ldq t0
    aslq
    clc
    adcq t0
    stq t0                      ; * 3
    ldq t0
    aslq
    aslq
    aslq
    aslq
    aslq
    aslq
    aslq
    aslq
    aslq
    aslq
    stq t0
    ldz #0
    lda t1 + 1
    lsr
    tax
    lda t1
    ror
    jsr div_signed              ; A/X = t0 / (A/X), signed
    clc
    adc t2
    sta t2
    txa
    adc t2 + 1
    sta t2 + 1
5:
    ; steer += push_steer; back towards 0 by 1; within -32 .. 32
    clc
    lda t3
    adc CUR_push_steer
    sta t3
    lda t3 + 1
    adc CUR_push_steer + 1
    sta t3 + 1
    bmi 51f
    ora t3
    beq 53f
    lda t3
    bne 52f
    dec t3 + 1
52:
    dec t3
    bra 53f
51:
    inc t3
    bne 53f
    inc t3 + 1
53:
    scmp t3, $20
    bmi 54f
    lda #$20
    sta t3
    lda #0
    sta t3 + 1
54:
    scmp t3, -$20
    bpl 55f
    lda #<(-$20)
    sta t3
    lda #>(-$20)
    sta t3 + 1
55:
    ldx #P_push_steer
    jsr decay
    ldx #P_push_x
    jsr decay
    ; off the road: speed -= (speed >> grip) >> 1
    clc
    lda CUR_x_view + 2
    adc #<$200
    sta t0
    lda CUR_x_view + 3
    adc #>$200
    lsr
    ror t0
    lsr
    ror t0
    lsr
    ror t0
    lsr
    ror t0
    ldx t0
    lda tab_grip, x
    beq 57f
    tax
    lda t2
    sta t0
    lda t2 + 1
    sta t0 + 1
56:
    cmp #$80                    ; asr of the word, x + 1 times
    ror t0 + 1
    ror t0
    lda t0 + 1
    dex
    bpl 56b
    sec
    lda t2
    sbc t0
    sta t2
    lda t2 + 1
    sbc t0 + 1
    sta t2 + 1
57:
    ; speed += slope_view >> 5
    lda CUR_slope_view
    sta t0
    lda CUR_slope_view + 1
    ldx #5
58:
    cmp #$80
    ror
    ror t0
    dex
    bne 58b
    tax
    clc
    lda t2
    adc t0
    sta t2
    txa
    adc t2 + 1
    sta t2 + 1
    ; braking
    lda CUR_joy
    and #JOY_DOWN
    beq 59f
    sec
    lda t2
    sbc #$30
    sta t2
    bcs 59f
    dec t2 + 1
59:
    scmp t2, $1AA
    bpl 60f
    lda #<$1AA
    sta t2
    lda #>$1AA
    sta t2 + 1
60:
    ; the engine's speed, 1000 .. 7999; the speed from it
    lda t2
    sta t0
    lda t2 + 1
    sta t0 + 1
    jsr rpm_of
    sta rpm_tmp
    stx rpm_tmp + 1
    scmp rpm_tmp, $3E8
    bpl 61f
    lda #<$3E8
    sta rpm_tmp
    lda #>$3E8
    sta rpm_tmp + 1
61:
    scmp rpm_tmp, $1F3F
    bmi 62f
    lda #<$1F3F
    sta rpm_tmp
    lda #>$1F3F
    sta rpm_tmp + 1
62:
    lda rpm_tmp
    ldx rpm_tmp + 1
    jsr speed_of
    ; gears: to (A, $FF for none)
    lda CUR_stopped
    ora CUR_stopped + 1
    ora CUR_automatic
    ora CUR_automatic + 1
    bne 70f
    lda CUR_fire_accel
    ora CUR_fire_accel + 1
    beq 63f
    lda CUR_joy_new             ; fire accelerates: forward / back up / down
    and #JOY_UP
    sta t0
    lda CUR_joy_new
    and #JOY_DOWN
    sta t0 + 1
    bra 64f
63:
    lda #0                      ; fire with forward / back
    sta t0
    sta t0 + 1
    lda CUR_joy_new
    and #JOY_FIRE
    beq 64f
    lda CUR_joy
    and #JOY_UP
    sta t0
    lda CUR_joy
    and #JOY_DOWN
    sta t0 + 1
64:
    lda t0
    beq 65f
    lda CUR_gear
    cmp #4
    beq 65f
    inc
    bra 80f
65:
    lda t0 + 1
    beq 90f
    lda CUR_gear
    beq 90f
    dec
    bra 80f
70:
    ; automatic: up from 4000 when the engine speeds up, else down below 2500
    lda CUR_rpm
    cmp rpm_tmp
    lda CUR_rpm + 1
    sbc rpm_tmp + 1
    bcs 71f
    lda rpm_tmp
    cmp #<$FA0
    lda rpm_tmp + 1
    sbc #>$FA0
    bcc 90f
    lda CUR_gear
    cmp #4
    beq 90f
    inc
    bra 80f
71:
    lda rpm_tmp
    cmp #<$9C4
    lda rpm_tmp + 1
    sbc #>$9C4
    bcs 90f
    lda CUR_gear
    beq 90f
    dec
80:
    ; the new gear if its engine speed stays within 1000 .. 7998
    sta t3 + 2
    jsr ratio_of
    lda t2
    sta t0
    lda t2 + 1
    sta t0 + 1
    jsr rpm_of
    cpx #>$3E8
    bcc 90f
    bne 81f
    cmp #<$3E8
    bcc 90f
81:
    cpx #>$1F3F
    bcc 82f
    bne 90f
    cmp #<$1F3F
    bcs 90f
82:
    sta rpm_tmp
    stx rpm_tmp + 1
    jsr speed_of
    lda t3 + 2
    sta CUR_gear
90:
    lda t3
    sta CUR_steer
    lda t3 + 1
    sta CUR_steer + 1
    lda t2
    sta CUR_speed
    lda t2 + 1
    sta CUR_speed + 1
    lda rpm_tmp
    sta CUR_rpm
    lda rpm_tmp + 1
    sta CUR_rpm + 1
    rts

; ratio_of: t1 = tab_gear_ratio[A]
ratio_of:
    asl
    tay
    lda tab_gear_ratio, y
    sta t1
    lda tab_gear_ratio + 1, y
    sta t1 + 1
    rts

; speed_of: t2 = (A/X * t1) >> 16, unsigned
speed_of:
    sta MULTINA
    stx MULTINA + 1
    lda #0
    sta MULTINA + 2
    sta MULTINA + 3
    lda t1
    ldx t1 + 1
    jsr set_mb_u
    lda MULTOUT + 2
    sta t2
    lda MULTOUT + 3
    sta t2 + 1
    rts

; decay: the word at cur + X one closer to 0
decay:
    lda cur + 1, x
    bmi 2f
    ora cur, x
    beq 3f
    lda cur, x
    bne 1f
    dec cur + 1, x
1:
    dec cur, x
3:
    rts
2:
    inc cur, x
    bne 3b
    inc cur + 1, x
    rts

; div_signed: A/X = t0 (signed 32) / A/X (positive word), rounded towards
; 0 as divs
div_signed:
    jsr set_mb_u
    lda t0 + 3
    php
    bpl 1f
    lda #0                      ; |t0|
    tax
    tay
    taz
    sec
    sbcq t0
    stq t0
    ldz #0
1:
    ldq t0
    stq_io MULTINA
    ldz #0
2:
    bit MATHBUSY
    bmi 2b
    lda DIVOUT
    ldx DIVOUT + 1
    plp
    bpl 3f
    eor #$FF
    clc
    adc #1
    pha
    txa
    eor #$FF
    adc #0
    tax
    pla
3:
    rts

; ---------------------------------------------------------------- drive_or_coast

drive_or_coast:
    lda CUR_speed_view
    ora CUR_speed_view + 1
    bne 1f
    sta CUR_joy
1:
    lda CUR_stopped
    ora CUR_stopped + 1
    bne 2f
    jmp drive
2:
    lda CUR_speed
    pha
    lda CUR_speed + 1
    pha
    jsr drive
    pla
    tax
    pla
    sec
    sbc #$18
    sta CUR_speed
    txa
    sbc #0
    sta CUR_speed + 1
    bpl 3f
    lda #0
    sta CUR_speed
    sta CUR_speed + 1
3:
    rts

; ---------------------------------------------------------------- player_frame

; player_frame: player A (0, 1)
player_frame:
    sta cur_n
    jsr get_player
    lda CUR_in_pits
    ora CUR_in_pits + 1
    beq 1f
    jsr in_pits
    jsr timers
    jmp put_player
1:
    lda #0
    sta race + R_scrape
    sta race + R_scrape + 1
    jsr move
    ldx cur_n
    beq 2f
    ldx #R_sound_p2 - R_sound_p1
2:
    clc
    lda race + R_sound_p1, x
    adc race + R_scrape
    sta race + R_sound_p1, x
    lda race + R_sound_p1 + 1, x
    adc race + R_scrape + 1
    sta race + R_sound_p1 + 1, x
    jsr burn
    jsr seg_here
    jsr pit_check
    lda #0
    sta race + R_scrape
    sta race + R_scrape + 1
    jsr hit_scenery
    clc                         ; both players' scraping goes to player 1's
    lda race + R_sound_p1
    adc race + R_scrape
    sta race + R_sound_p1
    lda race + R_sound_p1 + 1
    adc race + R_scrape + 1
    sta race + R_sound_p1 + 1
    lda #1
    jsr crash_flag
    lda race + R_difficulty
    cmp #3
    beq 3f
    jsr hit_opponents
    lda #2
    jsr crash_flag
3:
    lda race + R_two_players
    ora race + R_two_players + 1
    beq 4f
    lda cur_n                   ; the other player
    eor #1
    jsr player_ptr
    jsr hit_other
    lda #2
    jsr crash_flag
4:
    jsr drive_or_coast
    jsr timers
    jmp put_player

; crash_flag: crash[cur_n] = A if the last check hit something
crash_flag:
    ldx race + R_hit
    beq 1f
    ldx cur_n
    beq 2f
    ldx #2
2:
    sta race + R_crash, x
    lda #0
    sta race + R_crash + 1, x
1:
    rts

; player_ptr: pp = &race.p[A]
player_ptr:
    ldx #<P0
    ldy #>P0
    cmp #0
    beq 1f
    ldx #<P1
    ldy #>P1
1:
    stx pp
    sty pp + 1
    rts

; get_player / put_player: race.p[cur_n] to cur and back
get_player:
    lda cur_n
    jsr player_ptr
    ldy #PLAYER_SIZE - 1
1:
    lda (pp), y
    sta cur, y
    dey
    cpy #$FF
    bne 1b
    rts

put_player:
    lda cur_n
    jsr player_ptr
    ldy #PLAYER_SIZE - 1
1:
    lda cur, y
    sta (pp), y
    dey
    cpy #$FF
    bne 1b
    rts

; ---------------------------------------------------------------- opponents

; Signed compare of the words at a and b: N set if a < b
.macro scmpw a, b
    lda \a
    cmp \b
    lda \a + 1
    sbc \b + 1
    bvc .Lscmpw\@
    eor #$80
.Lscmpw\@:
.endm

OPP = race + R_opp

.section .bss.race_s
o_off:      .fill 1         ; offset of the opponent being moved
o_ahead:    .fill 1         ; offset of the one it must not pass
o_want:     .fill 2
o_pos:      .fill 4
o_x:        .fill 2
o_speed:    .fill 2
o_dx:       .fill 2
o_lim:      .fill 4
.section .text.race_s

; the opponents drive (race.c opponents()), X: the offset of each
opponents:
    ldx #0
1:
    stx o_off
    ; want = target + bonus
    clc
    lda OPP + O_target, x
    adc race + R_opp_bonus
    sta o_want
    lda OPP + O_target + 1, x
    adc race + R_opp_bonus + 1
    sta o_want + 1
    ; speed += ((want - speed) >> 7) + 1 (unsigned), at most want
    sec
    lda o_want
    sbc OPP + O_speed, x
    sta t0
    lda o_want + 1
    sbc OPP + O_speed + 1, x
    asl t0
    rol
    tay
    lda #0
    rol
    sta t0 + 1
    tya
    sec                         ; + 1 with the carry set
    adc OPP + O_speed, x
    sta o_speed
    lda t0 + 1
    adc OPP + O_speed + 1, x
    sta o_speed + 1
    lda o_want
    cmp o_speed
    lda o_want + 1
    sbc o_speed + 1
    bcs 2f
    lda o_want
    sta o_speed
    lda o_want + 1
    sta o_speed + 1
2:
    lda OPP + O_x, x
    sta o_x
    lda OPP + O_x + 1, x
    sta o_x + 1
    lda OPP + O_dx, x
    sta o_dx
    lda OPP + O_dx + 1, x
    sta o_dx + 1
    lda OPP + O_pos, x
    sta o_pos
    lda OPP + O_pos + 1, x
    sta o_pos + 1
    lda OPP + O_pos + 2, x
    sta o_pos + 2
    lda OPP + O_pos + 3, x
    sta o_pos + 3
    ; the segment's limits, bytes 14 (left) and 15 (right), * 16
    lda o_pos + 2
    ldx o_pos + 3
    jsr segment
    ldy #15
    lda (pp), y
    jsr times16
    lda t0
    sta t1
    lda t0 + 1
    sta t1 + 1                  ; right
    ldy #14
    lda (pp), y
    jsr times16                 ; left in t0
    scmpw o_x, t1
    bmi 4f
    ; x >= right: x -= 4, dx negative
    sec
    lda o_x
    sbc #4
    sta o_x
    bcs 31f
    dec o_x + 1
31:
    bit o_dx + 1
    bmi 7f
    jsr neg_odx
    bra 7f
4:
    scmpw o_x, t0
    bpl 6f
    ; x < left: x += 4, dx positive
    clc
    lda o_x
    adc #4
    sta o_x
    bcc 41f
    inc o_x + 1
41:
    bit o_dx + 1
    bpl 7f
    jsr neg_odx
    bra 7f
6:
    clc
    lda o_x
    adc o_dx
    sta o_x
    lda o_x + 1
    adc o_dx + 1
    sta o_x + 1
7:
    ; pos += speed (sign-extended)
    ldx #0
    bit o_speed + 1
    bpl 71f
    dex
71:
    clc
    lda o_pos
    adc o_speed
    sta o_pos
    lda o_pos + 1
    adc o_speed + 1
    sta o_pos + 1
    txa
    adc o_pos + 2
    sta o_pos + 2
    txa
    adc o_pos + 3
    sta o_pos + 3
    ; the car ahead: the limit
    ldx o_off
    bne 8f
    ; the leader: the last one, a lap on
    lda race + R_opponents
    sec
    sbc #1
    jsr times12
    sta o_ahead
    tax
    clc
    lda OPP + O_pos, x
    adc race + R_opp_length
    sta o_lim
    lda OPP + O_pos + 1, x
    adc race + R_opp_length + 1
    sta o_lim + 1
    lda OPP + O_pos + 2, x
    adc race + R_opp_length + 2
    sta o_lim + 2
    lda OPP + O_pos + 3, x
    adc race + R_opp_length + 3
    sta o_lim + 3
    bra 9f
8:
    txa
    sec
    sbc #OPPONENT_SIZE
    sta o_ahead
    tax
    lda OPP + O_pos, x
    sta o_lim
    sec
    lda OPP + O_pos + 1, x
    sbc #$40
    sta o_lim + 1
    lda OPP + O_pos + 2, x
    sbc #0
    sta o_lim + 2
    lda OPP + O_pos + 3, x
    sbc #0
    sta o_lim + 3
9:
    ; limit < pos (unsigned): pos = limit, and swap speed, target, dx
    lda o_lim
    cmp o_pos
    lda o_lim + 1
    sbc o_pos + 1
    lda o_lim + 2
    sbc o_pos + 2
    lda o_lim + 3
    sbc o_pos + 3
    bcs 10f
    ldx #3
91:
    lda o_lim, x
    sta o_pos, x
    dex
    bpl 91b
    ldx o_ahead
    ldy o_off
    lda OPP + O_speed, x        ; speed
    pha
    lda o_speed
    sta OPP + O_speed, x
    pla
    sta o_speed
    lda OPP + O_speed + 1, x
    pha
    lda o_speed + 1
    sta OPP + O_speed + 1, x
    pla
    sta o_speed + 1
    lda OPP + O_target, x       ; target (into this one's entry directly)
    pha
    lda OPP + O_target, y
    sta OPP + O_target, x
    pla
    sta OPP + O_target, y
    lda OPP + O_target + 1, x
    pha
    lda OPP + O_target + 1, y
    sta OPP + O_target + 1, x
    pla
    sta OPP + O_target + 1, y
    lda OPP + O_dx, x           ; dx
    pha
    lda o_dx
    sta OPP + O_dx, x
    pla
    sta o_dx
    lda OPP + O_dx + 1, x
    pha
    lda o_dx + 1
    sta OPP + O_dx + 1, x
    pla
    sta o_dx + 1
10:
    ; store
    ldx o_off
    lda o_pos
    sta OPP + O_pos, x
    lda o_pos + 1
    sta OPP + O_pos + 1, x
    lda o_pos + 2
    sta OPP + O_pos + 2, x
    lda o_pos + 3
    sta OPP + O_pos + 3, x
    lda o_x
    sta OPP + O_x, x
    lda o_x + 1
    sta OPP + O_x + 1, x
    lda o_speed
    sta OPP + O_speed, x
    lda o_speed + 1
    sta OPP + O_speed + 1, x
    lda o_dx
    sta OPP + O_dx, x
    lda o_dx + 1
    sta OPP + O_dx + 1, x
    ; the next
    txa
    clc
    adc #OPPONENT_SIZE
    tax
    lda race + R_opponents
    jsr times12
    sta t0
    cpx t0
    beq 11f
    jmp 1b
11:
    rts

neg_odx:
    sec
    lda #0
    sbc o_dx
    sta o_dx
    lda #0
    sbc o_dx + 1
    sta o_dx + 1
    rts

; times16: t0 = A (a signed byte) * 16
times16:
    ldx #0
    cmp #$80
    bcc 1f
    dex
1:
    stx t0 + 1
    asl
    rol t0 + 1
    asl
    rol t0 + 1
    asl
    rol t0 + 1
    asl
    rol t0 + 1
    sta t0
    rts

; times12: A = A * 12 (A < 22)
times12:
    asl
    asl
    sta t0
    asl
    clc
    adc t0
    rts

; ---------------------------------------------------------------- input, autopilot, animate

input:
    ldx #0
    jsr input1
    ldx #1
input1:
    txa
    sta cur_n
    jsr get_player
    ldx cur_n
    lda race_joy, x
    sta CUR_joy
    tay
    eor cur + P_joy_last
    sta t0
    tya
    and t0
    sta CUR_joy_new
    sty cur + P_joy_last
    jmp put_player

autopilot:
    lda #JOY_FIRE
    sta t0
    scmp P0 + P_x + 2, $20
    bmi 1f
    lda #JOY_FIRE | JOY_LEFT
    sta t0
1:
    scmp P0 + P_x + 2, -$60
    bpl 2f
    lda t0
    ora #JOY_RIGHT
    sta t0
2:
    lda t0
    sta P0 + P_joy
    lda #JOY_FIRE
    sta t0
    scmp P1 + P_x + 2, $60
    bmi 3f
    lda #JOY_FIRE | JOY_LEFT
    sta t0
3:
    scmp P1 + P_x + 2, -$20
    bpl 4f
    lda t0
    ora #JOY_RIGHT
    sta t0
4:
    lda t0
    sta P1 + P_joy
    rts

animate:
    lda race + R_buffer
    and #7
    bne 9f
    jsr race_random
    ldz #0
    sta t0
    stx t0 + 1
    cpx #$40
    bcc 1f
    inw_abs P0 + P_flicker
1:
    cpx #$C0
    bcs 2f
    inw_abs P1 + P_flicker
2:
    lda t0
    ldx t0 + 1
    bmi 3f
    sta P1 + P_flicker_r
    stx P1 + P_flicker_r + 1
    rts
3:
    sta P0 + P_flicker_r
    stx P0 + P_flicker_r + 1
9:
    rts

; ---------------------------------------------------------------- places

; place_of: place of the car at t2 (4 bytes), the other player at t1 -> A
place_of:
    lda #1
    sta t0
    lda race + R_difficulty
    cmp #3
    beq 3f
    ldx #0
    ldy race + R_opponents
1:
    lda t2                      ; pos < opp_pic[i] (unsigned): one more ahead
    cmp race + R_opp_pic, x
    lda t2 + 1
    sbc race + R_opp_pic + 1, x
    lda t2 + 2
    sbc race + R_opp_pic + 2, x
    lda t2 + 3
    sbc race + R_opp_pic + 3, x
    bcs 2f
    inc t0
2:
    inx
    inx
    inx
    inx
    dey
    bne 1b
3:
    lda race + R_two_players
    ora race + R_two_players + 1
    beq 4f
    lda t2
    cmp t1
    lda t2 + 1
    sbc t1 + 1
    lda t2 + 2
    sbc t1 + 2
    lda t2 + 3
    sbc t1 + 3
    bcs 4f
    inc t0
4:
    lda t0
    rts

places:
    lda P0 + P_fuel
    ora P0 + P_fuel + 1
    ora P0 + P_fuel + 2
    ora P0 + P_fuel + 3
    beq 1f
    lda P0 + P_stopped
    ora P0 + P_stopped + 1
    bne 2f
1:
    ldq mos16(P0 + P_pos)
    stq t2
    ldq mos16(P1 + P_pos)
    stq t1
    ldz #0
    jsr place_of
    sta P0 + P_place
    lda #0
    sta P0 + P_place + 1
2:
    lda race + R_two_players
    ora race + R_two_players + 1
    beq 4f
    lda P1 + P_fuel
    ora P1 + P_fuel + 1
    ora P1 + P_fuel + 2
    ora P1 + P_fuel + 3
    beq 3f
    lda P1 + P_stopped
    ora P1 + P_stopped + 1
    bne 4f
3:
    ldq mos16(P1 + P_pos)
    stq t2
    ldq mos16(P0 + P_pos)
    stq t1
    ldz #0
    jsr place_of
    sta P1 + P_place
    lda #0
    sta P1 + P_place + 1
4:
    rts

; ---------------------------------------------------------------- laps

laps:
    lda race + R_finished
    sta t3                      ; done (a byte: at most 21)
    ; out of fuel: stopped
    lda #0
    jsr laps_fuel
    lda #1
    jsr laps_fuel
    lda #0
    jsr laps_finish
    lda race + R_two_players
    ora race + R_two_players + 1
    beq 1f
    lda #1
    jsr laps_finish
1:
    ; the opponents over the line
    lda race + R_next_finisher
    sta t3 + 1                  ; i
2:
    lda t3 + 1
    cmp race + R_opponents
    beq 3f
    jsr times12
    tax
    sec                         ; finish - pos < 0: over the line
    lda race + R_finish
    sbc OPP + O_pos, x
    lda race + R_finish + 1
    sbc OPP + O_pos + 1, x
    lda race + R_finish + 2
    sbc OPP + O_pos + 2, x
    lda race + R_finish + 3
    sbc OPP + O_pos + 3, x
    bpl 3f
    jsr laps_time
    inc t3 + 1
    bra 2b
3:
    lda t3 + 1
    sta race + R_next_finisher
    lda #0
    sta race + R_next_finisher + 1
    sta race + R_finished + 1
    lda t3
    sta race + R_finished
    cmp #10
    bcc 4f
    lda #1
    sta P0 + P_stopped
    sta P1 + P_stopped
    lda #0
    sta P0 + P_stopped + 1
    sta P1 + P_stopped + 1
4:
    rts

; laps_time: finish_frames[done++] = frames
laps_time:
    lda t3
    asl
    tax
    lda race + R_frames
    sta race + R_finish_frames, x
    lda race + R_frames + 1
    sta race + R_finish_frames + 1, x
    inc t3
    rts

laps_fuel:
    sta cur_n
    jsr get_player
    lda CUR_stopped
    ora CUR_stopped + 1
    bne 1f
    lda CUR_fuel
    ora CUR_fuel + 1
    ora CUR_fuel + 2
    ora CUR_fuel + 3
    bne 1f
    lda #1
    sta CUR_stopped
1:
    jmp put_player

laps_finish:
    sta cur_n
    jsr get_player
    lda CUR_place + 1
    bne 9f
    lda CUR_place
    cmp #11
    bcs 9f
    sec                         ; finish - pos >= 0: not over the line
    lda race + R_finish
    sbc CUR_pos
    lda race + R_finish + 1
    sbc CUR_pos + 1
    lda race + R_finish + 2
    sbc CUR_pos + 2
    lda race + R_finish + 3
    sbc CUR_pos + 3
    bpl 9f
    lda CUR_stopped
    ora CUR_stopped + 1
    beq 1f
    lda CUR_fuel
    ora CUR_fuel + 1
    ora CUR_fuel + 2
    ora CUR_fuel + 3
    bne 9f
    lda #1
    sta CUR_fuel
1:
    lda #1
    sta CUR_stopped
    lda #0
    sta CUR_stopped + 1
    lda CUR_pos + 2
    sta CUR_cam_pos + 2
    lda CUR_pos + 3
    sta CUR_cam_pos + 3
    lda CUR_x + 2
    sta CUR_cam_x
    lda CUR_x + 3
    sta CUR_cam_x + 1
    jsr laps_time
9:
    jmp put_player

; ---------------------------------------------------------------- race_over

; race_over: carry set when the race is over
race_over:
    ldx #0
    jsr over1
    bcc 9f
    lda race + R_two_players
    ora race + R_two_players + 1
    beq 8f
    ldx #PLAYER_SIZE
    jsr over1
    rts
8:
    sec
9:
    rts

; over1: the player at P0 + X stopped and not rolling (carry set)
over1:
    lda P0 + P_stopped, x
    ora P0 + P_stopped + 1, x
    beq 1f
    lda P0 + P_in_pits_shown, x
    ora P0 + P_in_pits_shown + 1, x
    bne 2f
    lda P0 + P_speed_view, x
    ora P0 + P_speed_view + 1, x
    bne 1f
2:
    sec
    rts
1:
    clc
    rts

; ---------------------------------------------------------------- race_frame

race_frame:
    lda race + R_clock + 1
    bpl 1f
    ; before the start: the camera flies in
    sec
    lda #<(-100)
    sbc race + R_clock
    sta t0
    lda #>(-100)
    sbc race + R_clock + 1
    sta t0 + 1
    bmi 2f
    jsr sext0
    ldq t0
    aslq
    aslq
    aslq
    aslq
    stq t0
    ldz #0
    add32 P0 + P_cam_pos, t0
    add32 P1 + P_cam_pos, t0
2:
    lda #0
    sta cur_n
    jsr get_player
    jsr seg_here
    jsr put_player
    lda #1
    sta cur_n
    jsr get_player
    jsr seg_here
    jsr put_player
    jmp 9f
1:
    lda race + R_over
    ora race + R_over + 1
    beq 3f
    lda race + R_over_timer
    cmp #150
    beq 3f
    inc race + R_over_timer
3:
    lda race + R_paused
    ora race + R_paused + 1
    beq 4f
    jmp 9f
4:
    jsr animate
    lda race + R_difficulty
    cmp #3
    beq 5f
    jsr opponents
5:
    jsr input
    lda race + R_demo
    ora race + R_demo + 1
    beq 6f
    jsr autopilot
6:
    lda #0
    sta race + R_control
    sta race + R_control + 1
    jsr player_frame
    lda race + R_control2
    sta race + R_control
    lda race + R_control2 + 1
    sta race + R_control + 1
    lda race + R_two_players
    ora race + R_two_players + 1
    beq 7f
    lda #1
    jsr player_frame
7:
    inw_abs race + R_frames
    ldx #0
    jsr timer1
    ldx #PLAYER_SIZE
    jsr timer1
    jsr places
    jsr laps
    jsr race_over
    bcc 9f
    lda #1
    sta race + R_over
    lda #0
    sta race + R_over + 1
9:
    ; the clock: from $200 back to $100
    inw_abs race + R_clock
    lda race + R_clock + 1
    cmp #2
    bne 10f
    lda race + R_clock
    bne 10f
    lda #1
    sta race + R_clock + 1
10:
    ldz #0
    rts

; timer1: the player at P0 + X: timer down while positive
timer1:
    lda P0 + P_timer + 1, x
    bmi 2f
    ora P0 + P_timer, x
    beq 2f
    lda P0 + P_timer, x
    bne 1f
    dec P0 + P_timer + 1, x
1:
    dec P0 + P_timer, x
2:
    rts

; ---------------------------------------------------------------- race_picture

race_picture:
    inc race + R_buffer
    lda race + R_buffer
    cmp #3
    bne 1f
    lda #0
    sta race + R_buffer
1:
    lda #0
    jsr picture1
    lda #1
    jsr picture1
    ; the opponents as they are
    ldx #0
    ldy #0
2:
    lda OPP + O_pos, x
    sta race + R_opp_pic, y
    lda OPP + O_pos + 1, x
    sta race + R_opp_pic + 1, y
    lda OPP + O_pos + 2, x
    sta race + R_opp_pic + 2, y
    lda OPP + O_pos + 3, x
    sta race + R_opp_pic + 3, y
    phy
    tya
    lsr
    tay
    lda OPP + O_x, x
    sta race + R_opp_pic_x, y
    lda OPP + O_x + 1, x
    sta race + R_opp_pic_x + 1, y
    ply
    txa
    clc
    adc #OPPONENT_SIZE
    tax
    iny
    iny
    iny
    iny
    cpy #4 * OPPONENTS
    bne 2b
    ldz #0
    rts

picture1:
    sta cur_n
    jsr get_player
    ldq mos16(CUR_pos)
    stq mos16(cur + P_pos_pic)
    stq mos16(cur + P_pos_pic2)
    stq mos16(cur + P_pos_shown)
    ldq mos16(CUR_x)
    stq mos16(cur + P_x_pic)
    stq mos16(cur + P_x_pic2)
    stq mos16(cur + P_x_shown)
    ldz #0
    lda CUR_in_pits
    sta cur + P_in_pits_pic
    sta cur + P_in_pits_shown
    lda CUR_in_pits + 1
    sta cur + P_in_pits_pic + 1
    sta cur + P_in_pits_shown + 1
    ; the camera instead before the start and after the finish
    bit race + R_clock + 1
    bmi 1f
    lda CUR_stopped
    ora CUR_stopped + 1
    beq 2f
    lda CUR_fuel
    ora CUR_fuel + 1
    ora CUR_fuel + 2
    ora CUR_fuel + 3
    beq 2f
    lda CUR_place + 1
    bne 2f
    lda CUR_place
    cmp #11
    bcs 2f
1:
    ldq mos16(CUR_cam_pos)
    stq mos16(cur + P_pos_pic)
    ldz #0
    lda CUR_cam_x
    sta cur + P_x_pic + 2
    lda CUR_cam_x + 1
    sta cur + P_x_pic + 3
2:
    ldq mos16(cur + P_pos_pic)
    stq mos16(cur + P_pos_view)
    ldq mos16(cur + P_x_pic)
    stq mos16(cur + P_x_view)
    ldz #0
    ldx #0
3:
    lda CUR_speed, x            ; speed, steer, curve, u16 -> *_view
    sta cur + P_speed_view, x
    inx
    cpx #6
    bne 3b
    lda CUR_u16
    sta cur + P_u16_view
    lda CUR_u16 + 1
    sta cur + P_u16_view + 1
    lda CUR_slope
    sta CUR_slope_view
    lda CUR_slope + 1
    sta CUR_slope_view + 1
    jmp put_player

; ---------------------------------------------------------------- race_seg_lookup

; race_seg_lookup(n): the course at race_lookup_pos for player n (race_init)
.global race_seg_lookup
race_seg_lookup:
    sta cur_n
    jsr get_player
    ldq mos16(race_lookup_pos)
    stq t2
    ldz #0
    jsr seg_lookup
    jsr put_player
    ldz #0
    rts
