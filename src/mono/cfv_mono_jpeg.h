#ifndef CFV_MONO_JPEG_H
#define CFV_MONO_JPEG_H

#include "cfv_mono.h"

/* The caller owns both frame handles and their mapped planes. The private
 * handle must refer to frame.dst_y/dst_uv, never the stock source. */
typedef struct {
    cfv_mono_frame planes;
    const void *stock_encoder_frame;
    const void *private_encoder_frame;
} cfv_mono_jpeg_request;

typedef int (*cfv_mono_jpeg_encoder)(void *context, const void *frame);

typedef struct {
    cfv_mono_result preparation;
    int encoder_called;
    int encoder_result;
} cfv_mono_jpeg_result;

/* One-shot selection and encoding. With monochrome off, passes the stock
 * frame unchanged. With it on, copies pixels to the private buffer first.
 * A failed preparation never calls the encoder or falls back to color. */
cfv_mono_jpeg_result cfv_mono_encode_jpeg(
    const cfv_mono_jpeg_request *request,
    int monochrome_enabled,
    cfv_mono_jpeg_encoder encoder,
    void *encoder_context);

/* The device adapter allocates/maps a private encoder frame and returns its
 * handle and plane views. acquire must make source pixels readable by the CPU;
 * sync_for_encoder makes the written destination visible to the encoder.
 * Keep the ticket until actual encoder completion.
 * An acquire failure must clean up its own partially allocated resources.
 * release is called exactly once after every successful acquire. */
typedef struct {
    cfv_mono_frame planes;
    const void *encoder_frame;
} cfv_mono_owned_jpeg_frame;

typedef int (*cfv_mono_jpeg_acquire)(void *context,
                                    const void *stock_encoder_frame,
                                    cfv_mono_owned_jpeg_frame *private_frame);
typedef void (*cfv_mono_jpeg_release)(void *context,
                                     cfv_mono_owned_jpeg_frame *private_frame);
typedef int (*cfv_mono_jpeg_sync)(void *context,
                                 cfv_mono_owned_jpeg_frame *private_frame);

typedef struct {
    cfv_mono_jpeg_acquire acquire;
    cfv_mono_jpeg_sync sync_for_encoder;
    cfv_mono_jpeg_release release;
} cfv_mono_jpeg_memory;

/* A ticket keeps the private frame alive until the adapter's actual encoder
 * completion event. This also supports asynchronous encoders. */
typedef struct {
    const void *encoder_frame;
    cfv_mono_owned_jpeg_frame private_frame;
    int owns_private;
    cfv_mono_jpeg_release release;
    void *release_context;
} cfv_mono_jpeg_ticket;

cfv_mono_result cfv_mono_jpeg_begin(
    const void *stock_encoder_frame,
    int monochrome_enabled,
    const cfv_mono_jpeg_memory *memory,
    void *context,
    cfv_mono_jpeg_ticket *ticket);

void cfv_mono_jpeg_end(cfv_mono_jpeg_ticket *ticket);

#endif
