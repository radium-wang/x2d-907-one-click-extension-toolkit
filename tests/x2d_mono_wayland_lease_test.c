#include "x2d_mono_wayland_lease.h"
#include <assert.h>
#include <stdio.h>

static int frees;
static void release(void *user, void *lease) {
    assert(user == lease);
    frees++;
}
int main(void) {
    x2d_mono_wayland_leases state;
    assert(x2d_mono_wayland_leases_init(&state) == 0);
    int wl[X2D_MONO_WAYLAND_MAX_LEASES + 1];
    int private_frame[X2D_MONO_WAYLAND_MAX_LEASES + 1];
    x2d_mono_wayland_ticket ticket[X2D_MONO_WAYLAND_MAX_LEASES + 1];
    for (size_t i = 0; i < X2D_MONO_WAYLAND_MAX_LEASES; ++i)
        assert(x2d_mono_wayland_lease_reserve(&state, &private_frame[i],
                    release, &private_frame[i], &ticket[i]) == 0);
    assert(x2d_mono_wayland_leases_outstanding(&state) == X2D_MONO_WAYLAND_MAX_LEASES);
    assert(x2d_mono_wayland_lease_reserve(&state, &private_frame[0],
                release, &private_frame[0], &ticket[8]) == -1);
    assert(x2d_mono_wayland_lease_reserve(&state, &private_frame[8],
                release, &private_frame[8], &ticket[8]) == -1);
    assert(x2d_mono_wayland_leases_destroy(&state) == -1);
    for (size_t i = 0; i < X2D_MONO_WAYLAND_MAX_LEASES; ++i)
        assert(x2d_mono_wayland_lease_bind_buffer(&state, ticket[i], &wl[i]) == 0);
    assert(x2d_mono_wayland_lease_bind_buffer(&state, ticket[1], &wl[0]) == -1);
    assert(x2d_mono_wayland_lease_compositor_released(&state, &wl[0]) == 0);
    assert(frees == 0);
    assert(x2d_mono_wayland_lease_buffer_destroyed(&state, &wl[0]) == 1);
    assert(frees == 1);
    assert(x2d_mono_wayland_lease_compositor_released(&state, &wl[0]) == -1);
    assert(x2d_mono_wayland_lease_reserve(&state, &private_frame[8],
                release, &private_frame[8], &ticket[8]) == 0);
    assert(x2d_mono_wayland_lease_bind_buffer(&state, ticket[0], &wl[0]) == -1);
    assert(x2d_mono_wayland_lease_cancel_unsubmitted(&state, ticket[8]) == 0);
    assert(frees == 2);
    assert(x2d_mono_wayland_lease_buffer_destroyed(&state, &wl[1]) == 0);
    assert(frees == 2);
    assert(x2d_mono_wayland_lease_compositor_released(&state, &wl[1]) == 1);
    for (size_t i = 2; i < X2D_MONO_WAYLAND_MAX_LEASES; ++i) {
        assert(x2d_mono_wayland_lease_compositor_released(&state, &wl[i]) == 0);
        assert(x2d_mono_wayland_lease_buffer_destroyed(&state, &wl[i]) == 1);
    }
    assert(frees == X2D_MONO_WAYLAND_MAX_LEASES + 1);
    assert(x2d_mono_wayland_leases_outstanding(&state) == 0);
    assert(x2d_mono_wayland_leases_destroy(&state) == 0);
    puts("x2d Wayland lease registry: OK");
    return 0;
}
