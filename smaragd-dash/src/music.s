; Smaragd Dash: the music player in 45GS02 assembly, for the song made by
; tools/mkmusic.py - the same as the C in src/music.c, write for write;
; tests/test_music.sh plays both (-DMUSIC_CHECK) and compares what they
; write to the SIDs, frame by frame.
;
; Six voices on the second ($D420, left) and fourth ($D460, right) SID;
; the sound effects keep the first and third. music_frame() is called
; once per frame; the song is written for 50 frames a second, so at 60
; (NTSC) every sixth frame is left out.
;
; Each voice's state lies in arrays of six (v_*, indexed by X): its place
; in its part of the song, its instrument (as an offset into song_instr),
; its SID registers, frequency, pulse width and the rest of src/music.c's
; struct voice. music_sid_l and music_sid_r say where the SIDs are.
;
; They change A, X, Y and __rc2-__rc12, which a caller does not keep.
; Z stays 0. src/music.c checks the song's layout these numbers stand for.

.global music_start, music_stop, music_frame, music_sid_l, music_sid_r, music_ntsc

TEMPO = 6                       ; SONG_TEMPO: frames per row
VOICES = 6                      ; SONG_VOICES
I_WAVE = 0                      ; struct instrument
I_AD = 1
I_SR = 2
I_PW = 3
I_PWM = 5
I_VIB_DELAY = 6
I_VIB_DEPTH = 7
I_ARP = 8
I_SWEEP = 9
I_NOISE = 10

ptr = __rc2                     ; the voice's SID registers
song = __rc4                    ; its place in the song
f = __rc6                       ; the frequency written
tmp = __rc8
cnt = __rc10
ins = __rc11                    ; its instrument: offset into song_instr
wave = __rc12

.section .data.music_s,"aw",@progbits
music_sid_l: .short $D420
music_sid_r: .short $D460

.section .bss.music_s,"aw",@nobits
v_plo:  .fill VOICES
v_phi:  .fill VOICES
v_in:   .fill VOICES
v_rlo:  .fill VOICES
v_rhi:  .fill VOICES
v_flo:  .fill VOICES
v_fhi:  .fill VOICES
v_pwlo: .fill VOICES
v_pwhi: .fill VOICES
v_pwm:  .fill VOICES            ; signed
v_note: .fill VOICES
v_len:  .fill VOICES            ; rows per note
v_rows: .fill VOICES            ; rows left of the current note
v_t:    .fill VOICES            ; frames since the note started
v_gate: .fill VOICES
row_frame:  .fill 1
is_row:     .fill 1
filter_t:   .fill 2
playing:    .fill 1
music_ntsc: .fill 1             ; not 0: NTSC
ntsc_frame: .fill 1             ; counts to 6: the sixth is left out
cutoff_lo:  .fill 1

.section .rodata.music_s,"a",@progbits
voice_off:                      ; a voice's registers in its SID
    .byte 0, 7, 14, 0, 7, 14
arp_steps:                      ; [arp][t % 3]: semitones
    .byte 0, 0, 0, 0, 3, 7, 0, 4, 7
vib_wave:
    .byte 0, 1, 2, 1, 0, $ff, $fe, $ff

.section .text.music_s,"ax",@progbits

; Silence, the filter on voice 2 (the bass) with resonance 10, low pass,
; full volume: the SID at ptr
sid_setup:
    lda #0
    ldy #24
1:  sta (ptr),y
    dey
    bpl 1b
    ldy #$17
    lda #$A2
    sta (ptr),y
    iny
    lda #$1F
    sta (ptr),y
    rts

sid_l:
    lda music_sid_l
    sta ptr
    lda music_sid_l+1
    sta ptr+1
    rts

sid_r:
    lda music_sid_r
    sta ptr
    lda music_sid_r+1
    sta ptr+1
    rts

music_start:
    jsr sid_l
    jsr sid_setup
    jsr sid_r
    jsr sid_setup
    ldx #0
1:  txa                         ; the start of its part, instrument 0
    asl
    tay
    lda song_voice,y
    sta v_plo,x
    lda song_voice+1,y
    sta v_phi,x
    stz v_in,x
    cpx #3                      ; its registers: voices 0-2 left, 3-5 right
    bcs 2f
    jsr sid_l
    bra 3f
2:  jsr sid_r
3:  clc
    lda ptr
    adc voice_off,x
    sta v_rlo,x
    lda ptr+1
    adc #0
    sta v_rhi,x
    lda #1
    sta v_rows,x
    sta v_len,x
    stz v_gate,x
    inx
    cpx #VOICES
    bne 1b
    lda #TEMPO - 1
    sta row_frame
    stz filter_t
    stz filter_t+1
    lda $D06F
    and #$80
    sta music_ntsc
    stz ntsc_frame
    lda #1
    sta playing
    rts

music_stop:
    stz playing
    jsr sid_l
    ldy #$18
    lda #0
    sta (ptr),y
    jsr sid_r
    lda #0
    sta (ptr),y
    ldx #0
1:  jsr voice_regs
    ldy #4
    lda #0
    sta (ptr),y
    inx
    cpx #VOICES
    bne 1b
    rts

voice_regs:
    lda v_rlo,x
    sta ptr
    lda v_rhi,x
    sta ptr+1
    rts

music_frame:
    lda playing
    bne 1f
    rts
1:  lda music_ntsc
    beq 2f
    inc ntsc_frame
    lda ntsc_frame
    cmp #6
    bne 2f
    stz ntsc_frame
    rts
2:  stz is_row
    inc row_frame
    lda row_frame
    cmp #TEMPO
    bne 3f
    stz row_frame
    inc is_row
3:  ldx #0
voice:
    jsr voice_regs
    lda is_row
    beq 1f
    dec v_rows,x
    bne 1f
    jsr next_event
1:  ldy v_in,x
    sty ins
    lda v_gate,x
    bne 2f
    jmp next_voice
2:  lda v_rows,x                ; the gate closes shortly before the next
    cmp #1                      ; note, so that it starts afresh
    bne 3f
    lda row_frame
    cmp #TEMPO - 2
    bne 3f
    stz v_gate,x
    lda song_instr+I_WAVE,y
    ldy #4
    sta (ptr),y
    jmp next_voice
3:  lda v_flo,x
    sta f
    lda v_fhi,x
    sta f+1
    lda song_instr+I_ARP,y
    beq sweep
    sta tmp                     ; arpeggio: the note and its chord's
    asl                         ; steps in turn
    adc tmp
    sta tmp
    lda v_t,x
4:  cmp #3
    bcc 5f
    sbc #3
    bra 4b
5:  clc
    adc tmp
    tay
    lda arp_steps,y
    clc
    adc v_note,x
    asl
    tay
    lda note_freq,y
    sta f
    lda note_freq+1,y
    sta f+1
    bra pulse
sweep:
    lda song_instr+I_SWEEP,y    ; down, by its part
    beq vibrato
    sta cnt
    lda v_flo,x
    sta tmp
    lda v_fhi,x
    sta tmp+1
1:  lsr tmp+1
    ror tmp
    dec cnt
    bne 1b
    sec
    lda v_flo,x
    sbc tmp
    sta v_flo,x
    sta f
    lda v_fhi,x
    sbc tmp+1
    sta v_fhi,x
    sta f+1
    bra pulse
vibrato:
    lda song_instr+I_VIB_DEPTH,y
    beq pulse
    sta cnt
    lda song_instr+I_VIB_DELAY,y
    cmp v_t,x
    bcs pulse                   ; only after the delay
    lda f
    sta tmp
    lda f+1
    sta tmp+1
1:  lsr tmp+1                   ; tmp: f by its depth's part
    ror tmp
    dec cnt
    bne 1b
    lda v_t,x
    and #7
    tay
    lda vib_wave,y              ; f + tmp * wave / 2
    beq pulse
    bpl 3f
    cmp #$FF
    bne 2f
    lsr tmp+1
    ror tmp
2:  sec
    lda f
    sbc tmp
    sta f
    lda f+1
    sbc tmp+1
    sta f+1
    bra pulse
3:  cmp #1
    bne 4f
    lsr tmp+1
    ror tmp
4:  clc
    lda f
    adc tmp
    sta f
    lda f+1
    adc tmp+1
    sta f+1
pulse:
    lda v_pwm,x                 ; the pulse width goes to and fro
    beq 3f
    ldy #0
    ora #0
    bpl 1f
    dey
1:  clc
    adc v_pwlo,x
    sta v_pwlo,x
    tya
    adc v_pwhi,x
    sta v_pwhi,x
    cmp #2                      ; below $200 or above $E00: back
    bcc 2f
    cmp #$0E
    bcc 3f
    bne 2f
    lda v_pwlo,x
    beq 3f
2:  lda #0
    sec
    sbc v_pwm,x
    sta v_pwm,x
3:  ldy ins
    lda v_t,x                   ; noise at first (the drums), then the wave
    cmp song_instr+I_NOISE,y
    lda #$80
    bcc 4f
    lda song_instr+I_WAVE,y
4:  ora #1
    sta wave
    ldy #0
    lda f
    sta (ptr),y
    iny
    lda f+1
    sta (ptr),y
    iny
    lda v_pwlo,x
    sta (ptr),y
    iny
    lda v_pwhi,x
    sta (ptr),y
    iny
    lda wave
    sta (ptr),y
    lda v_t,x
    cmp #255
    beq next_voice
    inc v_t,x
next_voice:
    inx
    cpx #VOICES
    beq filter
    jmp voice

; The bass filter opens and closes slowly (one cycle every 8 bars): the
; cutoff $180 + phase, up to $380, and down again
filter:
    inc filter_t
    bne 1f
    inc filter_t+1
1:  lda filter_t
    sta tmp
    lda filter_t+1
    and #3
    sta tmp+1
    cmp #2
    bcc 2f
    lda #$FF
    sec
    sbc tmp
    sta tmp
    lda #3
    sbc tmp+1
    sta tmp+1
2:  clc
    lda tmp
    adc #$80
    sta tmp
    lda tmp+1
    adc #1
    sta tmp+1
    lda tmp
    and #7
    sta cutoff_lo
    ldy #3
3:  lsr tmp+1
    ror tmp
    dey
    bne 3b
    jsr sid_l
    jsr put_filter
    jsr sid_r
put_filter:
    ldy #$15
    lda cutoff_lo
    sta (ptr),y
    iny
    lda tmp
    sta (ptr),y
    rts

; The voice X's next note or rest: its lengths and instruments on the
; way, back to the start of its part at its end
next_event:
    lda v_plo,x
    sta song
    lda v_phi,x
    sta song+1
1:  lda (song),z
    inw song
    cmp #$FF
    bne 2f
    txa
    asl
    tay
    lda song_voice,y
    sta song
    lda song_voice+1,y
    sta song+1
    bra 1b
2:  cmp #$C0
    bcc 3f
    and #$3F                    ; a length
    clc
    adc #1
    sta v_len,x
    bra 1b
3:  cmp #$80
    bcc 4f
    and #$3F                    ; an instrument: 11 bytes each
    sta tmp
    asl
    asl
    adc tmp
    asl
    adc tmp
    sta v_in,x
    bra 1b
4:  pha                         ; a note or a rest
    lda song
    sta v_plo,x
    lda song+1
    sta v_phi,x
    lda v_len,x
    sta v_rows,x
    ldy v_in,x
    pla
    cmp #$7F
    bne 5f
    lda song_instr+I_WAVE,y     ; a rest: the gate closed
    ldy #4
    sta (ptr),y
    stz v_gate,x
    rts
5:  sta v_note,x
    asl
    phy
    tay
    lda note_freq,y
    sta v_flo,x
    lda note_freq+1,y
    sta v_fhi,x
    ply
    lda song_instr+I_PW,y
    sta v_pwlo,x
    lda song_instr+I_PW+1,y
    sta v_pwhi,x
    lda song_instr+I_PWM,y
    sta v_pwm,x
    stz v_t,x
    lda #1
    sta v_gate,x
    lda song_instr+I_AD,y
    sta tmp
    lda song_instr+I_SR,y
    sta tmp+1
    ldy #4
    lda #$08                    ; test bit: the oscillator restarts
    sta (ptr),y
    iny
    lda tmp
    sta (ptr),y
    iny
    lda tmp+1
    sta (ptr),y
    rts
