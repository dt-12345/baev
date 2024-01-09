# Largely adapated from https://github.com/zeldamods/evfl
import struct
import io

def get_string(data, offset):
    if type(data) != bytes:
        data = data.read()
    end = data.find(b'\x00', offset)
    return data[offset:end].decode('utf-8')

class Stream:
    __slots__ = ["stream"]

    def __init__(self, stream) -> None:
        self.stream = stream

    def seek(self, *args) -> None:
        self.stream.seek(*args)

    def tell(self) -> int:
        return self.stream.tell()

    def skip(self, skip_size) -> None:
        self.stream.seek(skip_size, 1)

class ReadStream(Stream):
    def __init__(self, data) -> None:
        stream = io.BytesIO(memoryview(data))
        super().__init__(stream)
        self.data = data

    def read(self, *args) -> bytes:
        return self.stream.read(*args)
    
    def read_u8(self, end="<") -> int:
        return struct.unpack(f"{end}B", self.read(1))[0]
    
    def read_u16(self, end="<") -> int:
        return struct.unpack(f"{end}H", self.read(2))[0]
    
    def read_s16(self, end="<") -> int:
        return struct.unpack(f"{end}h", self.read(2))[0]
    
    def read_u32(self, end="<") -> int:
        return struct.unpack(f"{end}I", self.read(4))[0]
    
    def read_s32(self, end="<") -> int:
        return struct.unpack(f"{end}i", self.read(4))[0]
    
    def read_u64(self, end="<") -> int:
        return struct.unpack(f"{end}Q", self.read(8))[0]
    
    def read_s64(self, end="<") -> int:
        return struct.unpack(f"{end}q", self.read(8))[0]
    
    def read_f32(self, end="<") -> float:
        return struct.unpack(f"{end}f", self.read(4))[0]

    def read_string(self, offset=None, size=4, end="<"):
        current = self.stream.read(1)
        string = current
        while current != b'\x00':
            current = self.stream.read(1)
            string += current
        string = string.decode('utf-8')[:-1]
        return string
    
class PlaceholderWriter:
    __slots__ = ["_offset"]

    def __init__(self, offset):
        self._offset = offset

    def write(self, stream, data):
        pos = stream.tell()
        stream.seek(self._offset)
        stream.write(data)
        stream.seek(pos)

class WriteStream(Stream):
    def __init__(self, stream):
        super().__init__(stream)
        self._string_list = [] # List of strings in file
        self._strings = b'' # String pool to write to file
        self._string_refs = {} # Maps strings to relative offsets
        self._string_list_exb = [] # List of strings in the EXB Section
        self._strings_exb = b'' # String pool to write to the EXB section
        self._string_refs_exb = {} # Maps strings to relative offsets

    def add_string(self, string):
        if string not in self._string_list:
            encoded = string.encode()
            self._string_list.append(string)
            self._string_refs[string] = len(self._strings)
            self._strings += encoded
            if encoded[-1:] != b'\x00': # All strings must end with a null termination character
                self._strings += b'\x00'

    def add_string_exb(self, string):
        if string not in self._string_list_exb:
            encoded = string.encode()
            self._string_list_exb.append(string)
            self._string_refs_exb[string] = len(self._strings_exb)
            self._strings_exb += encoded
            if encoded[-1:] != b'\x00': # All strings must end with a null termination character
                self._strings_exb += b'\x00'

    def write(self, data):
        self.stream.write(data)

def u8(value):
    return struct.pack("B", value)

def u16(value):
    return struct.pack("<H", value)

def s16(value):
    return struct.pack("<h", value)

def u32(value):
    return struct.pack("<I", value)

def s32(value):
    return struct.pack("<i", value)

def u64(value):
    return struct.pack("<Q", value)

def f32(value):
    return struct.pack("<f", value)

def string(value):
    return value.encode()

def vec3f(values):
    buffer = b''
    for value in values:
        buffer += f32(value)
    return buffer

def byte_custom(value, size):
    return struct.pack(f"<{size}s", value)

def padding():
    return struct.pack("x")