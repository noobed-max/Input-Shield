#include <inputshield.h>
#include <utils.h>

enum ScanCode
{
    SCANCODE_X   = 0x2D,
    SCANCODE_Y   = 0x15,
    SCANCODE_ESC = 0x01
};

int main()
{
    IshieldContext context;
    IshieldDevice device;
    IshieldKeyStroke stroke;

    raise_process_priority();

    context = ishield_create_context();

    ishield_set_filter(context, ishield_is_keyboard, ISHIELD_FILTER_KEY_DOWN | ISHIELD_FILTER_KEY_UP);

    while(ishield_receive(context, device = ishield_wait(context), (IshieldStroke *)&stroke, 1) > 0)
    {
        if(stroke.code == SCANCODE_X) stroke.code = SCANCODE_Y;

        ishield_send(context, device, (IshieldStroke *)&stroke, 1);

        if(stroke.code == SCANCODE_ESC) break;
    }

    ishield_destroy_context(context);

    return 0;
}
