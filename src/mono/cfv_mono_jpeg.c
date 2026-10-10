#include "cfv_mono_jpeg.h"
#include <string.h>

cfv_mono_jpeg_result cfv_mono_encode_jpeg(
    const cfv_mono_jpeg_request *request,
    int monochrome_enabled,
    cfv_mono_jpeg_encoder encoder,
    void *encoder_context) {
    cfv_mono_jpeg_result result = {CFV_MONO_BAD_ARGUMENT, 0, 0};
    if (!request || !encoder || !request->stock_encoder_frame)
        return result;

    const void *selected = request->stock_encoder_frame;
    if (monochrome_enabled) {
        if (!request->private_encoder_frame ||
            request->private_encoder_frame == request->stock_encoder_frame)
            return result;
        result.preparation = cfv_mono_yuv8_sp422(&request->planes);
        if (result.preparation != CFV_MONO_OK)
            return result;
        selected = request->private_encoder_frame;
    }

    result.preparation = CFV_MONO_OK;
    result.encoder_called = 1;
    result.encoder_result = encoder(encoder_context, selected);
    return result;
}

cfv_mono_result cfv_mono_jpeg_begin(
    const void *stock_encoder_frame,
    int monochrome_enabled,
    const cfv_mono_jpeg_memory *memory,
    void *context,
    cfv_mono_jpeg_ticket *ticket) {
    if (!stock_encoder_frame || !ticket) return CFV_MONO_BAD_ARGUMENT;
    memset(ticket, 0, sizeof *ticket);
    if (!monochrome_enabled) {
        ticket->encoder_frame = stock_encoder_frame;
        return CFV_MONO_OK;
    }
    if (!memory || !memory->acquire || !memory->sync_for_encoder ||
        !memory->release)
        return CFV_MONO_BAD_ARGUMENT;

    cfv_mono_owned_jpeg_frame *private_frame = &ticket->private_frame;
    if (memory->acquire(context, stock_encoder_frame, private_frame) != 0) {
        memset(ticket, 0, sizeof *ticket);
        return CFV_MONO_PRIVATE_BUFFER_FAILED;
    }
    if (!private_frame->encoder_frame ||
        private_frame->encoder_frame == stock_encoder_frame) {
        memory->release(context, private_frame);
        memset(ticket, 0, sizeof *ticket);
        return CFV_MONO_BAD_ARGUMENT;
    }
    cfv_mono_result result = cfv_mono_yuv8_sp422(&private_frame->planes);
    if (result != CFV_MONO_OK) {
        memory->release(context, private_frame);
        memset(ticket, 0, sizeof *ticket);
        return result;
    }
    if (memory->sync_for_encoder(context, private_frame) != 0) {
        memory->release(context, private_frame);
        memset(ticket, 0, sizeof *ticket);
        return CFV_MONO_SYNC_FAILED;
    }
    ticket->encoder_frame = private_frame->encoder_frame;
    ticket->owns_private = 1;
    ticket->release = memory->release;
    ticket->release_context = context;
    return CFV_MONO_OK;
}

void cfv_mono_jpeg_end(cfv_mono_jpeg_ticket *ticket) {
    if (!ticket) return;
    if (ticket->owns_private)
        ticket->release(ticket->release_context, &ticket->private_frame);
    memset(ticket, 0, sizeof *ticket);
}
