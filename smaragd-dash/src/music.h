// Smaragd Dash: title music (src/music.s, song from tools/mkmusic.py)

#ifndef MUSIC_H
#define MUSIC_H

void music_start(void);
void music_stop(void);
void music_frame(void);  // once per frame

#ifdef ASM_CHECK
void music_check(void);  // src/music.c: the C player against src/music.s
#endif

#endif
