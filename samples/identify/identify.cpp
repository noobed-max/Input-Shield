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

    raise_process_priority();

    context = ishield_create_context();

    ishield_set_filter(context, ishield_is_keyboard, ISHIELD_FILTER_KEY_DOWN | ISHIELD_FILTER_KEY_UP);
    ishield_set_filter(context, ishield_is_mouse, ISHIELD_FILTER_MOUSE_LEFT_BUTTON_DOWN);

    while(ishield_receive(context, device = ishield_wait(context), &stroke, 1) > 0)
    {
        if(ishield_is_keyboard(device))
        {
            IshieldKeyStroke &keystroke = *(IshieldKeyStroke *) &stroke;

            cout << "ISHIELD_KEYBOARD(" << device - ISHIELD_KEYBOARD(0) << ")" << endl;

            if(keystroke.code == SCANCODE_ESC) break;
        }
        else if(ishield_is_mouse(device))
        {
            cout << "ISHIELD_MOUSE(" << device - ISHIELD_MOUSE(0) << ")" << endl;
        }
        else
        {
            cout << "UNRECOGNIZED(" << device << ")" << endl;
        }

        ishield_send(context, device, &stroke, 1);
    }

    ishield_destroy_context(context);

    return 0;
}
