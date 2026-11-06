#!/usr/bin/env python3
"""Crop the banner from the in-situ photograph. Stdlib only.

    python3 scripts/make_banner.py

sips crops only to a centred rectangle, so the JPEG is converted to PNG, cut here, and
written back out. Crop boxes are constants rather than arguments: a banner is a framing
decision and belongs in the file, not in somebody's shell history.

Boxes are in the source image's own pixels (3024 x 4032).
"""
import os, struct, subprocess, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'images', 'finished-in-situ.jpeg')
TMP = '/tmp/_banner_full.png'

# x0, y0, x1, y1
BOXES = {
    # the object alone: the cabinet and the monitor standing on it, nothing else
    'banner-object.png': (495, 2090, 1020, 2900),
    # wider: the cabinet in the room, chrome returning the light. Includes two record
    # sleeves on the floor, one carrying a face - third-party artwork, so this one is
    # a decision rather than a default.
    'banner-room.png':   (303, 2150, 1830, 2900),
}


def read_png(p):
    d = open(p, 'rb').read()
    i, idat = 8, b''
    while i < len(d):
        ln = struct.unpack('>I', d[i:i + 4])[0]
        t, body = d[i + 4:i + 8], d[i + 8:i + 8 + ln]; i += 12 + ln
        if t == b'IHDR': w, h, bd, ct = struct.unpack('>IIBB', body[:10])
        elif t == b'IDAT': idat += body
        elif t == b'IEND': break
    raw = zlib.decompress(idat)
    n = {0: 1, 2: 3, 4: 2, 6: 4}[ct]; assert bd == 8
    stride = w * n
    out = bytearray(h * stride); prev = bytearray(stride); pos = 0
    for y in range(h):
        f = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos + stride]); pos += stride
        if f == 1:
            for x in range(n, stride): line[x] = (line[x] + line[x - n]) & 255
        elif f == 2:
            for x in range(stride): line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = line[x - n] if x >= n else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - n] if x >= n else 0
                c = prev[x - n] if x >= n else 0
                b_ = prev[x]; p_ = a + b_ - c
                pa, pb, pc = abs(p_ - a), abs(p_ - b_), abs(p_ - c)
                pr = a if (pa <= pb and pa <= pc) else (b_ if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out[y * stride:(y + 1) * stride] = line; prev = line
    return w, h, n, out


def write_png(path, w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n'
                           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(bytes(raw), 6)) + chunk(b'IEND', b''))


def main():
    subprocess.run(['sips', '-s', 'format', 'png', SRC, '--out', TMP],
                   check=True, capture_output=True)
    W, H, n, px = read_png(TMP)
    print('source %dx%d' % (W, H))
    for name, (x0, y0, x1, y1) in BOXES.items():
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x1), min(H, y1)
        cw, ch = x1 - x0, y1 - y0
        buf = bytearray(cw * ch * 3)
        for y in range(ch):
            s = ((y0 + y) * W + x0) * n
            d = y * cw * 3
            for x in range(cw):
                buf[d + x * 3:d + x * 3 + 3] = px[s + x * n:s + x * n + 3]
        out = os.path.join(ROOT, 'images', name)
        write_png(out, cw, ch, buf)
        subprocess.run(['sips', '-Z', '1600', out], check=True, capture_output=True)
        print('  %-20s %4d x %-4d  ratio %.2f' % (name, cw, ch, cw / float(ch)))
    os.remove(TMP)
    return 0


if __name__ == '__main__':
    sys.exit(main())
