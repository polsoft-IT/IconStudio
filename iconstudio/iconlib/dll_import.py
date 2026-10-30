import struct
import os

RT_ICON = 3
RT_GROUP_ICON = 14


class PEFile:
    def __init__(self, path):
        self.path = path
        self.data = None
        self.sections = []
        self.load()

    def load(self):
        with open(self.path, "rb") as f:
            self.data = f.read()
        e_lfanew = struct.unpack("<I", self.data[0x3C:0x40])[0]
        pe_sig = self.data[e_lfanew:e_lfanew+4]
        if pe_sig != b"PE\x00\x00":
            raise Exception("Not a PE file")
        num_sections = struct.unpack("<H", self.data[e_lfanew+6:e_lfanew+8])[0]
        opt_size = struct.unpack("<H", self.data[e_lfanew+20:e_lfanew+22])[0]
        sec_offset = e_lfanew + 24 + opt_size
        for i in range(num_sections):
            off = sec_offset + i * 40
            name = self.data[off:off+8].rstrip(b"\x00").decode("ascii", errors="ignore")
            vsize = struct.unpack("<I", self.data[off+8:off+12])[0]
            vaddr = struct.unpack("<I", self.data[off+12:off+16])[0]
            raw_size = struct.unpack("<I", self.data[off+16:off+20])[0]
            raw_ptr = struct.unpack("<I", self.data[off+20:off+24])[0]
            self.sections.append({
                "name": name, "vaddr": vaddr, "vsize": vsize,
                "raw_ptr": raw_ptr, "raw_size": raw_size,
            })

    def get_section(self, name):
        for s in self.sections:
            if s["name"] == name:
                return s
        return None

    def rva_to_offset(self, rva):
        for s in self.sections:
            start = s["vaddr"]
            end = start + s["vsize"]
            if start <= rva < end:
                return s["raw_ptr"] + (rva - start)
        return None


class DLLIconImporter:
    def __init__(self, path):
        self.pe = PEFile(path)
        self.icons = []

    def import_icons(self):
        rsrc = self.pe.get_section(".rsrc")
        if not rsrc:
            raise Exception("No .rsrc section")
        base = rsrc["raw_ptr"]
        data = self.pe.data[base:base + rsrc["raw_size"]]
        offset = 0
        size = len(data)
        while offset < size - 16:
            try:
                type_id = struct.unpack("<I", data[offset:offset+4])[0]
                res_id = struct.unpack("<I", data[offset+4:offset+8])[0]
                lang = struct.unpack("<I", data[offset+8:offset+12])[0]
                length = struct.unpack("<I", data[offset+12:offset+16])[0]
                blob = data[offset+16:offset+16+length]
                if type_id == RT_GROUP_ICON:
                    self._parse_group(res_id, blob)
                offset += 16 + length
            except Exception:
                break
        return self.icons

    def _parse_group(self, group_id, blob):
        reserved, type_, count = struct.unpack("<HHH", blob[:6])
        entries = []
        off = 6
        for i in range(count):
            e = struct.unpack("<BBBBHHH", blob[off:off+14])
            off += 14
            entries.append({
                "width": e[0], "height": e[1], "colorcount": e[2],
                "planes": e[4], "bitcount": e[5], "icon_id": e[6],
            })
        ico_data = self._build_ico(entries)
        self.icons.append({"id": group_id, "ico": ico_data})

    def _build_ico(self, entries):
        icon_blobs = []
        for e in entries:
            try:
                blob = self._find_icon_blob(e["icon_id"])
            except Exception:
                blob = b""
            icon_blobs.append(blob)
        header = struct.pack("<HHH", 0, 1, len(entries))
        dir_entries = []
        offset = 6 + len(entries) * 16
        for blob in icon_blobs:
            if len(blob) >= 16:
                width = blob[6]; height = blob[7]; colorcount = blob[8]
                planes = struct.unpack("<H", blob[12:14])[0]
                bitcount = struct.unpack("<H", blob[14:16])[0]
            else:
                width = height = colorcount = planes = bitcount = 0
            size = len(blob)
            dir_entries.append(struct.pack(
                "<BBBBHHII",
                width, height, colorcount, 0,
                planes, bitcount, size, offset
            ))
            offset += size
        return header + b"".join(dir_entries) + b"".join(icon_blobs)

    def _find_icon_blob(self, icon_id):
        rsrc = self.pe.get_section(".rsrc")
        base = rsrc["raw_ptr"]
        data = self.pe.data[base:base + rsrc["raw_size"]]
        offset = 0
        size = len(data)
        while offset < size - 16:
            try:
                type_id = struct.unpack("<I", data[offset:offset+4])[0]
                res_id = struct.unpack("<I", data[offset+4:offset+8])[0]
                lang = struct.unpack("<I", data[offset+8:offset+12])[0]
                length = struct.unpack("<I", data[offset+12:offset+16])[0]
                blob = data[offset+16:offset+16+length]
                if type_id == RT_ICON and res_id == icon_id:
                    return blob
                offset += 16 + length
            except Exception:
                break
        raise Exception("Icon blob not found")
