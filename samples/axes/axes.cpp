#include <inputshield.h>
#include <utils.h>

enum ScanCode
{
    SCANCODE_ESC = 0x01
};

int main()
{
    IshieldContext context;
    IshieldDevice device;
    IshieldStroke stroke;

    raise_process_priority();

    context = ishield_create_context();

    ishield_set_filter(context, ishield_is_keyboard, ISHIELD_FILTER_KEY_DOWN | ISHIELD_FILTER_KEY_UP);
    ishield_set_filter(context, ishield_is_mouse, ISHIELD_FILTER_MOUSE_MOVE);

    while(ishield_receive(context, device = ishield_wait(context), &stroke, 1) > 0)
    {
        if(ishield_is_mouse(device))
        {
            IshieldMouseStroke &mstroke = *(IshieldMouseStroke *) &stroke;

            if(!(mstroke.flags & ISHIELD_MOUSE_MOVE_ABSOLUTE)) mstroke.y *= -1;

            ishield_send(context, device, &stroke, 1);
        }

        if(ishield_is_keyboard(device))
        {
            IshieldKeyStroke &kstroke = *(IshieldKeyStroke *) &stroke;

            ishield_send(context, device, &stroke, 1);

            if(kstroke.code == SCANCODE_ESC) break;
        }
    }

    ishield_destroy_context(context);

    return 0;
}
