#coding: utf-8
import time
import ctypes


class JLink(object):
    def __init__(self, dllpath, coretype):
        self.jlk = ctypes.cdll.LoadLibrary(dllpath)

        self.jlk.JLINKARM_Open()
        if not self.jlk.JLINKARM_IsOpen():
            raise Exception('No JLink connected')

        err_buf = (ctypes.c_char * 64)()
        self.jlk.JLINKARM_ExecCommand(('Device = %s' %coretype).encode(), err_buf, 64)
        
        self.jlk.JLINKARM_TIF_Select(1)
        self.jlk.JLINKARM_SetSpeed(12000)

    def write_U32(self, addr, val):
        self.jlk.JLINKARM_WriteU32(addr, val)

    def read_U32(self, addr):
        buf = (ctypes.c_uint32 * 1)()
        self.jlk.JLINKARM_ReadMemU32(addr, 1, buf, 0)

        return buf[0]

    def write_mem_U32(self, addr, data):
        byte = []
        for x in data:
            byte.extend([x&0xFF, (x>>8)&0xFF, (x>>16)&0xFF, (x>>24)&0xFF])
        self.write_mem(addr, byte)

    def read_mem_U32(self, addr, count):
        buffer = (ctypes.c_uint32 * count)()
        self.jlk.JLINKARM_ReadMemU32(addr, count, buffer, 0)

        return buffer
