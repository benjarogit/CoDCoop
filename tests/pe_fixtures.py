"""Small PE32 readonly DATA export fixtures; never executable test programs."""
import struct


def core_pe(protocol=9):
    data=bytearray(0x600)
    data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,0x80);data[0x80:0x84]=b'PE\0\0'
    struct.pack_into('<HHIIIHH',data,0x84,0x14c,1,0,0,0,224,0x2102)
    struct.pack_into('<H',data,0x98,0x10b);struct.pack_into('<I',data,0x98+92,16)
    struct.pack_into('<II',data,0x98+96,0x1000,0x80)
    section=0x98+224;data[section:section+8]=b'.rdata\0\0'
    struct.pack_into('<IIII',data,section+8,0x400,0x1000,0x400,0x200)
    struct.pack_into('<I',data,section+36,0x40000040)
    struct.pack_into('<IIIII',data,0x200+20,1,1,0x1040,0x1044,0x1048)
    struct.pack_into('<I',data,0x240,0x1100);struct.pack_into('<I',data,0x244,0x1060);struct.pack_into('<H',data,0x248,0)
    data[0x260:0x26e]=b'Coop_Protocol\0';struct.pack_into('<I',data,0x300,protocol)
    return bytes(data)


def malformed_core(kind, protocol=9):
    data=bytearray(core_pe(protocol));section=0x98+224
    if kind=='missing':data[0x260:0x26e]=b'Other_Export_\0'
    elif kind=='forwarded':struct.pack_into('<I',data,0x240,0x1060)
    elif kind=='writable':struct.pack_into('<I',data,section+36,0xc0000040)
    elif kind=='executable':struct.pack_into('<I',data,section+36,0x60000040)
    elif kind=='out_of_bounds':struct.pack_into('<I',data,0x240,0xffffffff)
    elif kind=='export_count':struct.pack_into('<I',data,0x200+24,0xffffffff)
    elif kind=='ordinal':struct.pack_into('<H',data,0x248,1)
    elif kind=='truncated':return bytes(data[:160])
    else:raise ValueError(kind)
    return bytes(data)
