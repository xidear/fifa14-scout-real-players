# -*- coding: utf-8 -*-
"""Minimal reader/writer for the two pristine FIFA14 EA databases.

Main DB : 90 tables, players table 79, 72-byte rows
New DB  : 123 tables, players table 112, 76-byte rows

All name pointers are absolute offsets relative to the start of *their own*
database.  Keep the two buffers separate; never copy a pointer across DBs.
"""
import struct, hashlib, os

EPOCH_DAYS = 0  # DOB is days since 1582-10-14; caller converts with datetime


def md5_bytes(b):
    return hashlib.md5(b).hexdigest()


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def read_bits(rec, bit_off, width, msb=False):
    v = 0
    if msb:
        for k in range(width):
            b = bit_off + k
            bit = (rec[b >> 3] >> (7 - (b & 7))) & 1
            v = (v << 1) | bit
    else:
        for k in range(width):
            b = bit_off + k
            bit = (rec[b >> 3] >> (b & 7)) & 1
            v |= bit << k
    return v


def write_bits(rec, bit_off, width, value, msb=False):
    if msb:
        for k in range(width):
            b = bit_off + k
            mask = 1 << (7 - (b & 7))
            if (value >> (width - 1 - k)) & 1:
                rec[b >> 3] |= mask
            else:
                rec[b >> 3] &= ~mask
    else:
        for k in range(width):
            b = bit_off + k
            mask = 1 << (b & 7)
            if (value >> k) & 1:
                rec[b >> 3] |= mask
            else:
                rec[b >> 3] &= ~mask


class Layout:
    def __init__(self, name, ntables, players_tbl, links_tbl, teams_tbl,
                 rowsize, name_offs, dob_off, potential_bit, position_bit,
                 nationality_bit):
        self.name = name
        self.ntables = ntables
        self.players_tbl = players_tbl
        self.links_tbl = links_tbl
        self.teams_tbl = teams_tbl
        self.rowsize = rowsize
        self.name_offs = name_offs
        self.dob_off = dob_off
        self.potential_bit = potential_bit
        self.position_bit = position_bit
        self.nationality_bit = nationality_bit


MAIN = Layout("main", 90, 79, 80, 81, 72, (4, 8, 12), 16, 374, 179, 518)
NEWDB = Layout("newdb", 123, 112, 113, 114, 76, (4, 8, 12, 16), 20, 406, 211, 550)

# second preferred position: main bit 189, new 221
MAIN_PREF2 = 189
NEWDB_PREF2 = 221


class FifaDB:
    def __init__(self, data, layout, path=None):
        self.d = bytearray(data)
        self.layout = layout
        self.path = path
        self.offs = list(struct.unpack_from("<%dI" % layout.ntables, self.d, 12))
        self.p_off = self.offs[layout.players_tbl]
        self.p_base = self.p_off + 8
        self.p_end = self.offs[layout.links_tbl]
        self.n = (self.p_end - self.p_base) // layout.rowsize
        self.p_count = struct.unpack_from("<I", self.d, self.p_off)[0]
        self.t_base = self.offs[layout.teams_tbl] + 8
        self.t_end = self.offs[layout.teams_tbl + 1]
        self.tn = (self.t_end - self.t_base) // 44
        self.l_base = self.offs[layout.links_tbl] + 8
        self.l_end = self.offs[layout.teams_tbl]
        self.ln = (self.l_end - self.l_base) // 16
        self._index = None

    @classmethod
    def load(cls, path, layout):
        with open(path, "rb") as f:
            return cls(f.read(), layout, path)

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.d)

    def record_offset(self, pid):
        if self._index is None:
            self._index = {}
            rs = self.layout.rowsize
            for i in range(self.n):
                o = self.p_base + i * rs
                self._index[struct.unpack_from("<I", self.d, o)[0]] = o
        return self._index.get(pid)

    def record(self, pid):
        o = self.record_offset(pid)
        return None if o is None else memoryview(self.d)[o:o + self.layout.rowsize]

    def records(self):
        rs = self.layout.rowsize
        for i in range(self.n):
            o = self.p_base + i * rs
            yield struct.unpack_from("<I", self.d, o)[0], o

    def name_at(self, ptr):
        if not ptr:
            return None
        if ptr + 2 > len(self.d):
            return None
        n = struct.unpack_from("<H", self.d, ptr)[0]
        if n == 0 or ptr + 2 + n > len(self.d):
            return None
        raw = self.d[ptr + 2:ptr + 2 + n]
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", "replace")

    def names(self, pid):
        o = self.record_offset(pid)
        if o is None:
            return None
        return [self.name_at(struct.unpack_from("<I", self.d, o + k)[0]) for k in self.layout.name_offs]

    def dob(self, pid):
        o = self.record(pid)
        return None if o is None else struct.unpack_from("<I", o, self.layout.dob_off)[0]

    def potential(self, pid):
        o = self.record(pid)
        return None if o is None else read_bits(o, self.layout.potential_bit, 7)

    def set_potential(self, pid, value):
        o = self.record(pid)
        if o is None:
            raise KeyError(pid)
        write_bits(o, self.layout.potential_bit, 7, max(0, min(127, int(value))))

    def position(self, pid):
        o = self.record(pid)
        return None if o is None else read_bits(o, self.layout.position_bit, 5)

    def nationality(self, pid):
        o = self.record(pid)
        return None if o is None else read_bits(o, self.layout.nationality_bit, 8, msb=True)

    def linked_pids(self):
        out = set()
        for i in range(self.ln):
            o = self.l_base + i * 16
            out.add(struct.unpack_from("<I", self.d, o)[0])
        return out

    def fake_pids(self):
        return [pid for pid, _ in self.records() if 400000 <= pid <= 416281]

    def team_ids(self):
        out = set()
        for i in range(self.tn):
            out.add(struct.unpack_from("<I", self.d, self.t_base + i * 44)[0])
        return out

    def summary(self):
        return {
            "layout": self.layout.name, "size": len(self.d),
            "players": self.n, "header_count": self.p_count,
            "teams": self.tn, "links": self.ln,
            "fake_count": len(self.fake_pids()),
            "md5": md5_bytes(self.d),
        }


def load_both(main_path, newdb_path):
    return (FifaDB.load(main_path, MAIN), FifaDB.load(newdb_path, NEWDB))


if __name__ == "__main__":
    base = r"D:\FIFA14\work\scout_real_fifa14\base"
    m, n = load_both(os.path.join(base, "main_fifa.db"), os.path.join(base, "newdb_fifa.db"))
    print("main", m.summary())
    print("newdb", n.summary())
    for pid in (158023, 400000, 412236, 408884, 408879):
        print(pid, "main", m.names(pid), m.dob(pid), m.potential(pid), m.position(pid), m.nationality(pid))
        print(pid, "new ", n.names(pid), n.dob(pid), n.potential(pid), n.position(pid), n.nationality(pid))