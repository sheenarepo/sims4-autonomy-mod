"""Build SleepControl.ts4script and SleepControl.package into dist/.

Run with Python 3.7 (the game's version):
    python3.7 tools/build.py
"""

import io
import os
import py_compile
import shutil
import struct
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
DIST = os.path.join(ROOT, 'dist')
sys.path.insert(0, SRC)

from sleepcontrol import computer  # noqa: E402

TUNING_TYPE_INTERACTION = 0xE882D22F
STBL_TYPE = 0x220557DA
STBL_GROUP = 0x80000000

DISPLAY_NAME = 'Sleep Control Settings'


def fnv32(text):
    h = 0x811C9DC5
    for byte in text.lower().encode('utf-8'):
        h = (h * 0x01000193) & 0xFFFFFFFF
        h ^= byte
    return h


DISPLAY_NAME_KEY = fnv32('SleepControl:' + DISPLAY_NAME)


# --- Script archive -------------------------------------------------------

def build_script(path):
    if sys.version_info[:2] != (3, 7):
        raise SystemExit('Compile with Python 3.7, not {}'.format(sys.version.split()[0]))
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as zf:
        for folder, _dirs, files in os.walk(SRC):
            if '__pycache__' in folder:
                continue
            for name in sorted(files):
                if not name.endswith('.py'):
                    continue
                source = os.path.join(folder, name)
                rel = os.path.relpath(source, SRC)
                compiled = os.path.join(tmp, rel + 'c')
                os.makedirs(os.path.dirname(compiled), exist_ok=True)
                py_compile.compile(source, cfile=compiled, dfile=rel, doraise=True)
                zf.write(compiled, rel.replace(os.sep, '/') + 'c')


# --- Package (DBPF 2.1) ---------------------------------------------------

def interaction_xml():
    # Matches the game's ImmediateSuperInteraction and DoCommand tuning
    # (allow_autonomous is locked to False by the game, so it is not set here).
    return '''<?xml version="1.0" encoding="utf-8"?>
<I c="ImmediateSuperInteraction" i="interaction" m="interactions.base.immediate_interaction" n="{name}" s="{iid}">
  <L n="basic_extras">
    <V t="do_command">
      <U n="do_command">
        <T n="command">sleepcontrol.menu</T>
      </U>
    </V>
  </L>
  <T n="display_name">0x{key:08X}<!--{label}--></T>
  <T n="pie_menu_priority">9</T>
  <E n="target_type">OBJECT</E>
</I>
'''.format(name=computer.MENU_INTERACTION_NAME, iid=computer.MENU_INTERACTION_ID,
           key=DISPLAY_NAME_KEY, label=DISPLAY_NAME).encode('utf-8')


def stbl(entries):
    body = io.BytesIO()
    strings_length = 0
    for key, text in entries:
        data = text.encode('utf-8')
        body.write(struct.pack('<IBH', key, 0, len(data)))
        body.write(data)
        strings_length += len(data) + 1
    header = b'STBL' + struct.pack('<HBQHI', 5, 0, len(entries), 0, strings_length)
    return header + body.getvalue()


def dbpf(resources):
    """resources: list of (type, group, instance, bytes); stored uncompressed."""
    out = io.BytesIO()
    out.write(b'\0' * 96)
    index = io.BytesIO()
    index.write(struct.pack('<I', 0))
    for rtype, group, instance, data in resources:
        offset = out.tell()
        out.write(data)
        index.write(struct.pack('<IIIIIIIHH', rtype, group, instance >> 32, instance & 0xFFFFFFFF,
                                offset, len(data) | 0x80000000, len(data), 0x0000, 1))
    index_offset = out.tell()
    index_bytes = index.getvalue()
    out.write(index_bytes)
    header = bytearray(96)
    header[0:4] = b'DBPF'
    struct.pack_into('<II', header, 4, 2, 1)
    struct.pack_into('<I', header, 36, len(resources))
    struct.pack_into('<I', header, 44, len(index_bytes))
    struct.pack_into('<I', header, 60, 3)
    struct.pack_into('<Q', header, 64, index_offset)
    result = bytearray(out.getvalue())
    result[0:96] = header
    return bytes(result)


def build_package(path):
    instance = computer.MENU_INTERACTION_ID
    resources = [
        (TUNING_TYPE_INTERACTION, 0, instance, interaction_xml()),
        # English string table; the top byte of the instance is the language (0x00 = English).
        (STBL_TYPE, STBL_GROUP, (instance & 0x00FFFFFFFFFFFFFF), stbl([(DISPLAY_NAME_KEY, DISPLAY_NAME)])),
    ]
    with open(path, 'wb') as f:
        f.write(dbpf(resources))


def main():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    build_script(os.path.join(DIST, 'SleepControl.ts4script'))
    build_package(os.path.join(DIST, 'SleepControl.package'))
    for name in sorted(os.listdir(DIST)):
        print(name, os.path.getsize(os.path.join(DIST, name)), 'bytes')


if __name__ == '__main__':
    main()
