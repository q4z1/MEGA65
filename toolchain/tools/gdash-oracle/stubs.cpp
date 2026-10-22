// GDash's settings and palettes that its cave code refers to, for the oracle
#include <glib.h>
#include "cave/colors.hpp"
bool gd_import_as_all_caves_selectable = false;
bool gd_use_bdcff_highscore = false;
bool gd_particle_effects = false;
bool gd_alternate_vertical_animation = false;
gboolean gd_param_debug = FALSE;
int gd_c64_palette = 0, gd_c64dtv_palette = 0, gd_atari_palette = 0;
#include <string>
std::string gd_last_cave_file;  // settings.cpp's
