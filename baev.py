from utils import *
import json
import os

class BAEV:
    def __init__(self, data, filename=''):
        from_json = False
        if type(data) == str:
            self.filename = os.path.basename(os.path.splitext(data)[0])
            if os.path.splitext(data)[1] == '.json':
                from_json = True
                with open(data, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                with open(data, 'rb') as f:
                    data = f.read()
        else:
            self.filename = filename
        if from_json:
            self.output_dict = data
        else:
            self.stream = ReadStream(data)
            self.data = data

            self.header = self.FileHeader()

            self.stream.seek(self.header["Section Info"][0]["Base Offset"])
            self.container = self.Container()
            self.output_dict = self.container["Event Info"]

    def Header(self):
        header = {}
        # should be BFFH (binary cafe file header) or BFSI (binary cafe section info)
        header["Magic"] = self.stream.read(4).decode('utf-8') 
        header["Section Offset"] = self.stream.read_u32()
        header["Section Size"] = self.stream.read_u32()
        header["Section Alignment"] = self.stream.read_u32()
        return header
    
    def FileHeader(self):
        header = self.Header()
        header["Section Info"] = self.Array(self.SectionHeader)
        header["Container Offset"] = self.stream.read_u64()
        header["Meme"] = self.stream.read(0x80).replace(b'\x00', b'').decode('utf-8')
        return header
    
    def SectionHeader(self):
        header = self.Header()
        header["Base Offset"] = self.stream.read_u64()
        header["Section Name"] = self.stream.read(0x10).replace(b'\x00', b'').decode('utf-8')
        return header

    # Common BAEV array structure
    def Array(self, element):
        array = []
        offset = self.stream.read_u64()
        count = self.stream.read_u32()
        size = self.stream.read_u32()
        pos = self.stream.tell()
        self.stream.seek(offset)
        for i in range(count):
            array.append(element())
        self.stream.seek(pos)
        return array
    
    def Container(self):
        container = {}
        container["Head Offset"] = self.stream.read_u64()
        ver_sub = self.stream.read_u8()
        ver_min = self.stream.read_u8()
        ver_maj = self.stream.read_u16()
        container["Version"] = str(ver_maj) + "." + str(ver_min) + "." + str(ver_sub)
        container["Unknown Value"] = self.stream.read_u32()
        container["String Pool Offset"] = self.stream.read_u64()
        container["Event Info"] = self.Array(self.Node)
        nodes = self.Array(self.EventNode)
        with open('test.json', 'w') as f:
            json.dump(nodes, f, indent=4)
        for entry in container["Event Info"]:
            for i in range(len(entry["Nodes"])):
                entry["Nodes"][i] = nodes[entry["Nodes"][i]]
        return container
    
    def U32(self):
        return self.stream.read_u32()

    def Node(self):
        entry = {}
        entry["Hash"] = hex(self.stream.read_u32())
        padding = self.stream.read_u32()
        entry["Nodes"] = self.Array(self.U32) # indices
        return entry
    
    def EventNode(self):
        entry = {}
        offset = self.stream.read_u64()
        count = self.stream.read_u32()
        entry_size = self.stream.read_u32()
        entry["Hash"] = hex(self.stream.read_u32())
        entry["Unknown"] = self.stream.read_u32()
        pos = self.stream.tell()
        self.stream.seek(offset)
        entry["Event"] = []
        for i in range(count):
            entry["Event"].append(self.Event())
        self.stream.seek(pos)
        return entry

    def Event(self):
        entry = {}
        pos = self.stream.tell()
        self.stream.seek(self.stream.read_u64())
        entry["Name"] = self.stream.read_string()
        self.stream.seek(pos + 8)
        entry["Trigger Array"] = self.Array(self.TriggerEventArray)
        entry["Hold Array"] = self.Array(self.HoldEventArray)
        entry["Unknown 1"] = self.stream.read_u32()
        entry["Unknown 2"] = self.stream.read_u32()
        return entry

    def TriggerEventArray(self):
        entry = {}
        entry["Parameters"] = self.Array(self.ParamOffset)
        entry["Start Frame"] = self.stream.read_f32()
        padding = self.stream.read_f32()
        return entry
    
    def HoldEventArray(self):
        entry = {}
        entry["Parameters"] = self.Array(self.ParamOffset)
        entry["Start Frame"] = self.stream.read_f32()
        entry["End Frame"] = self.stream.read_f32()
        return entry

    def Parameter(self):
        param_type = self.stream.read_u32()
        padding = self.stream.read_u32()
        match param_type:
            case 0:
                parameter = self.stream.read_u32()
            case 1:
                parameter = self.stream.read_f32()
            case 3:
                parameter = [self.stream.read_f32(), self.stream.read_f32(), self.stream.read_f32()]
            case 5:
                self.stream.seek(self.stream.read_u64())
                parameter = self.stream.read_string()
            case _:
                raise ValueError(param_type)
        return parameter

    def ParamOffset(self):
        offset = self.stream.read_u64()

        pos = self.stream.tell()
        self.stream.seek(offset)
        param = self.Parameter()
        self.stream.seek(pos)
        return param
    
    def ToJson(self, output=''):
        if output:
            os.makedirs(output, exist_ok=True)
        with open(os.path.join(output, self.filename + '.json'), 'w', encoding='utf-8') as f:
            json.dump(self.output_dict, f, indent=4, ensure_ascii=False)

    def CalcOffsets(self, buffer):
        offsets = {}
        offset = 0
        offsets["BFFH"] = offset
        offset += 0xA8
        offsets["BFSI0"] = offset
        offset += 0x28
        offsets["BFSI1"] = offset
        offset += 0x28
        offsets["Container"] = offset
        offset += 0x38
        offsets["HashHeader"] = offset
        offset += 0x18 * len(self.output_dict)
        offsets["Indices"] = offset
        offset += 0x4 * len(self.output_dict)
        offset = offset - offset % 8 + (8 if offset % 8 == 0 else 0)
        offsets["Nodes"] = offset
        for entry in self.output_dict:
            offset += 0x18 * len(entry["Nodes"])
        offsets["Events"] = offset
        count = 0
        for entry in self.output_dict:
            for node in entry["Nodes"]:
                count += 1
                for event in node["Event"]:
                    offset += 0x30
                    buffer.add_string(event["Name"])
                    for trigger in event["Trigger Array"]:
                        offset += 0x18
                        for param in trigger["Parameters"]:
                            offset += 0x8 + (0x18 if type(param) == list else 0x10)
                            if type(param) == str:
                                buffer.add_string(param)
                    for hold in event["Hold Array"]:
                        offset += 0x18
                        for param in hold["Parameters"]:
                            offset += 0x8 + (0x18 if type(param) == list else 0x10)
                            if type(param) == str:
                                buffer.add_string(param)
        offsets["String"] = offset
        offsets["Size"] = offset + len(buffer._strings)
        return offsets, count

    # Too lazy to finish and all the nesting makes my head hurt
    # Also have to figure out how tf the events are sorted bc it makes no sense
    """def ToBytes(self, output=''):
        if output:
            os.makedirs(output, exist_ok=True)
        with open(os.path.join(output, self.filename + '.baev'), 'wb') as f:
            buffer = WriteStream(f)
            buffer.add_string("")
            offsets, count = self.CalcOffsets(buffer)
            buffer.write("BFFH".encode('utf-8'))
            buffer.write(u32(offsets["BFFH"]))
            buffer.write(u32(offsets["Size"])) # file size
            buffer.write(u32(8)) # alignment
            buffer.write(u64(offsets["BFSI0"])) # offset for section headers array
            buffer.write(u32(2)) # section count
            buffer.write(u32(0x28)) # section header size
            buffer.write(u64(offsets["Container"])) # data container offset
            buffer.write("Nintendo.AnimationEvent.ResourceConverter.Resource.AnimationEventArchiveResData".encode('utf-8'))
            buffer.skip(0x31) # padding bc the meme string is 0x80 bytes
            buffer.write("BFSI".encode('utf-8'))
            buffer.write(u32(offsets["Container"])) # section offset
            buffer.write(u32(offsets["String"] - offsets["Container"])) # section size
            buffer.write(u32(8)) # section alignment
            buffer.write(u64(offsets["Container"])) # section pointer
            buffer.write("Default\x00\x00\x00\x00\x00\x00\x00\x00\x00".encode('utf-8')) # section name string
            buffer.write("BFSI".encode('utf-8')) # header is the same as the previous one
            buffer.write(u32(offsets["String"]))
            buffer.write(u32(len(buffer._strings)))
            buffer.write(u32(1))
            buffer.write(u64(offsets["String"]))
            buffer.write("StringPool\x00\x00\x00\x00\x00\x00".encode('utf-8'))
            buffer.write(u64(0))
            buffer.write(b'\x00\x00\x01\x00') # version
            buffer.write(u32(0)) # padding
            buffer.write(u64(offsets["String"])) # string pool offset
            buffer.write(u64(offsets["HashHeader"]))
            buffer.write(u32(len(self.output_dict)))
            buffer.write(u32(0x18)) # element size
            buffer.write(u64(offsets["Nodes"]))
            buffer.write(u32(count))
            buffer.write(u32(0x18))
            offset = offsets["Indices"]
            for entry in self.output_dict:
                buffer.write(u32(int(entry["Hash"], 16)))
                buffer.write(u32(0)) # padding
                buffer.write(u64(offset))
                offset += 4 * len(entry["Nodes"])
                buffer.write(u32(len(entry["Nodes"])))
                buffer.write(u32(4)) # entry size
            # ideally we'd want to figure out how these are sorted
            nodes = []
            for entry in self.output_dict:
                for node in entry["Nodes"]:
                    nodes.append(node)
            for entry in self.output_dict:
                for node in entry["Nodes"]:
                    buffer.write(u32(nodes.index(node)))
            while buffer.tell() % 8 != 0:
                buffer.write(u8(0))
            offset = offsets["Events"]
            for node in nodes:
                buffer.write(u64(offset))
                buffer.write(u32(len(node["Event"])))
                buffer.write(u32(0x30)) # element size
                buffer.write(u32(int(node["Hash"], 16)))
                buffer.write(u32(node["Unknown"]))
                for event in node["Event"]:
                    for trigger in event["Trigger Array"]:
                        offset += 0x18
                        for param in trigger["Parameters"]:
                            offset += 0x8 + (0x18 if type(param) == list else 0x10)
                    for hold in event["Hold Array"]:
                        offset += 0x18
                        for param in hold["Parameters"]:
                            offset += 0x8 + (0x18 if type(param) == list else 0x10)"""
            
if __name__ == "__main__":
    file = BAEV("Player.root.baev")

    #file.ToBytes("output")
    file.ToJson()