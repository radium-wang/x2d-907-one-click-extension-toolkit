#include "x2d_mono_wayland_lease.h"
#include <stdint.h>
#include <string.h>

int x2d_mono_wayland_leases_init(x2d_mono_wayland_leases *leases) {
    if (!leases) return -1;
    memset(leases, 0, sizeof *leases);
    return pthread_mutex_init(&leases->mutex, NULL) == 0 ? 0 : -1;
}

int x2d_mono_wayland_lease_reserve(x2d_mono_wayland_leases *leases,
                                   void *lease,
                                   x2d_mono_wayland_release_fn release,
                                   void *user,
                                   x2d_mono_wayland_ticket *ticket) {
    if (!leases || !lease || !release || !ticket) return -1;
    if (pthread_mutex_lock(&leases->mutex) != 0) return -1;
    size_t free_index = X2D_MONO_WAYLAND_MAX_LEASES;
    for (size_t i = 0; i < X2D_MONO_WAYLAND_MAX_LEASES; ++i) {
        if (leases->slots[i].lease == lease) {
            pthread_mutex_unlock(&leases->mutex);
            return -1;
        }
        if (!leases->slots[i].lease && free_index == X2D_MONO_WAYLAND_MAX_LEASES)
            free_index = i;
    }
    if (free_index == X2D_MONO_WAYLAND_MAX_LEASES) {
        pthread_mutex_unlock(&leases->mutex);
        return -1;
    }
    x2d_mono_wayland_lease_slot *slot = &leases->slots[free_index];
    unsigned generation = slot->generation + 1u;
    if (!generation) generation = 1u;
    *slot = (x2d_mono_wayland_lease_slot){
        .lease = lease, .release = release, .user = user,
        .generation = generation
    };
    *ticket = (x2d_mono_wayland_ticket){free_index, generation};
    pthread_mutex_unlock(&leases->mutex);
    return 0;
}

int x2d_mono_wayland_lease_bind_buffer(x2d_mono_wayland_leases *leases,
                                       x2d_mono_wayland_ticket ticket,
                                       void *wl_buffer) {
    if (!leases || !wl_buffer || ticket.slot >= X2D_MONO_WAYLAND_MAX_LEASES)
        return -1;
    if (pthread_mutex_lock(&leases->mutex) != 0) return -1;
    x2d_mono_wayland_lease_slot *slot = &leases->slots[ticket.slot];
    if (!slot->lease || slot->generation != ticket.generation ||
        slot->wl_buffer) {
        pthread_mutex_unlock(&leases->mutex);
        return -1;
    }
    for (size_t i = 0; i < X2D_MONO_WAYLAND_MAX_LEASES; ++i) {
        if (leases->slots[i].wl_buffer == wl_buffer) {
            pthread_mutex_unlock(&leases->mutex);
            return -1;
        }
    }
    slot->wl_buffer = wl_buffer;
    pthread_mutex_unlock(&leases->mutex);
    return 0;
}

int x2d_mono_wayland_lease_cancel_unsubmitted(
    x2d_mono_wayland_leases *leases, x2d_mono_wayland_ticket ticket) {
    if (!leases || ticket.slot >= X2D_MONO_WAYLAND_MAX_LEASES)
        return -1;
    if (pthread_mutex_lock(&leases->mutex) != 0) return -1;
    x2d_mono_wayland_lease_slot *slot = &leases->slots[ticket.slot];
    if (!slot->lease || slot->generation != ticket.generation ||
        slot->wl_buffer) {
        pthread_mutex_unlock(&leases->mutex);
        return -1;
    }
    x2d_mono_wayland_lease_slot owned = *slot;
    unsigned generation = slot->generation;
    memset(slot, 0, sizeof *slot);
    slot->generation = generation;
    pthread_mutex_unlock(&leases->mutex);
    owned.release(owned.user, owned.lease);
    return 0;
}

static int mark(x2d_mono_wayland_leases *leases, void *wl_buffer,
                int is_compositor_release) {
    if (!leases || !wl_buffer) return -1;
    if (pthread_mutex_lock(&leases->mutex) != 0) return -1;
    for (size_t i = 0; i < X2D_MONO_WAYLAND_MAX_LEASES; ++i) {
        x2d_mono_wayland_lease_slot *slot = &leases->slots[i];
        if (slot->wl_buffer != wl_buffer) continue;
        if (is_compositor_release)
            slot->compositor_released = 1;
        else
            slot->buffer_destroyed = 1;
        if (slot->compositor_released && slot->buffer_destroyed) {
            x2d_mono_wayland_lease_slot owned = *slot;
            unsigned generation = slot->generation;
            memset(slot, 0, sizeof *slot);
            slot->generation = generation;
            pthread_mutex_unlock(&leases->mutex);
            owned.release(owned.user, owned.lease);
            return 1;
        }
        pthread_mutex_unlock(&leases->mutex);
        return 0;
    }
    pthread_mutex_unlock(&leases->mutex);
    return -1;
}

int x2d_mono_wayland_lease_compositor_released(
    x2d_mono_wayland_leases *leases, void *wl_buffer) {
    return mark(leases, wl_buffer, 1);
}
int x2d_mono_wayland_lease_buffer_destroyed(
    x2d_mono_wayland_leases *leases, void *wl_buffer) {
    return mark(leases, wl_buffer, 0);
}
size_t x2d_mono_wayland_leases_outstanding(x2d_mono_wayland_leases *leases) {
    if (!leases || pthread_mutex_lock(&leases->mutex) != 0) return SIZE_MAX;
    size_t count = 0;
    for (size_t i = 0; i < X2D_MONO_WAYLAND_MAX_LEASES; ++i)
        count += leases->slots[i].lease != NULL;
    pthread_mutex_unlock(&leases->mutex);
    return count;
}
int x2d_mono_wayland_leases_destroy(x2d_mono_wayland_leases *leases) {
    if (!leases || x2d_mono_wayland_leases_outstanding(leases)) return -1;
    return pthread_mutex_destroy(&leases->mutex) == 0 ? 0 : -1;
}
