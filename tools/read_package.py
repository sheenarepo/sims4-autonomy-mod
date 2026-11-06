"""Read back a DBPF package and list its resources (used to check our builder,
and later to read the game's own tuning)."""

import struct
import sys
import zlib


def read_index(data):
    assert data[:4] == b'DBPF', 'not a package'
    count = struct.unpack_from('<I', data, 36)[0]
    index_offset = struct.unpack_from('<Q', data, 64)[0] or struct.unpack_from('<I', data, 40)[0]
    flags = struct.unpack_from('<I', data, index_offset)[0]
    pos = index_offset + 4
    const = {}
    for i, field in enumerate(('type', 'group', 'inst_hi')):
        if flags & (1 << i):
            const[field] = struct.unpack_from('<I', data, pos)[0]
            pos += 4
    entries = []
    for _ in range(count):
        entry = {}
        for field in ('type', 'group', 'inst_hi'):
            if field in const:
                entry[field] = const[field]
            else:
                entry[field] = struct.unpack_from('<I', data, pos)[0]
                pos += 4
        inst_lo, offset, file_size, mem_size = struct.unpack_from('<IIII', data, pos)
        pos += 16
        compression = 0
        if file_size & 0x80000000:
            compression, _committed = struct.unpack_from('<HH', data, pos)
            pos += 4
        entry.update(instance=(entry['inst_hi'] << 32) | inst_lo, offset=offset,
                     file_size=file_size & 0x7FFFFFFF, mem_size=mem_size, compression=compression)
        entries.append(entry)
    return entries


def read_resource(data, entry):
    raw = data[entry['offset']:entry['offset'] + entry['file_size']]
    if entry['compression'] == 0:
        return raw
    if entry['compression'] == 0x5A42:
        return zlib.decompress(raw)
    raise ValueError('unsupported compression 0x{:04X}'.format(entry['compression']))


if __name__ == '__main__':
    data = open(sys.argv[1], 'rb').read()
    for e in read_index(data):
        print('{type:08X}:{group:08X}:{instance:016X} size={mem_size} comp={compression:04X}'.format(**e))
        try:
            body = read_resource(data, e)
            print('   ', body[:160])
        except ValueError as exc:
            print('   ', exc)
