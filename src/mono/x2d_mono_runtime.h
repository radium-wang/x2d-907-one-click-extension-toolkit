#ifndef X2D_MONO_RUNTIME_H
#define X2D_MONO_RUNTIME_H
#include "cfv_mono_control.h"

/* Shared process-local state used by the three image hooks.  A hook must
 * withdraw its readiness on any contract or conversion fault. */
int x2d_mono_runtime_requested(void);
int x2d_mono_runtime_enabled(void);
void x2d_mono_runtime_ready(unsigned route, int ready);
unsigned x2d_mono_runtime_ready_mask(void);
int x2d_mono_runtime_start(void);
void x2d_mono_runtime_stop(void);
#endif
