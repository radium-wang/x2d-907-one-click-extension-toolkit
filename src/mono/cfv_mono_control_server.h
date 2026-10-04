#ifndef CFV_MONO_CONTROL_SERVER_H
#define CFV_MONO_CONTROL_SERVER_H

#include "cfv_mono_control.h"
#include <stdatomic.h>

/* Serve one already-accepted connection. No request data reaches a shell. */
int cfv_mono_control_respond_fd(cfv_mono_control *control, int fd);

/* Loopback-only endpoint for the camera-service integration. The caller owns
 * its thread and lifecycle. This function is not auto-started by a ctor. */
int cfv_mono_control_serve(cfv_mono_control *control, unsigned short port,
                           const atomic_int *stop);

#endif
