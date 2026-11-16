#!/usr/bin/env python3
"""ELF evidence for the manual validation sample: symbol lines (nm / nm -D style), and JNINativeMethod
entries ({char *name; char *signature; void *fnPtr}, 24 bytes) decoded from a library's relocations."""
import hashlib, os
from functools import lru_cache
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

R_X86_64_64, R_X86_64_RELATIVE = 1, 8


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def symbolized(path):
    """the Dataset_symbolized copy of a Dataset library (same file, symbols added), if any"""
    s = path.replace("/Dataset/", "/Dataset_symbolized/")
    return s if s != path and os.path.isfile(s) else path


class Elf:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        self.e = ELFFile(self.f)
        self.dyn, self.all = {}, {}     # name -> (value, letter); all = dynsym + symtab
        for secname in (".dynsym", ".symtab"):
            sec = self.e.get_section_by_name(secname)
            if not sec:
                continue
            for s in sec.iter_symbols():
                if not s.name or s["st_shndx"] == "SHN_UNDEF":
                    continue
                typ, bind = s["st_info"]["type"], s["st_info"]["bind"]
                if typ not in ("STT_FUNC", "STT_GNU_IFUNC", "STT_LOOS", "STT_OBJECT", "STT_NOTYPE"):
                    continue
                letter = "i" if typ in ("STT_GNU_IFUNC", "STT_LOOS") else ("W" if bind == "STB_WEAK" else "T")
                if typ == "STT_OBJECT":
                    letter = "D"
                if bind == "STB_LOCAL":
                    letter = letter.lower()
                name = s.name.split("@")[0]
                v = (s["st_value"], letter)
                if secname == ".dynsym":
                    self.dyn.setdefault(name, v)
                self.all.setdefault(name, v)
        self.needed = [t.needed for t in (self.e.get_section_by_name(".dynamic") or [None]).iter_tags()
                       if t.entry.d_tag == "DT_NEEDED"] if self.e.get_section_by_name(".dynamic") else []
        self.by_addr = {}
        for n, (v, l) in self.all.items():
            if l.upper() in ("T", "W", "I"):
                self.by_addr.setdefault(v, []).append(n)

    def sym_line(self, name):
        """('nm -D' | 'nm' | None, line)"""
        if name in self.dyn:
            v, l = self.dyn[name]
            return "nm -D", f"{v:016x} {l} {name}"
        if name in self.all:
            v, l = self.all[name]
            return "nm", f"{v:016x} {l} {name} (local, not exported)"
        return None, ""

    def addr(self, name):
        return self.all.get(name, (None, None))[0]

    def _cstr(self, vaddr):
        for seg in self.e.iter_segments():
            if seg["p_type"] == "PT_LOAD" and seg["p_vaddr"] <= vaddr < seg["p_vaddr"] + seg["p_filesz"]:
                off = seg["p_offset"] + vaddr - seg["p_vaddr"]
                self.f.seek(off)
                b = self.f.read(400)
                z = b.find(b"\0")
                if z <= 0:
                    return None
                try:
                    return b[:z].decode("ascii")
                except UnicodeDecodeError:
                    return None
        return None

    def file_off(self, vaddr):
        for seg in self.e.iter_segments():
            if seg["p_type"] == "PT_LOAD" and seg["p_vaddr"] <= vaddr < seg["p_vaddr"] + seg["p_filesz"]:
                return seg["p_offset"] + vaddr - seg["p_vaddr"]
        return None

    @lru_cache(maxsize=None)
    def jni_tables(self):
        """name -> [(entry vaddr, name, signature, fn target)]; fn target = int address or symbol name"""
        rel = {}
        for sec in self.e.iter_sections():
            if not isinstance(sec, RelocationSection) or not sec.is_RELA():
                continue
            symtab = self.e.get_section(sec["sh_link"]) if sec["sh_link"] else None
            for r in sec.iter_relocations():
                t = r["r_info_type"]
                if t == R_X86_64_RELATIVE:
                    rel[r["r_offset"]] = r["r_addend"]
                elif t == R_X86_64_64 and symtab is not None:
                    s = symtab.get_symbol(r["r_info_sym"])
                    v = s["st_value"] if s["st_shndx"] != "SHN_UNDEF" and s["st_value"] else s.name.split("@")[0]
                    rel[r["r_offset"]] = v + r["r_addend"] if isinstance(v, int) else v
        out = {}
        for o in sorted(rel):
            a, b, c = rel.get(o), rel.get(o + 8), rel.get(o + 16)
            if not isinstance(a, int) or not isinstance(b, int) or c is None:
                continue
            sig = self._cstr(b)
            if not sig or not sig.startswith("(") or ")" not in sig:
                continue
            name = self._cstr(a)
            if not name or not (name[0].isalpha() or name[0] in "_$"):
                continue
            out.setdefault(name, []).append((o, name, sig, c))
        return out


@lru_cache(maxsize=64)
def elf(path):
    return Elf(path)


def jni_mangle(s):
    out = []
    for ch in s:
        if ch == "." or ch == "/":
            out.append("_")
        elif ch == "_":
            out.append("_1")
        elif ch == ";":
            out.append("_2")
        elif ch == "[":
            out.append("_3")
        elif ch.isalnum() and ord(ch) < 128:
            out.append(ch)
        else:
            out.append("_0%04x" % ord(ch))
    return "".join(out)


def jni_short_name(java):
    cls, meth = java.rsplit(".", 1)
    return "Java_" + jni_mangle(cls) + "_" + jni_mangle(meth)
