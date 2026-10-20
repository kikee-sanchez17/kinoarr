"""OpenSubtitles' file hash, which identifies one exact release of a movie.

The hash is the file size plus the first and last 64 KiB of the file read as
little-endian 64-bit integers, all summed modulo 2**64.
"""

import struct
from pathlib import Path

CHUNK_SIZE = 64 * 1024
WORD_FORMAT = "<Q"  # little-endian unsigned 64-bit
WORD_SIZE = struct.calcsize(WORD_FORMAT)
HASH_MASK = 2**64 - 1


def movie_hash(video_path: Path) -> str | None:
    """Return the 16-hex-digit hash, or None for files too small to hash (under 128 KiB)."""
    size = video_path.stat().st_size
    if size < 2 * CHUNK_SIZE:
        return None
    with video_path.open("rb") as video:
        first_chunk = video.read(CHUNK_SIZE)
        video.seek(-CHUNK_SIZE, 2)
        last_chunk = video.read(CHUNK_SIZE)
    total = (size + _sum_words(first_chunk) + _sum_words(last_chunk)) & HASH_MASK
    return f"{total:016x}"


def _sum_words(chunk: bytes) -> int:
    return sum(word for (word,) in struct.iter_unpack(WORD_FORMAT, chunk))
