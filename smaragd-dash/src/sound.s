; Smaragd Dash: the sound effects in 45GS02 assembly - the same as the C in
; src/sound.c, write for write; tests/test_asm.sh plays both (-DASM_CHECK)
; with the same random numbers and compares what they write to the SIDs.
;
; Every effect plays on two SIDs alike, left and right: voices 1-3 on the
; first ($D400) and the third ($D440), voices 4-6 on the second ($D420)
; and the fourth ($D460), which the title's music has (src/music.s) - in a
; cave they are the effects'. sound_sid says where the first SID is.
;
; A sound starts in two parts: play closes the gate and sets the test bit
; (the oscillator and the noise generator start afresh), sound_frame opens
; the gate with the waveform - a SID clocked at 1 MHz, as the real
; MEGA65's, may not see a gate closed and opened again a microsecond later.
; A sound is not cut off by one of lower rank in the first third of its
; decay, while it is loud; the sounds outside the ticks have the top rank.
; The waveform goes off when the envelope (attack 0, sustain 0) has died
; away: a SID still lets a voice at envelope 0 be heard faintly.
;
; The amoeba and the magic wall sound as long as they are alive, as in
; GDash, whose looped sounds come from the C64: a triangle on voice 6 that
; takes a random frequency (its high byte) every frame - the amoeba's
; 120-490 Hz each frame, the magic wall's 2020-2380 Hz every second one,
; both alive: the frames take turns. A sound of voice 6 interrupts it; it
; comes back when that one has died away.
;
; sound_tick(events): events (SND_*, src/engine.h) in A, X, __rc2, __rc3.
; They change A, X, Y and __rc2-__rc3, which a caller does not keep (and
; call rnd()). Z stays 0.

.global sound_init, sound_off, sound_still, sound_frame, sound_tick
.global sound_crackle, sound_clock, sound_bonus, sound_exit, sound_life, sound_sid

VOICES = 6
HUM_VOICE = 5
HUM_AMOEBA = 1
HUM_MAGIC = 2
RIGHT = $40                     ; the third SID from the first (the fourth from the second)
TOP = 255
TEST = $08
TRI = $10
SAW = $20
PULSE = $40
NOISE = $80

ptr = __rc2                     ; the voice's registers

.section .data.sound_s,"aw",@progbits
sound_sid: .short $D400

.section .bss.sound_s,"aw",@nobits
left:    .fill VOICES           ; frames until the voice is switched off
rank:    .fill VOICES
hold:    .fill VOICES
start:   .fill VOICES           ; the waveform to open the gate with, 0: none
hum:     .fill 1                ; HUM_* the last tick wanted; 0: quiet
humming: .fill 1                ; the hum has the voice, its gate is open
hum_odd: .fill 1                ; the frames take turns
events:  .fill 4
done:    .fill 1                ; a bit for each voice that has had its sound
p_rank:  .fill 1                ; play's sound
p_freq:  .fill 2
p_wave:  .fill 1
p_ad:    .fill 1
m_a:     .fill 1                ; mul's
m_b:     .fill 1
m_lo:    .fill 1
m_hi:    .fill 1

.section .rodata.sound_s,"a",@progbits
; Frames until an envelope with this decay has died away, at 60 frames a
; second and with two to spare (only decays up to 11 are used)
decay_frames:
    .byte 3, 4, 5, 7, 10, 13, 15, 17, 21, 47, 92, 146, 182, 255, 255, 255
voice_off:                      ; a voice's registers from the first SID's
    .byte 0, 7, 14, $20, $27, $2E
voice_bit:
    .byte 1, 2, 4, 8, 16, 32

; The sounds of a cave tick: on each voice the first one wanted plays, and
; it ranks above those behind it. The flag as its byte in events and its
; bit there; the frequency goes up by rnd() times vary.
.macro fx byte, mask, voice, freq, vary, wave, ad
    .byte \byte, \mask, \voice, <(\freq), >(\freq), \vary, \wave, \ad
.endm
FX = 8                          ; bytes per sound
tick_fx:
    ; voice 1: what Rockford takes (and the time counted into the score)
    fx 1, $01, 0, $3800, 0, PULSE, $0A   ; SND_CLOCK: a bell
    fx 0, $04, 0, $6800, 16, TRI, $09    ; SND_COLLECT
    fx 1, $10, 0, $5400, 0, PULSE, $08   ; SND_PICKUP
    ; voice 2: what falls
    fx 1, $02, 1, $2800, 0, NOISE, $05   ; SND_NUT: a crack
    fx 0, $01, 1, $0700, 0, NOISE, $07   ; SND_BOULDER
    ; voice 3: diamonds landing (and the exit, the last seconds, a life)
    fx 2, $08, 2, $2000, 0, NOISE, $08   ; SND_CRACK: Rockford hatches
    fx 0, $02, 2, $3000, 64, TRI, $06    ; SND_DIAMOND
    ; voice 4: explosions and machines
    fx 0, $20, 3, $1400, 0, NOISE, $0B   ; SND_EXPLODE
    fx 1, $20, 3, $0B00, 0, SAW, $07     ; SND_DOOR: a creak
    fx 2, $02, 3, $4000, 0, NOISE, $02   ; SND_HAMMER: a rattle
    fx 2, $01, 3, $3000, 0, PULSE, $02   ; SND_BOMB: a tick
    fx 1, $08, 3, $0900, 0, PULSE, $06   ; SND_GROW: a low knock
    ; voice 5: Rockford's steps
    fx 0, $08, 4, $B000, 0, NOISE, $03   ; SND_DIRT
    fx 0, $10, 4, $F000, 0, NOISE, $01   ; SND_STEP
    ; voice 6: what goes on in the cave
    fx 1, $80, 5, $7000, 0, SAW, $09     ; SND_TELEPORT
    fx 1, $40, 5, $4800, 0, PULSE, $01   ; SND_SWITCH: a click
    fx 1, $04, 5, $1800, 8, PULSE, $05   ; SND_SLIME: a blob
    fx 2, $04, 5, $D000, 0, NOISE, $03   ; SND_HISS
TICK_FX = (. - tick_fx) / FX

; The sounds outside the ticks (top rank): sound_crackle, sound_clock,
; sound_bonus, sound_exit, sound_life
own_fx:
    fx 0, 0, 2, $8000, 128, NOISE, $01   ; covering/uncovering the cave
    fx 0, 0, 2, $2400, 0, PULSE, $05     ; last seconds
    fx 0, 0, 0, $4000, 32, TRI, $02      ; time counted into the score
    fx 0, 0, 2, $2000, 0, NOISE, $08     ; the exit opens
    fx 0, 0, 2, $5800, 0, SAW, $0A       ; an extra life

.section .text.sound_s,"ax",@progbits

; ptr: the registers of voice X
voice_regs:
    clc
    lda sound_sid
    adc voice_off,x
    sta ptr
    lda sound_sid+1
    adc #0
    sta ptr+1
    rts

; A into register Y of the voice at ptr, left and right
put2:
    sta (ptr),y
    pha
    tya
    eor #RIGHT
    tay
    pla
    sta (ptr),y
    pha
    tya
    eor #RIGHT
    tay
    pla
    rts

; m_lo, m_hi: A times m_b
mul:
    sta m_a
    stz m_lo
    stz m_hi
    ldy #8
1:  asl m_lo
    rol m_hi
    asl m_b
    bcc 2f
    clc
    lda m_lo
    adc m_a
    sta m_lo
    bcc 2f
    inc m_hi
2:  dey
    bne 1b
    rts

sound_init:
    lda sound_sid
    sta ptr
    lda sound_sid+1
    sta ptr+1
    ldy #0                      ; registers 0-24 of each SID 0, volume full
1:  tya
    and #$1F
    cmp #25
    bcs 3f
    cmp #24
    lda #0
    bcc 2f
    lda #$0F
2:  sta (ptr),y
3:  iny
    bpl 1b
    rts

sound_off:
    ldx #0
1:  jsr voice_regs
    ldy #4
    lda #0
    jsr put2
    stz left,x
    stz hold,x
    stz start,x
    inx
    cpx #VOICES
    bne 1b
    stz hum
    stz humming
    rts

sound_still:
    stz hum
    rts

; Start the sound p_* on voice X (0-5) of rank p_rank. The gate opens in
; the next sound_frame (start).
play:
    lda hold,x
    beq 1f
    lda p_rank
    cmp rank,x
    bcs 1f
    rts
1:  lda p_rank
    sta rank,x
    cpx #HUM_VOICE
    bne 2f
    stz humming
2:  lda p_ad
    and #15
    tay
    lda decay_frames,y
    sta left,x
    ldy #0                      ; hold: a third of it
3:  cmp #3
    bcc 4f
    sbc #3
    iny
    bra 3b
4:  tya
    sta hold,x
    lda p_wave
    sta start,x
    jsr voice_regs
    ldy #4
    lda #TEST
    jsr put2
    ldy #0
    lda p_freq
    jsr put2
    iny
    lda p_freq+1
    jsr put2
    iny
    lda #0
    jsr put2
    iny
    lda #$08                    ; pulse width 50 %
    jsr put2
    ldy #5
    lda p_ad
    jsr put2
    iny
    lda #0
    jmp put2

; The sound at Y in tick_fx (or own_fx) into p_*, with its frequency
; varied; its voice in X
fx_take:
    lda tick_fx+3,y
    sta p_freq
    lda tick_fx+4,y
    sta p_freq+1
    lda tick_fx+6,y
    sta p_wave
    lda tick_fx+7,y
    sta p_ad
    lda tick_fx+5,y
    beq 1f
    sta m_b
    phy
    jsr rnd
    jsr mul
    ply
    clc
    lda p_freq
    adc m_lo
    sta p_freq
    lda p_freq+1
    adc m_hi
    sta p_freq+1
1:  ldx tick_fx+2,y
    rts

sound_crackle:
    ldy #(own_fx - tick_fx)
    bra own
sound_clock:
    ldy #(own_fx - tick_fx) + FX
    bra own
sound_bonus:
    ldy #(own_fx - tick_fx) + 2 * FX
    bra own
sound_exit:
    ldy #(own_fx - tick_fx) + 3 * FX
    bra own
sound_life:
    ldy #(own_fx - tick_fx) + 4 * FX
own:
    lda #TOP
    sta p_rank
    jsr fx_take
    jmp play

sound_tick:
    sta events
    stx events+1
    lda __rc2
    sta events+2
    lda __rc3
    sta events+3
    lda events                  ; SND_MAGIC, else SND_AMOEBA
    ldx #HUM_MAGIC
    bit #$40
    bne 1f
    ldx #HUM_AMOEBA
    bit #$80
    bne 1f
    ldx #0
1:  stx hum
    stz done
    ldy #0                      ; the sound's place in tick_fx
    lda #TICK_FX
    sta p_rank                  ; TICK_FX less its number
2:  ldx tick_fx,y
    lda events,x
    and tick_fx+1,y
    beq 3f
    ldx tick_fx+2,y
    lda voice_bit,x
    bit done
    bne 3f
    ora done
    sta done
    phy
    jsr fx_take
    jsr play
    ply
3:  dec p_rank
    tya
    clc
    adc #FX
    tay
    cpy #TICK_FX * FX
    bne 2b
    rts

sound_frame:
    ldx #0
1:  lda start,x
    beq 2f
    ora #1                      ; the frames of the sound count from here
    pha
    jsr voice_regs
    pla
    ldy #4
    jsr put2
    stz start,x
    bra 5f
2:  lda hold,x
    beq 3f
    dec hold,x
3:  lda left,x
    beq 4f
    dec left,x
    bne 5f
    jsr voice_regs              ; died away: the waveform off, the gate
    ldy #4                      ; stays closed for a frame
    lda #0
    jsr put2
    bra 5f
4:  cpx #HUM_VOICE
    bne 5f
    jsr hum_frame
5:  inx
    cpx #VOICES
    bne 1b
    rts

; Voice 6 in a frame without a sound of its own: the hum starts, goes on
; with a new frequency or ends (its waveform goes off with left, as a
; sound's does)
hum_frame:
    lda hum
    bne 2f
    lda humming
    beq 1f
    stz humming
    lda #3
    sta left+HUM_VOICE
    ldx #HUM_VOICE
    jsr voice_regs
    ldy #4
    lda #TRI                    ; gate closed: release 0
    jsr put2
1:  rts
2:  lda hum_odd
    eor #1
    sta hum_odd
    lda hum                     ; the magic wall: every other frame when
    and #HUM_MAGIC              ; both are alive
    beq 4f
    lda hum_odd
    bne 3f
    lda hum
    and #HUM_AMOEBA
    bne 4f
3:  lda hum_odd                 ; the magic wall alone keeps its frequency
    bne 5f                      ; for two frames
    lda humming
    bne 1b
5:  lda #$86
    bra 6f
4:  lda #$08                    ; the amoeba
6:  pha
    lda #25                     ; + rnd() * 25 / 256
    sta m_b
    jsr rnd
    jsr mul
    pla
    clc
    adc m_hi
    pha
    ldx #HUM_VOICE
    jsr voice_regs
    ldy #0
    tya
    jsr put2
    iny
    pla
    jsr put2
    lda humming
    bne 7f
    ldy #5
    lda #$20                    ; attack 2: no click
    jsr put2
    iny
    lda #$70                    ; sustain 7, release 0
    jsr put2
    ldy #4
    lda #TRI | 1
    jsr put2
7:  lda #1
    sta humming
    stz rank+HUM_VOICE
    stz hold+HUM_VOICE
    ldx #HUM_VOICE
    rts
