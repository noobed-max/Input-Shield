#include <iostream>

#include <utils.h>
#include <inputshield.h>

using namespace std;

namespace scancode {
    enum {
        esc  = 0x01,
        ctrl = 0x1D,
        alt  = 0x38,
        del  = 0x53,
    };
}

IshieldKeyStroke ctrl_down = {scancode::ctrl, ISHIELD_KEY_DOWN                      , 0};
IshieldKeyStroke alt_down  = {scancode::alt , ISHIELD_KEY_DOWN                      , 0};
IshieldKeyStroke del_down  = {scancode::del , ISHIELD_KEY_DOWN | ISHIELD_KEY_E0, 0};
IshieldKeyStroke ctrl_up   = {scancode::ctrl, ISHIELD_KEY_UP                        , 0};
IshieldKeyStroke alt_up    = {scancode::alt , ISHIELD_KEY_UP                        , 0};
IshieldKeyStroke del_up    = {scancode::del , ISHIELD_KEY_UP | ISHIELD_KEY_E0  , 0};

bool operator==(const IshieldKeyStroke &first,
                const IshieldKeyStroke &second) {
    return first.code == second.code && first.state == second.state;
}

bool shall_produce_keystroke(const IshieldKeyStroke &kstroke) {
    static int ctrl_is_down = 0, alt_is_down = 0, del_is_down = 0;

    if (ctrl_is_down + alt_is_down + del_is_down < 2) {
        if (kstroke == ctrl_down) { ctrl_is_down = 1; }
        if (kstroke == ctrl_up  ) { ctrl_is_down = 0; }
        if (kstroke == alt_down ) { alt_is_down = 1;  }
        if (kstroke == alt_up   ) { alt_is_down = 0;  }
        if (kstroke == del_down ) { del_is_down = 1;  }
        if (kstroke == del_up   ) { del_is_down = 0;  }
        return true;
    }

    if (ctrl_is_down == 0 && (kstroke == ctrl_down || kstroke == ctrl_up)) {
        return false;
    }

    if (alt_is_down == 0 && (kstroke == alt_down || kstroke == alt_up)) {
        return false;
    }

    if (del_is_down == 0 && (kstroke == del_down || kstroke == del_up)) {
        return false;
    }

    if (kstroke == ctrl_up) {
        ctrl_is_down = 0;
    } else if (kstroke == alt_up) {
        alt_is_down = 0;
    } else if (kstroke == del_up) {
        del_is_down = 0;
    }

    return true;
}

int main() {
    IshieldContext context;
    IshieldDevice device;
    IshieldKeyStroke kstroke;

    raise_process_priority();

    context = ishield_create_context();

    ishield_set_filter(context, ishield_is_keyboard,
                            ISHIELD_FILTER_KEY_ALL);

    while (ishield_receive(context, device = ishield_wait(context),
                                (IshieldStroke *)&kstroke, 1) > 0) {
        if (!shall_produce_keystroke(kstroke)) {
            cout << "ctrl-alt-del pressed" << endl;
            continue;
        }

        ishield_send(context, device, (IshieldStroke *)&kstroke, 1);

        if (kstroke.code == scancode::esc)
            break;
    }

    ishield_destroy_context(context);

    return 0;
}
