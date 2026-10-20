; Lotus Run: the music player (music.h), run by the raster interrupt
; (irq.s) once a frame. It plays MUSIC (tools/mkmusic.py) on the four SIDs,
; reading it from attic RAM through a 32-bit pointer.
;
; MUSIC: offsets (16 bits) of the instruments, of the pattern table and of
; each song's header. A song: frames per row, its length, the position to
; go back to at its end, then its patterns' numbers. The pattern table
; holds each pattern's offset; a pattern is 64 rows: $80 + n stands for
; n + 1 empty rows, else a byte says which parts have something (bit i:
; part i), and for each of them in turn: $00-$5F a note, $60 + n
; instrument n and then the note, $7F the note's release.
;
; An instrument is 32 bytes: attack/decay, sustain/release, pulse width
; (x16), its change per frame (signed, bouncing between $100 and $EFF),
; vibrato (delay << 4 | shift, 0 none), the filter's cutoff at the start (0:
; the filter is left alone) and its fall per frame, the instrument of its
; echo ($FF none), the number of steps, the step to loop to, and from byte
; 16 on the steps: waveform with gate, then pitch - $00-$7F semitones from
; the note (7 bits, signed), $80 + n a frequency of n * 512.
;
; The parts, in stereo (the SIDs at $D400 and $D420 on the right, $D440
; and $D460 on the left): the bass and the drums on both sides, the hi-hat
; on the right, the melody on both sides, a little higher on the left, the
; second voice on the left, the ticks between the beats on the left; then
; the echoes: of the melody 3 rows later on the right and 6 rows later on
; the left, of the second voice 3 rows later on the right. The bass goes
; through the filters of the SIDs at $D400 and $D440.

.include "offsets.inc"

.global music_start, music_stop, music_frame

; zero page: in the KERNAL's, which is switched out (irq.s)
mp  = $F8                       ; 4 bytes: a pointer into MUSIC
tmp = $FC                       ; 2 bytes

PARTS  = 9
STORED = 6                      ; the parts in the patterns
ECHO   = 6                      ; the first echo
NONE   = $FF

.section .lowram.music_s,"aw",@nobits   ; set before use: LOW_RAM (mem.h)
playing:    .fill 1
speed:      .fill 1
tick:       .fill 1             ; frames to the next row
row:        .fill 1
wait:       .fill 1             ; empty rows still to come
pos:        .fill 1             ; in the song
length:     .fill 1
restart:    .fill 1
mask:       .fill 1
song:       .fill 2             ; offsets in MUSIC
table:      .fill 2
insts:      .fill 2
pat:        .fill 2
src_note:   .fill 2             ; the melody's and the second voice's event
src_inst:   .fill 2             ; this row (NONE, $7F, note), and instrument
ring_i:     .fill 1
ring_note:  .fill 16            ; their last 8 rows (the melody's, then the
ring_inst:  .fill 16            ; second voice's)
p_inst:     .fill PARTS         ; per part: the instrument (NONE: silent)
p_note:     .fill PARTS
p_step:     .fill PARTS
p_new:      .fill PARTS         ; the note starts: gate still off
p_rel:      .fill PARTS         ; released
p_frames:   .fill PARTS         ; since the note started (up to 255)
p_vib:      .fill PARTS         ; vibrato phase
p_pwlo:     .fill PARTS
p_pwhi:     .fill PARTS
p_pwspd:    .fill PARTS
p_cut:      .fill PARTS         ; filter cutoff (0: not touched)
p_wave:     .fill PARTS
cur_flo:    .fill 1             ; the part being updated
cur_fhi:    .fill 1
cur_wave:   .fill 1
cur_pitch:  .fill 1
count:      .fill 1

.section .lowcode.music_data,"a",@progbits   ; LOW_CODE (mem.h)
; per part: its voices' registers (offset from $D400; NONE: one voice
; only), whether the second one is a little higher
part_v0:    .byte $00, $07, $0E, $20, $67, $4E, $2E, $6E, $27
part_v1:    .byte $40, $47, NONE, $60, NONE, NONE, NONE, NONE, NONE
part_detune: .byte 0, 0, 0, 1, 0, 0
; per stored part: whose echo it makes (0 the melody's, 1 the second's)
part_src:   .byte NONE, NONE, NONE, 0, 1, NONE
; per echo: of whom (ring offset), how many rows later
echo_ring:  .byte 0, 0, 8
echo_delay: .byte 3, 6, 3
; the SID's frequencies of C6 to B6 (1 MHz clock)
freq_tab:   .word $4495, $48A9, $4CFC, $518F, $5669, $5B8C
            .word $60FE, $66C2, $6CDF, $7358, $7A34, $8178
vib_tab:    .byte 0, 1, 2, 1, 0, $FF, $FE, $FF

.section .lowcode.music_s,"ax",@progbits

; music_start(song): from the start of a song (A); called with the
; interrupt on
music_start:
    sta tmp
    lda #0
    sta playing
    jsr silence
    lda #0
    sta mp
    sta mp + 1
    lda #<(MUSIC_ATTIC >> 16)
    sta mp + 2
    lda #>(MUSIC_ATTIC >> 16)
    sta mp + 3
    ldz #0
    lda [mp], z
    sta insts
    inz
    lda [mp], z
    sta insts + 1
    inz
    lda [mp], z
    sta table
    inz
    lda [mp], z
    sta table + 1
    lda tmp
    asl
    clc
    adc #4
    taz
    lda [mp], z
    sta song
    inz
    lda [mp], z
    sta song + 1
    lda song
    sta mp
    lda song + 1
    sta mp + 1
    ldz #0
    lda [mp], z
    sta speed
    inz
    lda [mp], z
    sta length
    inz
    lda [mp], z
    sta restart
    lda #NONE
    sta pos                     ; next_pattern takes it to 0
    ldx #PARTS - 1
1:  sta p_inst, x
    dex
    bpl 1b
    ldx #15
2:  sta ring_note, x
    dex
    bpl 2b
    jsr next_pattern
    lda #0
    sta row
    sta ring_i
    lda #1
    sta tick
    sta playing
    ldz #0
    rts

; music_stop(): silence
music_stop:
    lda #0
    sta playing
    jsr silence
    ldz #0
    rts

; All four SIDs quiet; the filters of the first and third low pass for the
; bass
silence:
    ldx #$7F
    lda #0
1:  sta $D400, x
    dex
    bpl 1b
    lda #$81                    ; resonance 8, voice 1 filtered
    sta $D417
    sta $D457
    lda #$1F                    ; low pass, full volume
    sta $D418
    sta $D458
    lda #$0F
    sta $D438
    sta $D478
    rts

; Once a frame (irq.s)
music_frame:
    lda playing
    bne 1f
    rts
1:  dec tick
    bne 2f
    lda speed
    sta tick
    jsr do_row
2:  ldx #PARTS - 1
3:  jsr update_part
    dex
    bpl 3b
    rts

; The next byte of the pattern
read_pat:
    lda pat
    sta mp
    lda pat + 1
    sta mp + 1
    inc pat
    bne 1f
    inc pat + 1
1:  ldz #0
    lda [mp], z
    rts

; mp: instrument A
inst_ptr:
    sta tmp
    lsr
    lsr
    lsr
    sta tmp + 1
    lda tmp
    asl
    asl
    asl
    asl
    asl
    clc
    adc insts
    sta mp
    lda tmp + 1
    adc insts + 1
    sta mp + 1
    rts

; The song's next pattern
next_pattern:
    lda #0
    sta wait
    inc pos
    lda pos
    cmp length
    bcc 1f
    lda restart
    sta pos
1:  lda song
    clc
    adc #3
    sta mp
    lda song + 1
    adc #0
    sta mp + 1
    ldz pos
    lda [mp], z
    asl
    sta tmp
    lda #0
    rol
    sta tmp + 1
    lda table
    clc
    adc tmp
    sta mp
    lda table + 1
    adc tmp + 1
    sta mp + 1
    ldz #0
    lda [mp], z
    sta pat
    inz
    lda [mp], z
    sta pat + 1
    rts

; A row: the parts' events, the echoes
do_row:
    lda #NONE
    sta src_note
    sta src_note + 1
    lda wait
    beq 1f
    dec wait
    bra .Lecho
1:  jsr read_pat
    bpl 2f
    and #$7F
    sta wait
    bra .Lecho
2:  sta mask
    ldx #0
3:  lsr mask
    bcc 6f
    jsr read_pat
    cmp #$7F
    bne 4f
    sta p_rel, x                ; released
    ldy part_src, x
    bmi 6f
    sta src_note, y
    bra 6f
4:  cmp #$60
    bcc 5f
    sbc #$60
    sta p_inst, x
    jsr read_pat
5:  ldy part_src, x
    bmi 51f
    sta src_note, y
    pha
    lda p_inst, x
    sta src_inst, y
    pla
51: jsr note_on
6:  inx
    cpx #STORED
    bne 3b
.Lecho:
    ldy ring_i
    lda src_note
    sta ring_note, y
    lda src_inst
    sta ring_inst, y
    lda src_note + 1
    sta ring_note + 8, y
    lda src_inst + 1
    sta ring_inst + 8, y
    ldx #ECHO
8:  lda ring_i
    sec
    sbc echo_delay - ECHO, x
    and #7
    ora echo_ring - ECHO, x
    tay
    jsr echo_event
    inx
    cpx #PARTS
    bne 8b
    lda ring_i
    clc
    adc #1
    and #7
    sta ring_i
    inc row
    lda row
    cmp #64
    bne 7f
    lda #0
    sta row
    jsr next_pattern
7:  rts

; Echo part X plays what its source did in ring entry Y
echo_event:
    lda ring_note, y
    cmp #NONE
    beq 2f
    cmp #$7F
    bne 1f
    sta p_rel, x
    rts
1:  sta count
    lda ring_inst, y
    jsr inst_ptr
    ldz #7
    lda [mp], z
    cmp #NONE
    beq 2f
    sta p_inst, x
    lda count
    jmp note_on
2:  rts

; Part X: note A starts (its gate goes on the frame after)
note_on:
    sta p_note, x
    lda #0
    sta p_step, x
    sta p_rel, x
    sta p_frames, x
    sta p_vib, x
    lda #1
    sta p_new, x
    lda p_inst, x
    jsr inst_ptr
    ldz #2
    lda [mp], z
    pha
    asl
    asl
    asl
    asl
    sta p_pwlo, x
    pla
    lsr
    lsr
    lsr
    lsr
    sta p_pwhi, x
    inz
    lda [mp], z
    sta p_pwspd, x
    ldz #5
    lda [mp], z
    sta p_cut, x
    lda p_wave, x
    and #$FE
    sta cur_wave
    ldy part_v0, x
    jsr envelope
    ldy part_v1, x
    bmi 1f
    jsr envelope
1:  rts

; Voice Y: gate off, the instrument's envelope
envelope:
    lda cur_wave
    sta $D404, y
    ldz #0
    lda [mp], z
    sta $D405, y
    inz
    lda [mp], z
    sta $D406, y
    rts

; A frame of part X (kept)
update_part:
    lda p_inst, x
    cmp #NONE
    bne 1f
    rts
1:  lda p_new, x
    beq 2f
    lda #0
    sta p_new, x
    rts
2:  lda p_inst, x
    jsr inst_ptr
    ; the step, and the next
    lda p_step, x
    asl
    clc
    adc #16
    taz
    lda [mp], z
    sta cur_wave
    inz
    lda [mp], z
    sta cur_pitch
    lda p_step, x
    clc
    adc #1
    ldz #8
    cmp [mp], z
    bcc 3f
    ldz #9
    lda [mp], z
3:  sta p_step, x
    lda p_rel, x
    beq 4f
    lda cur_wave
    and #$FE
    sta cur_wave
4:  lda cur_wave
    sta p_wave, x

    ; the pitch: fixed, or from the note
    lda cur_pitch
    bpl 5f
    asl
    sta cur_fhi
    lda #0
    sta cur_flo
    bra 8f
5:  cmp #$40
    bcc 6f
    ora #$80
6:  clc
    adc p_note, x
    bpl 61f
    lda #0
61: cmp #84
    bcc 62f
    lda #83
62: jsr note_freq

    ; vibrato after its delay: up to twice freq >> shift up and down
8:  ldz #4
    lda [mp], z
    beq 10f
    sta tmp
    lsr
    lsr
    lsr
    lsr
    cmp p_frames, x
    beq 81f
    bcs 10f
81: lda tmp
    and #15
    tay
    lda cur_fhi
    sta tmp + 1
    lda cur_flo
    sta tmp
82: lsr tmp + 1
    ror tmp
    dey
    bne 82b
    lda p_vib, x
    clc
    adc #1
    and #7
    sta p_vib, x
    tay
    lda vib_tab, y
    beq 10f
    bmi 85f
    sta count
83: lda cur_flo
    clc
    adc tmp
    sta cur_flo
    lda cur_fhi
    adc tmp + 1
    sta cur_fhi
    dec count
    bne 83b
    bra 10f
85: eor #$FF
    clc
    adc #1
    sta count
86: lda cur_flo
    sec
    sbc tmp
    sta cur_flo
    lda cur_fhi
    sbc tmp + 1
    sta cur_fhi
    dec count
    bne 86b
10: inc p_frames, x
    bne 11f
    dec p_frames, x

    ; the pulse width
11: lda p_pwspd, x
    beq 13f
    bmi 12f
    clc
    adc p_pwlo, x
    sta p_pwlo, x
    lda p_pwhi, x
    adc #0
    sta p_pwhi, x
    cmp #$0F
    bcc 13f
    bra 121f
12: clc
    adc p_pwlo, x
    sta p_pwlo, x
    lda p_pwhi, x
    adc #$FF
    sta p_pwhi, x
    cmp #$01
    bcs 13f
121: lda p_pwspd, x             ; at an end: back the other way
    eor #$FF
    clc
    adc #1
    sta p_pwspd, x

    ; the filter's cutoff, falling to $18
13: lda p_cut, x
    beq 15f
    lda part_v0, x
    and #$E0
    tay
    lda p_cut, x
    sta $D416, y
    lda part_v1, x
    bmi 14f
    and #$E0
    tay
    lda p_cut, x
    sta $D416, y
14: ldz #6
    lda p_cut, x
    sec
    sbc [mp], z
    bcc 141f
    cmp #$18
    bcs 142f
141: lda #$18
142: sta p_cut, x

    ; to the voices
15: ldy part_v0, x
    jsr voice_out
    ldy part_v1, x
    bmi 16f
    lda part_detune, x
    beq 151f
    lda cur_flo                 ; a little higher: + freq >> 8
    clc
    adc cur_fhi
    sta cur_flo
    bcc 151f
    inc cur_fhi
151: jsr voice_out
16: rts

; Voice Y: the part's frequency, pulse width and waveform
voice_out:
    lda cur_flo
    sta $D400, y
    lda cur_fhi
    sta $D401, y
    lda p_pwlo, x
    sta $D402, y
    lda p_pwhi, x
    sta $D403, y
    lda cur_wave
    sta $D404, y
    rts

; cur_flo/cur_fhi: the frequency of note A (0-83, C0-B6)
note_freq:
    ldy #6
1:  cmp #12
    bcc 2f
    sbc #12
    dey
    bra 1b
2:  sty tmp
    asl
    tay
    lda freq_tab, y
    sta cur_flo
    lda freq_tab + 1, y
    sta cur_fhi
    ldy tmp
    beq 4f
3:  lsr cur_fhi
    ror cur_flo
    dey
    bne 3b
4:  rts
