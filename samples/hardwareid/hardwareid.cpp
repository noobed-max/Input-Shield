#include <inputshield.h>
#include <utils.h>

#include <iostream>

enum ScanCode
{
    SCANCODE_ESC = 0x01
};

int main()
{
    using namespace std;

    IshieldContext context;
    IshieldDevice device;
    IshieldStroke stroke;

    wchar_t hardware_id[500];

    raise_process_priority();

    context = ishield_create_context();

    ishield_set_filter(context, ishield_is_keyboard, ISHIELD_FILTER_KEY_DOWN | ISHIELD_FILTER_KEY_UP);
    ishield_set_filter(context, ishield_is_mouse, ISHIELD_FILTER_MOUSE_LEFT_BUTTON_DOWN);

    while(ishield_receive(context, device = ishield_wait(context), &stroke, 1) > 0)
    {
        if(ishield_is_keyboard(device))
        {
            IshieldKeyStroke &keystroke = *(IshieldKeyStroke *) &stroke;

            if(keystroke.code == SCANCODE_ESC) break;
        }

        size_t length = ishield_get_hardware_id(context, device, hardware_id, sizeof(hardware_id));

        if(length > 0 && length < sizeof(hardware_id))
            wcout << hardware_id << endl;

        ishield_send(context, device, &stroke, 1);
    }

    ishield_destroy_context(context);

    return 0;
}
