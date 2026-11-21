"""Small PE32 readonly DATA export fixtures; never executable test programs."""
import struct


def core_pe(protocol=9, features=15):
    data=bytearray(0x600)
    data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,0x80);data[0x80:0x84]=b'PE\0\0'
    struct.pack_into('<HHIIIHH',data,0x84,0x14c,1,0,0,0,224,0x2102)
    struct.pack_into('<H',data,0x98,0x10b);struct.pack_into('<I',data,0x98+92,16)
    struct.pack_into('<II',data,0x98+96,0x1000,0x80)
    section=0x98+224;data[section:section+8]=b'.rdata\0\0'
    struct.pack_into('<IIII',data,section+8,0x400,0x1000,0x400,0x200)
    struct.pack_into('<I',data,section+36,0x40000040)
    count=1 if features is None else 2
    struct.pack_into('<IIIII',data,0x200+20,count,count,0x1040,0x1048,0x1050)
    struct.pack_into('<II',data,0x240,0x1100,0x1104)
    struct.pack_into('<II',data,0x248,0x1060,0x1070);struct.pack_into('<HH',data,0x250,0,1)
    data[0x260:0x26e]=b'Coop_Protocol\0';struct.pack_into('<I',data,0x300,protocol)
    data[0x270:0x27e]=b'Coop_Features\0'
    if features is not None:struct.pack_into('<I',data,0x304,features)
    return bytes(data)


def malformed_core(kind, protocol=9):
    data=bytearray(core_pe(protocol));section=0x98+224
    if kind=='missing':data[0x260:0x26e]=b'Other_Export_\0'
    elif kind=='forwarded':struct.pack_into('<I',data,0x240,0x1060)
    elif kind=='writable':struct.pack_into('<I',data,section+36,0xc0000040)
    elif kind=='executable':struct.pack_into('<I',data,section+36,0x60000040)
    elif kind=='out_of_bounds':struct.pack_into('<I',data,0x240,0xffffffff)
    elif kind=='export_count':struct.pack_into('<I',data,0x200+24,0xffffffff)
    elif kind=='ordinal':struct.pack_into('<H',data,0x250,2)
    elif kind=='truncated':return bytes(data[:160])
    else:raise ValueError(kind)
    return bytes(data)


def malformed_feature(kind, protocol=9):
    data=bytearray(core_pe(protocol));section=0x98+224
    if kind=='missing':data[0x270:0x27e]=b'Other_Feature\0'
    elif kind=='forwarded':struct.pack_into('<I',data,0x244,0x1070)
    elif kind=='out_of_bounds':struct.pack_into('<I',data,0x244,0xffffffff)
    elif kind=='ordinal':struct.pack_into('<H',data,0x252,2)
    elif kind in ('writable','executable'):
        data.extend(b'\0'*0x200);struct.pack_into('<H',data,0x86,2)
        second=section+40;data[second:second+8]=b'.data\0\0\0'
        struct.pack_into('<IIII',data,second+8,0x200,0x2000,0x200,0x600)
        struct.pack_into('<I',data,second+36,0xc0000040 if kind=='writable' else 0x60000040)
        struct.pack_into('<I',data,0x244,0x2000);struct.pack_into('<I',data,0x600,15)
    else:raise ValueError(kind)
    return bytes(data)
