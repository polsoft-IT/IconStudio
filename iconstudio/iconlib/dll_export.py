import struct
import os

RT_ICON = 3
RT_GROUP_ICON = 14


class IconFile:
    def __init__(self, path):
        self.path = path
        self.data = None
        self.entries = []
        self.load()

    def load(self):
        with open(self.path, "rb") as f:
            self.data = f.read()
        idReserved, idType, idCount = struct.unpack("<HHH", self.data[:6])
        offset = 6
        for i in range(idCount):
            entry = struct.unpack("<BBBBHHII", self.data[offset:offset+16])
            offset += 16
            self.entries.append({
                "width": entry[0],
                "height": entry[1],
                "colorcount": entry[2],
                "planes": entry[4],
                "bitcount": entry[5],
                "bytes": entry[6],
                "offset": entry[7],
            })


class DLLBuilder:
    def __init__(self):
        self.resources = []

    def add_icon(self, icon_path, group_id, icon_base_id):
        ico = IconFile(icon_path)
        grp_header = struct.pack("<HHH", 0, 1, len(ico.entries))
        grp_entries = []
        for i, e in enumerate(ico.entries):
            grp_entries.append(struct.pack(
                "<BBBBHHH",
                e["width"], e["height"], e["colorcount"], 0,
                e["planes"], e["bitcount"],
                icon_base_id + i
            ))
        group_data = grp_header + b"".join(grp_entries)
        self.resources.append({
            "type": RT_GROUP_ICON,
            "id": group_id,
            "lang": 0,
            "data": group_data
        })
        for i, e in enumerate(ico.entries):
            img = ico.data[e["offset"]:e["offset"] + e["bytes"]]
            self.resources.append({
                "type": RT_ICON,
                "id": icon_base_id + i,
                "lang": 0,
                "data": img
            })

    def build(self, out_path):
        dos_header = b"MZ" + b"\x00" * 58 + struct.pack("<I", 0x80)
        dos_header += b"\x00" * (0x80 - len(dos_header))
        pe_header = b"PE\x00\x00"
        machine = 0x014C
        sections = 1
        timestamp = 0
        sym_table = 0
        sym_count = 0
        opt_header_size = 0xE0
        characteristics = 0x210E
        file_header = struct.pack(
            "<HHIIIHH",
            machine, sections, timestamp,
            sym_table, sym_count,
            opt_header_size, characteristics
        )
        opt_header = b"\x0B\x01" + b"\x00" * (opt_header_size - 2)
        rsrc_data = self.build_resource_section()
        rsrc_size = len(rsrc_data)
        rsrc_raw_ptr = 0x200
        section_header = struct.pack(
            "<8sIIIIIIHHI",
            b".rsrc\x00\x00",
            rsrc_size, 0x1000, rsrc_size, rsrc_raw_ptr,
            0, 0, 0, 0, 0
        )
        header = dos_header + pe_header + file_header + opt_header + section_header
        if len(header) > rsrc_raw_ptr:
            raise ValueError("PE header larger than resource section offset")
        padding = b"\x00" * (rsrc_raw_ptr - len(header))
        with open(out_path, "wb") as f:
            f.write(header)
            f.write(padding)
            f.write(rsrc_data)

    def build_resource_section(self):
        types = {}
        for r in self.resources:
            types.setdefault(r["type"], []).append(r)
        blob = b""
        for t, items in types.items():
            for r in items:
                blob += struct.pack("<I", t)
                blob += struct.pack("<I", r["id"])
                blob += struct.pack("<I", r["lang"])
                blob += struct.pack("<I", len(r["data"]))
                blob += r["data"]
        return blob
