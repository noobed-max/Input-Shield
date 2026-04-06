#ifndef _INPUTSHIELD_H_
#define _INPUTSHIELD_H_

#ifdef ISHIELD_STATIC
    #define ISHIELD_API
#else
    #if defined _WIN32 || defined __CYGWIN__
        #ifdef ISHIELD_EXPORT
            #ifdef __GNUC__
                #define ISHIELD_API __attribute__((dllexport))
            #else
                #define ISHIELD_API __declspec(dllexport)
            #endif
        #else
            #ifdef __GNUC__
                #define ISHIELD_API __attribute__((dllimport))
            #else
                #define ISHIELD_API __declspec(dllimport)
            #endif
        #endif
    #else
        #if __GNUC__ >= 4
            #define ISHIELD_API __attribute__ ((visibility("default")))
        #else
            #define ISHIELD_API
        #endif
    #endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define ISHIELD_MAX_KEYBOARD 10

#define ISHIELD_MAX_MOUSE 10

#define ISHIELD_MAX_DEVICE ((ISHIELD_MAX_KEYBOARD) + (ISHIELD_MAX_MOUSE))

#define ISHIELD_KEYBOARD(index) ((index) + 1)

#define ISHIELD_MOUSE(index) ((ISHIELD_MAX_KEYBOARD) + (index) + 1)

typedef void *IshieldContext;

typedef int IshieldDevice;

typedef int IshieldPrecedence;

typedef unsigned short IshieldFilter;

typedef int (*IshieldPredicate)(IshieldDevice device);

enum IshieldKeyState
{
    ISHIELD_KEY_DOWN             = 0x00,
    ISHIELD_KEY_UP               = 0x01,
    ISHIELD_KEY_E0               = 0x02,
    ISHIELD_KEY_E1               = 0x04,
    ISHIELD_KEY_TERMSRV_SET_LED  = 0x08,
    ISHIELD_KEY_TERMSRV_SHADOW   = 0x10,
    ISHIELD_KEY_TERMSRV_VKPACKET = 0x20
};

enum IshieldFilterKeyState
{
    ISHIELD_FILTER_KEY_NONE             = 0x0000,
    ISHIELD_FILTER_KEY_ALL              = 0xFFFF,
    ISHIELD_FILTER_KEY_DOWN             = ISHIELD_KEY_UP,
    ISHIELD_FILTER_KEY_UP               = ISHIELD_KEY_UP << 1,
    ISHIELD_FILTER_KEY_E0               = ISHIELD_KEY_E0 << 1,
    ISHIELD_FILTER_KEY_E1               = ISHIELD_KEY_E1 << 1,
    ISHIELD_FILTER_KEY_TERMSRV_SET_LED  = ISHIELD_KEY_TERMSRV_SET_LED << 1,
    ISHIELD_FILTER_KEY_TERMSRV_SHADOW   = ISHIELD_KEY_TERMSRV_SHADOW << 1,
    ISHIELD_FILTER_KEY_TERMSRV_VKPACKET = ISHIELD_KEY_TERMSRV_VKPACKET << 1
};

enum IshieldMouseState
{
    ISHIELD_MOUSE_LEFT_BUTTON_DOWN   = 0x001,
    ISHIELD_MOUSE_LEFT_BUTTON_UP     = 0x002,
    ISHIELD_MOUSE_RIGHT_BUTTON_DOWN  = 0x004,
    ISHIELD_MOUSE_RIGHT_BUTTON_UP    = 0x008,
    ISHIELD_MOUSE_MIDDLE_BUTTON_DOWN = 0x010,
    ISHIELD_MOUSE_MIDDLE_BUTTON_UP   = 0x020,

    ISHIELD_MOUSE_BUTTON_1_DOWN      = ISHIELD_MOUSE_LEFT_BUTTON_DOWN,
    ISHIELD_MOUSE_BUTTON_1_UP        = ISHIELD_MOUSE_LEFT_BUTTON_UP,
    ISHIELD_MOUSE_BUTTON_2_DOWN      = ISHIELD_MOUSE_RIGHT_BUTTON_DOWN,
    ISHIELD_MOUSE_BUTTON_2_UP        = ISHIELD_MOUSE_RIGHT_BUTTON_UP,
    ISHIELD_MOUSE_BUTTON_3_DOWN      = ISHIELD_MOUSE_MIDDLE_BUTTON_DOWN,
    ISHIELD_MOUSE_BUTTON_3_UP        = ISHIELD_MOUSE_MIDDLE_BUTTON_UP,

    ISHIELD_MOUSE_BUTTON_4_DOWN      = 0x040,
    ISHIELD_MOUSE_BUTTON_4_UP        = 0x080,
    ISHIELD_MOUSE_BUTTON_5_DOWN      = 0x100,
    ISHIELD_MOUSE_BUTTON_5_UP        = 0x200,

    ISHIELD_MOUSE_WHEEL              = 0x400,
    ISHIELD_MOUSE_HWHEEL             = 0x800
};

enum IshieldFilterMouseState
{
    ISHIELD_FILTER_MOUSE_NONE               = 0x0000,
    ISHIELD_FILTER_MOUSE_ALL                = 0xFFFF,

    ISHIELD_FILTER_MOUSE_LEFT_BUTTON_DOWN   = ISHIELD_MOUSE_LEFT_BUTTON_DOWN,
    ISHIELD_FILTER_MOUSE_LEFT_BUTTON_UP     = ISHIELD_MOUSE_LEFT_BUTTON_UP,
    ISHIELD_FILTER_MOUSE_RIGHT_MOUSE_DOWN  = ISHIELD_MOUSE_RIGHT_BUTTON_DOWN,
    ISHIELD_FILTER_MOUSE_RIGHT_BUTTON_UP    = ISHIELD_MOUSE_RIGHT_BUTTON_UP,
    ISHIELD_FILTER_MOUSE_MIDDLE_BUTTON_DOWN = ISHIELD_MOUSE_MIDDLE_BUTTON_DOWN,
    ISHIELD_FILTER_MOUSE_MIDDLE_BUTTON_UP   = ISHIELD_MOUSE_MIDDLE_BUTTON_UP,

    ISHIELD_FILTER_MOUSE_BUTTON_1_DOWN      = ISHIELD_MOUSE_BUTTON_1_DOWN,
    ISHIELD_FILTER_MOUSE_BUTTON_1_UP        = ISHIELD_MOUSE_BUTTON_1_UP,
    ISHIELD_FILTER_MOUSE_BUTTON_2_DOWN      = ISHIELD_MOUSE_BUTTON_2_DOWN,
    ISHIELD_FILTER_MOUSE_BUTTON_2_UP        = ISHIELD_MOUSE_BUTTON_2_UP,
    ISHIELD_FILTER_MOUSE_BUTTON_3_DOWN      = ISHIELD_MOUSE_BUTTON_3_DOWN,
    ISHIELD_FILTER_MOUSE_BUTTON_3_UP        = ISHIELD_MOUSE_BUTTON_3_UP,

    ISHIELD_FILTER_MOUSE_BUTTON_4_DOWN      = ISHIELD_MOUSE_BUTTON_4_DOWN,
    ISHIELD_FILTER_MOUSE_BUTTON_4_UP        = ISHIELD_MOUSE_BUTTON_4_UP,
    ISHIELD_FILTER_MOUSE_BUTTON_5_DOWN      = ISHIELD_MOUSE_BUTTON_5_DOWN,
    ISHIELD_FILTER_MOUSE_BUTTON_5_UP        = ISHIELD_MOUSE_BUTTON_5_UP,

    ISHIELD_FILTER_MOUSE_WHEEL              = ISHIELD_MOUSE_WHEEL,
    ISHIELD_FILTER_MOUSE_HWHEEL             = ISHIELD_MOUSE_HWHEEL,

    ISHIELD_FILTER_MOUSE_MOVE               = 0x1000
};

enum IshieldMouseFlag
{
    ISHIELD_MOUSE_MOVE_RELATIVE      = 0x000,
    ISHIELD_MOUSE_MOVE_ABSOLUTE      = 0x001,
    ISHIELD_MOUSE_VIRTUAL_DESKTOP    = 0x002,
    ISHIELD_MOUSE_ATTRIBUTES_CHANGED = 0x004,
    ISHIELD_MOUSE_MOVE_NOCOALESCE    = 0x008,
    ISHIELD_MOUSE_TERMSRV_SRC_SHADOW = 0x100
};

typedef struct
{
    unsigned short state;
    unsigned short flags;
    short rolling;
    int x;
    int y;
    unsigned int information;
} IshieldMouseStroke;

typedef struct
{
    unsigned short code;
    unsigned short state;
    unsigned int information;
} IshieldKeyStroke;

typedef char IshieldStroke[sizeof(IshieldMouseStroke)];

IshieldContext ISHIELD_API ishield_create_context(void);

void ISHIELD_API ishield_destroy_context(IshieldContext context);

IshieldPrecedence ISHIELD_API ishield_get_precedence(IshieldContext context, IshieldDevice device);

void ISHIELD_API ishield_set_precedence(IshieldContext context, IshieldDevice device, IshieldPrecedence precedence);

IshieldFilter ISHIELD_API ishield_get_filter(IshieldContext context, IshieldDevice device);

void ISHIELD_API ishield_set_filter(IshieldContext context, IshieldPredicate predicate, IshieldFilter filter);

IshieldDevice ISHIELD_API ishield_wait(IshieldContext context);

IshieldDevice ISHIELD_API ishield_wait_with_timeout(IshieldContext context, unsigned long milliseconds);

int ISHIELD_API ishield_send(IshieldContext context, IshieldDevice device, const IshieldStroke *stroke, unsigned int nstroke);

int ISHIELD_API ishield_receive(IshieldContext context, IshieldDevice device, IshieldStroke *stroke, unsigned int nstroke);

unsigned int ISHIELD_API ishield_get_hardware_id(IshieldContext context, IshieldDevice device, void *hardware_id_buffer, unsigned int buffer_size);

int ISHIELD_API ishield_is_invalid(IshieldDevice device);

int ISHIELD_API ishield_is_keyboard(IshieldDevice device);

int ISHIELD_API ishield_is_mouse(IshieldDevice device);

#ifdef __cplusplus
}
#endif

#endif
