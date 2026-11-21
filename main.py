#!/usr/bin/env python3
"""news-image-20261121: sum up 21 November 2026's world news in one image.

The entry image is entry.png, a broadsheet front page drawn for this
bounty: "THE WORLD IN ONE DAY — Saturday, 21 November 2026", with ten
illustrated panels for the day's ten biggest stories.

Running with no arguments copies entry.png to the output directory
($MAKEFUN_OUTPUT_DIR, default /output) as entry.png. The copy is
byte-identical across runs: the program only copies the shipped file.

    python3 main.py
    python3 main.py --check    # verify the entry files
    python3 main.py --serve    # preview the ad page (index.html)

Standard library only.
"""

import argparse
import hashlib
import os
import shutil
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "entry.png")
AD = os.path.join(HERE, "ad.png")
INDEX = os.path.join(HERE, "index.html")
README = os.path.join(HERE, "README.md")
LICENSE = os.path.join(HERE, "LICENSE")

MAX_ENTRY_BYTES = 1_048_576
MAX_ENTRY_PX = 1024
MAX_AD_BYTES = 8_388_608
MAX_INDEX_BYTES = 2_097_152
DAY = "21 November 2026"


def _png_size(path):
    """Return (width, height) of a PNG file, or None if not a PNG."""
    with open(path, "rb") as f:
        head = f.read(33)
    if len(head) < 33 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def _jpeg_size(path):
    """Return (width, height) of a JPEG file, or None if not a JPEG."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    if data[-2:] != b"\xff\xd9":
        return None
    pos = 2
    while pos + 9 < len(data):
        if data[pos] != 0xFF:
            return None
        marker = data[pos + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        size = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
            return width, height
        pos += 2 + size
    return None


def image_size(path):
    """Return (format, width, height) for a PNG or JPEG file."""
    size = _png_size(path)
    if size is not None:
        return "PNG", size[0], size[1]
    size = _jpeg_size(path)
    if size is not None:
        return "JPEG", size[0], size[1]
    return None, None, None


def _png_chunks_ok(path):
    """Check every PNG chunk's CRC; True only if the file is whole."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    pos = 8
    saw_iend = False
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data):
            return False
        stored = struct.unpack(">I", data[end - 4:end])[0]
        actual = zlib.crc32(ctype + data[pos + 8:end - 4]) & 0xFFFFFFFF
        if stored != actual:
            return False
        if ctype == b"IEND":
            saw_iend = True
            return end == len(data) and saw_iend
        pos = end
    return False


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, "entry.png")
    tmp = os.path.join(output_dir, ".entry.png.tmp")
    shutil.copyfile(ENTRY, tmp)
    if sha256_file(tmp) != sha256_file(ENTRY):
        os.remove(tmp)
        raise IOError("entry.png copy failed verification")
    os.replace(tmp, dest)
    if sha256_file(dest) != sha256_file(ENTRY):
        raise IOError("entry.png copy failed verification after rename")
    return dest


def check():
    problems = []

    # entry.png: real image, <= 1 MiB, <= 1024x1024
    if not os.path.isfile(ENTRY):
        problems.append("entry.png missing")
    else:
        n = os.path.getsize(ENTRY)
        if n > MAX_ENTRY_BYTES:
            problems.append("entry.png is %d bytes, over 1 MiB" % n)
        fmt, w, h = image_size(ENTRY)
        if fmt is None:
            problems.append("entry.png is not a PNG or JPEG")
        elif w > MAX_ENTRY_PX or h > MAX_ENTRY_PX:
            problems.append("entry.png is %dx%d, over 1024x1024" % (w, h))
        if fmt == "PNG" and not _png_chunks_ok(ENTRY):
            problems.append("entry.png PNG chunks fail CRC")
        if fmt == "JPEG":
            with open(ENTRY, "rb") as f:
                data = f.read()
            if data[-2:] != b"\xff\xd9":
                problems.append("entry.png JPEG lacks end marker")

    # ad.png: PNG, <= 8 MB
    if not os.path.isfile(AD):
        problems.append("ad.png missing")
    else:
        n = os.path.getsize(AD)
        if n > MAX_AD_BYTES:
            problems.append("ad.png is %d bytes, over 8 MB" % n)
        fmt, w, h = image_size(AD)
        if fmt != "PNG":
            problems.append("ad.png is not a PNG")
        elif not _png_chunks_ok(AD):
            problems.append("ad.png PNG chunks fail CRC")

    # index.html: <= 2 MB, references ad.png, names the day
    if not os.path.isfile(INDEX):
        problems.append("index.html missing")
    else:
        n = os.path.getsize(INDEX)
        if n > MAX_INDEX_BYTES:
            problems.append("index.html is %d bytes, over 2 MB" % n)
        text = open(INDEX, encoding="utf-8").read()
        if "ad.png" not in text:
            problems.append("index.html does not reference ad.png")
        if DAY not in text:
            problems.append('index.html does not name the day "21 November 2026"')

    # README: carries the bounty badge and the make.fun link
    if not os.path.isfile(README):
        problems.append("README.md missing")
    else:
        text = open(README, encoding="utf-8").read()
        if "make.fun/badge/news-image-20261121.svg" not in text:
            problems.append("README.md lacks the make.fun bounty badge")
        if "https://make.fun/bounty/news-image-20261121" not in text:
            problems.append("README.md lacks the make.fun bounty link")

    # LICENSE: MIT text
    if not os.path.isfile(LICENSE):
        problems.append("LICENSE missing")
    else:
        text = open(LICENSE, encoding="utf-8").read()
        if "MIT License" not in text or "Permission is hereby granted" not in text:
            problems.append("LICENSE is not the MIT license text")

    if problems:
        for p in problems:
            print("FAIL: " + p, file=sys.stderr)
        return 1
    fmt, w, h = image_size(ENTRY)
    print("OK: entry.png %s %dx%d %d bytes" % (fmt, w, h, os.path.getsize(ENTRY)))
    print("OK: ad.png %d bytes" % os.path.getsize(AD))
    print("OK: index.html, README.md, LICENSE all check out")
    return 0


def serve(port=8000):
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    os.chdir(HERE)
    server = ThreadingHTTPServer(("127.0.0.1", port), SimpleHTTPRequestHandler)
    print("Serving the ad page at http://127.0.0.1:%d/index.html" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the entry files and exit")
    parser.add_argument("--serve", action="store_true",
                        help="preview the ad page on localhost")
    parser.add_argument("--port", type=int, default=8000,
                        help="port for --serve (default 8000)")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    if args.serve:
        return serve(args.port)
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    dest = run(out)
    print("wrote %s (%d bytes, sha256 %s)"
          % (dest, os.path.getsize(dest), sha256_file(dest)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
