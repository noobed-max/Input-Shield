#include <stdio.h>
#include <windows.h>
#include <winioctl.h>

#include "inputshield.h"

#define IOCTL_SET_PRECEDENCE    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_GET_PRECEDENCE    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_SET_FILTER        CTL_CODE(FILE_DEVICE_UNKNOWN, 0x804, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_GET_FILTER        CTL_CODE(FILE_DEVICE_UNKNOWN, 0x808, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_SET_EVENT         CTL_CODE(FILE_DEVICE_UNKNOWN, 0x810, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_WRITE             CTL_CODE(FILE_DEVICE_UNKNOWN, 0x820, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_READ              CTL_CODE(FILE_DEVICE_UNKNOWN, 0x840, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_GET_HARDWARE_ID   CTL_CODE(FILE_DEVICE_UNKNOWN, 0x880, METHOD_BUFFERED, FILE_ANY_ACCESS)

typedef struct _KEYBOARD_INPUT_DATA
{
    USHORT UnitId;
    USHORT MakeCode;
    USHORT Flags;
    USHORT Reserved;
    ULONG  ExtraInformation;
} KEYBOARD_INPUT_DATA, *PKEYBOARD_INPUT_DATA;

typedef struct _MOUSE_INPUT_DATA
{
    USHORT UnitId;
    USHORT Flags;
    USHORT ButtonFlags;
    USHORT ButtonData;
    ULONG  RawButtons;
    LONG   LastX;
    LONG   LastY;
    ULONG  ExtraInformation;
} MOUSE_INPUT_DATA, *PMOUSE_INPUT_DATA;

typedef struct
{
    void *handle;
    void *unempty;
} *IshieldDeviceArray;

IshieldContext ishield_create_context(void)
{
    IshieldDeviceArray device_array = 0;
    char device_name[] = "\\\\.\\inputshield00";
    DWORD bytes_returned;
    IshieldDevice i;

    device_array = (IshieldDeviceArray)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, ISHIELD_MAX_DEVICE * sizeof(*((IshieldDeviceArray) 0)));
    if(!device_array) return 0;

    for(i = 0; i < ISHIELD_MAX_DEVICE; ++i)
    {
        HANDLE zero_padded_handle[2] = {0};

        sprintf(&device_name[sizeof(device_name) - 3], "%02d", i);

        device_array[i].handle = CreateFileA(device_name, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL);

        if (device_array[i].handle == INVALID_HANDLE_VALUE) {
            ishield_destroy_context(device_array);
            return 0;
        }

        device_array[i].unempty = CreateEventA(NULL, TRUE, FALSE, NULL);

        if(device_array[i].unempty == NULL)
        {
            ishield_destroy_context(device_array);
            return 0;
        }

        zero_padded_handle[0] = device_array[i].unempty;

        if(!DeviceIoControl(device_array[i].handle, IOCTL_SET_EVENT, zero_padded_handle, sizeof(zero_padded_handle), NULL, 0, &bytes_returned, NULL))
        {
            ishield_destroy_context(device_array);
            return 0;
        }
    }

    return device_array;
}

void ishield_destroy_context(IshieldContext context)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    unsigned int i;

    if(!context) return;

    for(i = 0; i < ISHIELD_MAX_DEVICE; ++i)
    {
        if(device_array[i].handle != INVALID_HANDLE_VALUE)
            CloseHandle(device_array[i].handle);

        if(device_array[i].unempty != NULL)
            CloseHandle(device_array[i].unempty);
    }

    HeapFree(GetProcessHeap(), 0, context);
}

IshieldPrecedence ishield_get_precedence(IshieldContext context, IshieldDevice device)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    IshieldPrecedence precedence = 0;
    DWORD bytes_returned;

    if(context && device_array[device - 1].handle)
        DeviceIoControl(device_array[device - 1].handle, IOCTL_GET_PRECEDENCE, NULL, 0, (LPVOID)&precedence, sizeof(IshieldPrecedence), &bytes_returned, NULL);

    return precedence;
}

void ishield_set_precedence(IshieldContext context, IshieldDevice device, IshieldPrecedence precedence)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    DWORD bytes_returned;

    if(context && device_array[device - 1].handle)
        DeviceIoControl(device_array[device - 1].handle, IOCTL_SET_PRECEDENCE, (LPVOID)&precedence, sizeof(IshieldPrecedence), NULL, 0, &bytes_returned, NULL);
}

IshieldFilter ishield_get_filter(IshieldContext context, IshieldDevice device)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    IshieldFilter filter = 0;
    DWORD bytes_returned;

    if(context && device_array[device - 1].handle)
        DeviceIoControl(device_array[device - 1].handle, IOCTL_GET_FILTER, NULL, 0, (LPVOID)&filter, sizeof(IshieldFilter), &bytes_returned, NULL);

    return filter;
}

void ishield_set_filter(IshieldContext context, IshieldPredicate device_predicate, IshieldFilter filter)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    IshieldDevice i;
    DWORD bytes_returned;

    if(context)
        for(i = 0; i < ISHIELD_MAX_DEVICE; ++i)
            if(device_array[i].handle && device_predicate(i + 1))
                DeviceIoControl(device_array[i].handle, IOCTL_SET_FILTER, (LPVOID)&filter, sizeof(IshieldFilter), NULL, 0, &bytes_returned, NULL);
}

IshieldDevice ishield_wait(IshieldContext context)
{
    return ishield_wait_with_timeout(context, INFINITE);
}

IshieldDevice ishield_wait_with_timeout(IshieldContext context, unsigned long milliseconds)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    HANDLE wait_handles[ISHIELD_MAX_DEVICE];
    DWORD i, j, k;

    if(!context) return 0;

    for(i = 0, j = 0; i < ISHIELD_MAX_DEVICE; ++i)
    {
        if (device_array[i].unempty)
            wait_handles[j++] = device_array[i].unempty;
    }

    k = WaitForMultipleObjects(j, wait_handles, FALSE, milliseconds);

    if(k ==  WAIT_FAILED || k == WAIT_TIMEOUT) return 0;

    for(i = 0, j = 0; i < ISHIELD_MAX_DEVICE; ++i)
    {
        if (device_array[i].unempty)
            if (k == j++)
                break;
    }

    return i + 1;
}

int ishield_send(IshieldContext context, IshieldDevice device, const IshieldStroke *stroke, unsigned int nstroke)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    DWORD strokeswritten = 0;

    if(context == 0 || nstroke == 0 || ishield_is_invalid(device) || !device_array[device - 1].handle) return 0;

    if(ishield_is_keyboard(device))
    {
        PKEYBOARD_INPUT_DATA rawstrokes = (PKEYBOARD_INPUT_DATA)HeapAlloc(GetProcessHeap(), 0, nstroke * sizeof(KEYBOARD_INPUT_DATA));
        unsigned int i;

        if(!rawstrokes) return 0;

        for(i = 0; i < nstroke; ++i)
        {
            IshieldKeyStroke *key_stroke = (IshieldKeyStroke *) stroke;

            rawstrokes[i].UnitId = 0;
            rawstrokes[i].MakeCode = key_stroke[i].code;
            rawstrokes[i].Flags = key_stroke[i].state;
            rawstrokes[i].Reserved = 0;
            rawstrokes[i].ExtraInformation = key_stroke[i].information;
        }

        DeviceIoControl(device_array[device - 1].handle, IOCTL_WRITE, rawstrokes,(DWORD)nstroke * sizeof(KEYBOARD_INPUT_DATA), NULL, 0, &strokeswritten, NULL);

        HeapFree(GetProcessHeap(), 0,  rawstrokes);

        strokeswritten /= sizeof(KEYBOARD_INPUT_DATA);
    }
    else
    {
        PMOUSE_INPUT_DATA rawstrokes = (PMOUSE_INPUT_DATA)HeapAlloc(GetProcessHeap(), 0, nstroke * sizeof(MOUSE_INPUT_DATA));
        unsigned int i;

        if(!rawstrokes) return 0;

        for(i = 0; i < nstroke; ++i)
        {
            IshieldMouseStroke *mouse_stroke = (IshieldMouseStroke *) stroke;

            rawstrokes[i].UnitId = 0;
            rawstrokes[i].Flags = mouse_stroke[i].flags;
            rawstrokes[i].ButtonFlags = mouse_stroke[i].state;
            rawstrokes[i].ButtonData = mouse_stroke[i].rolling;
            rawstrokes[i].RawButtons = 0;
            rawstrokes[i].LastX = mouse_stroke[i].x;
            rawstrokes[i].LastY = mouse_stroke[i].y;
            rawstrokes[i].ExtraInformation = mouse_stroke[i].information;
        }

        DeviceIoControl(device_array[device - 1].handle, IOCTL_WRITE, rawstrokes, (DWORD)nstroke * sizeof(MOUSE_INPUT_DATA), NULL, 0, &strokeswritten, NULL);

        HeapFree(GetProcessHeap(), 0,  rawstrokes);

        strokeswritten /= sizeof(MOUSE_INPUT_DATA);
    }

    return strokeswritten;
}

int ishield_receive(IshieldContext context, IshieldDevice device, IshieldStroke *stroke, unsigned int nstroke)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    DWORD strokesread = 0;

    if(context == 0 || nstroke == 0 || ishield_is_invalid(device) || !device_array[device - 1].handle) return 0;

    if(ishield_is_keyboard(device))
    {
        PKEYBOARD_INPUT_DATA rawstrokes = (PKEYBOARD_INPUT_DATA)HeapAlloc(GetProcessHeap(), 0, nstroke * sizeof(KEYBOARD_INPUT_DATA));
        unsigned int i;

        if(!rawstrokes) return 0;

        DeviceIoControl(device_array[device - 1].handle, IOCTL_READ, NULL, 0, rawstrokes, (DWORD)nstroke * sizeof(KEYBOARD_INPUT_DATA), &strokesread, NULL);

        strokesread /= sizeof(KEYBOARD_INPUT_DATA);

        for(i = 0; i < (unsigned int)strokesread; ++i)
        {
            IshieldKeyStroke *key_stroke = (IshieldKeyStroke *) stroke;

            key_stroke[i].code = rawstrokes[i].MakeCode;
            key_stroke[i].state = rawstrokes[i].Flags;
            key_stroke[i].information = rawstrokes[i].ExtraInformation;
        }

        HeapFree(GetProcessHeap(), 0,  rawstrokes);
    }
    else
    {
        PMOUSE_INPUT_DATA rawstrokes = (PMOUSE_INPUT_DATA)HeapAlloc(GetProcessHeap(), 0, nstroke * sizeof(MOUSE_INPUT_DATA));
        unsigned int i;

        if(!rawstrokes) return 0;

        DeviceIoControl(device_array[device - 1].handle, IOCTL_READ, NULL, 0, rawstrokes, (DWORD)nstroke * sizeof(MOUSE_INPUT_DATA), &strokesread, NULL);

        strokesread /= sizeof(MOUSE_INPUT_DATA);

        for(i = 0; i < (unsigned int)strokesread; ++i)
        {
            IshieldMouseStroke *mouse_stroke = (IshieldMouseStroke *) stroke;

            mouse_stroke[i].flags = rawstrokes[i].Flags;
            mouse_stroke[i].state = rawstrokes[i].ButtonFlags;
            mouse_stroke[i].rolling = rawstrokes[i].ButtonData;
            mouse_stroke[i].x = rawstrokes[i].LastX;
            mouse_stroke[i].y = rawstrokes[i].LastY;
            mouse_stroke[i].information = rawstrokes[i].ExtraInformation;
        }

        HeapFree(GetProcessHeap(), 0,  rawstrokes);
    }

    return strokesread;
}

unsigned int ishield_get_hardware_id(IshieldContext context, IshieldDevice device, void *hardware_id_buffer, unsigned int buffer_size)
{
    IshieldDeviceArray device_array = (IshieldDeviceArray)context;
    DWORD output_size = 0;

    if(context == 0 || ishield_is_invalid(device) || !device_array[device - 1].handle) return 0;

    DeviceIoControl(device_array[device - 1].handle, IOCTL_GET_HARDWARE_ID, NULL, 0, hardware_id_buffer, buffer_size, &output_size, NULL);

    return output_size;
}

int ishield_is_invalid(IshieldDevice device)
{
    return !ishield_is_keyboard(device) && !ishield_is_mouse(device);
}

int ishield_is_keyboard(IshieldDevice device)
{
    return device >= ISHIELD_KEYBOARD(0) && device <= ISHIELD_KEYBOARD(ISHIELD_MAX_KEYBOARD - 1);
}

int ishield_is_mouse(IshieldDevice device)
{
    return device >= ISHIELD_MOUSE(0) && device <= ISHIELD_MOUSE(ISHIELD_MAX_MOUSE - 1);
}
