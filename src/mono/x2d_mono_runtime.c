#define _POSIX_C_SOURCE 200809L
#include "x2d_mono_runtime.h"
#include "cfv_mono_control_server.h"
#include "cfv_mono_pref.h"
#include <pthread.h>
#include <stdatomic.h>

static cfv_mono_control mono_control;
static pthread_once_t init_once = PTHREAD_ONCE_INIT;
static pthread_t server_thread;
static atomic_int running;
static atomic_int stopping;

static void init_control(void) {
    cfv_mono_control_init(&mono_control, CFV_MONO_FEATURE_PATH,
                          CFV_MONO_PREF_PATH);
}
static void *server_main(void *unused) {
    (void)unused;
    cfv_mono_control_serve(&mono_control, 18766, &stopping);
    atomic_store(&running, 0);
    return 0;
}
int x2d_mono_runtime_start(void) {
    pthread_once(&init_once, init_control);
    int expected = 0;
    if (!atomic_compare_exchange_strong(&running, &expected, 1)) return 0;
    atomic_store(&stopping, 0);
    if (pthread_create(&server_thread, 0, server_main, 0)) {
        atomic_store(&running, 0);
        return -1;
    }
    pthread_detach(server_thread);
    return 0;
}
void x2d_mono_runtime_stop(void) { atomic_store(&stopping, 1); }
void x2d_mono_runtime_ready(unsigned route, int ready) {
    pthread_once(&init_once, init_control);
    cfv_mono_control_set_ready(&mono_control, route, ready);
}
unsigned x2d_mono_runtime_ready_mask(void) {
    pthread_once(&init_once, init_control);
    return atomic_load(&mono_control.ready_mask);
}
int x2d_mono_runtime_requested(void) {
    pthread_once(&init_once, init_control);
    return cfv_mono_control_requested(&mono_control);
}
int x2d_mono_runtime_enabled(void) {
    pthread_once(&init_once, init_control);
    return cfv_mono_control_effective(&mono_control);
}
#ifdef __ANDROID__
__attribute__((constructor)) static void start_for_camera_service(void) {
    (void)x2d_mono_runtime_start();
}
#endif
