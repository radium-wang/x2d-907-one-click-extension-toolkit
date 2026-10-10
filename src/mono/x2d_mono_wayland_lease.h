#ifndef X2D_MONO_WAYLAND_LEASE_H
#define X2D_MONO_WAYLAND_LEASE_H

#include <pthread.h>
#include <stddef.h>

/* Hard cap: if no lease slot is available, the caller must forward stock. */
#define X2D_MONO_WAYLAND_MAX_LEASES 8u

typedef void (*x2d_mono_wayland_release_fn)(void *user, void *lease);
typedef struct {
    size_t slot;
    unsigned generation;
} x2d_mono_wayland_ticket;
typedef struct {
    void *wl_buffer;
    void *lease;
    x2d_mono_wayland_release_fn release;
    void *user;
    unsigned generation;
    unsigned compositor_released;
    unsigned buffer_destroyed;
} x2d_mono_wayland_lease_slot;
typedef struct {
    pthread_mutex_t mutex;
    x2d_mono_wayland_lease_slot slots[X2D_MONO_WAYLAND_MAX_LEASES];
} x2d_mono_wayland_leases;

int x2d_mono_wayland_leases_init(x2d_mono_wayland_leases *leases);
/* Reserve BEFORE handing private VMem to allocProtBuffers. Full registry or
 * duplicate lease returns -1; the private candidate stays with the caller. */
int x2d_mono_wayland_lease_reserve(x2d_mono_wayland_leases *leases,
                                   void *lease,
                                   x2d_mono_wayland_release_fn release,
                                   void *user,
                                   x2d_mono_wayland_ticket *ticket);
/* Bind the wl_buffer returned by allocProtBuffers, BEFORE pushBuffer. On an
 * ambiguous failure, keep the reservation quarantined until ownership is
 * independently resolved; never free a potentially submitted lease. */
int x2d_mono_wayland_lease_bind_buffer(x2d_mono_wayland_leases *leases,
                                       x2d_mono_wayland_ticket ticket,
                                       void *wl_buffer);
/* Cancel only if the adapter has proven there was no Wayland submission or
 * retained vendor reference. Calls release once. */
int x2d_mono_wayland_lease_cancel_unsubmitted(
    x2d_mono_wayland_leases *leases, x2d_mono_wayland_ticket ticket);
/* Invoke from verified WaylandControl::bufferRelease and BufferBase
 * destruction hooks. A lease is freed only after BOTH events. */
int x2d_mono_wayland_lease_compositor_released(
    x2d_mono_wayland_leases *leases, void *wl_buffer);
int x2d_mono_wayland_lease_buffer_destroyed(
    x2d_mono_wayland_leases *leases, void *wl_buffer);
size_t x2d_mono_wayland_leases_outstanding(x2d_mono_wayland_leases *leases);
int x2d_mono_wayland_leases_destroy(x2d_mono_wayland_leases *leases);

#endif
