#ifndef X2D_MONO_WAYLAND_POOL_H
#define X2D_MONO_WAYLAND_POOL_H

#include <pthread.h>
#include <stddef.h>

#define X2D_MONO_WAYLAND_POOL_MAX 8u

typedef void (*x2d_mono_wayland_pool_free_fn)(void *user, void *lease);
typedef enum {
    X2D_MONO_POOL_EMPTY = 0,
    X2D_MONO_POOL_AVAILABLE,
    X2D_MONO_POOL_RESERVED,
    X2D_MONO_POOL_IN_FLIGHT
} x2d_mono_wayland_pool_state;
typedef struct {
    void *stable_vmem;
    void *wl_buffer;
    void *lease;
    x2d_mono_wayland_pool_free_fn free_lease;
    void *user;
    x2d_mono_wayland_pool_state state;
    unsigned retiring;
    unsigned proxy_destroyed;
} x2d_mono_wayland_pool_slot;
typedef struct {
    pthread_mutex_t mutex;
    x2d_mono_wayland_pool_slot slots[X2D_MONO_WAYLAND_POOL_MAX];
} x2d_mono_wayland_pool;

int x2d_mono_wayland_pool_init(x2d_mono_wayland_pool *pool);
/* Add a private VMem lease once. The same handle is reused each time the
 * compositor releases its wl_buffer. A fresh handle every frame defeats the
 * stock BufferBase cache and would fill this pool immediately. */
int x2d_mono_wayland_pool_add(x2d_mono_wayland_pool *pool,
                              void *stable_vmem, void *lease,
                              x2d_mono_wayland_pool_free_fn free_lease,
                              void *user);
/* Returns a slot index or -1 when all private buffers are busy/retiring.
 * Caller must forward the stock frame for that one frame. */
int x2d_mono_wayland_pool_reserve(x2d_mono_wayland_pool *pool);
/* After allocProtBuffers creates the first wl_buffer, bind it before push.
 * Future presentations must find this same wl_buffer for the stable VMem. */
int x2d_mono_wayland_pool_bind_buffer(x2d_mono_wayland_pool *pool,
                                      int slot_index, void *wl_buffer);
/* Mark IN_FLIGHT before invoking a call that may synchronously deliver a
 * release event. An ambiguous stock return leaves it IN_FLIGHT. */
int x2d_mono_wayland_pool_submit_begin(x2d_mono_wayland_pool *pool,
                                       int slot_index);
/* Only a reserved, never-submitted frame may be canceled. */
int x2d_mono_wayland_pool_abort_unsubmitted(x2d_mono_wayland_pool *pool,
                                            int slot_index);
int x2d_mono_wayland_pool_compositor_released(x2d_mono_wayland_pool *pool,
                                              void *wl_buffer);
/* Signal when the tracked wl_buffer proxy is destroyed by the stock path. */
int x2d_mono_wayland_pool_proxy_destroyed(x2d_mono_wayland_pool *pool,
                                          void *wl_buffer);
/* Stop new reservations. Leases are freed only after the proxy is destroyed
 * and any in-flight presentation has received its compositor release. */
void x2d_mono_wayland_pool_retire(x2d_mono_wayland_pool *pool);
x2d_mono_wayland_pool_state x2d_mono_wayland_pool_state_of(
    x2d_mono_wayland_pool *pool, int slot_index);
size_t x2d_mono_wayland_pool_live(x2d_mono_wayland_pool *pool);
int x2d_mono_wayland_pool_destroy(x2d_mono_wayland_pool *pool);

#endif
