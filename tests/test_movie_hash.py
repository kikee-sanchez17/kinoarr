import struct

from app.movie_hash import CHUNK_SIZE, movie_hash


def test_hash_of_zero_filled_file_is_its_size(tmp_path):
    # All chunk words are zero, so only the size is left in the sum.
    video = tmp_path / "zeros.mkv"
    video.write_bytes(bytes(200_000))

    assert movie_hash(video) == f"{200_000:016x}"


def test_hash_sums_first_and_last_chunk_as_little_endian_words(tmp_path):
    first_chunk = struct.pack("<Q", 5) + bytes(CHUNK_SIZE - 8)
    middle = b"\xff" * 1_000  # outside both chunks: ignored
    last_chunk = bytes(CHUNK_SIZE - 8) + struct.pack("<Q", 7)
    video = tmp_path / "movie.mkv"
    video.write_bytes(first_chunk + middle + last_chunk)

    assert movie_hash(video) == f"{2 * CHUNK_SIZE + 1_000 + 5 + 7:016x}"


def test_hash_wraps_around_at_64_bits(tmp_path):
    video = tmp_path / "ones.mkv"
    video.write_bytes(b"\xff" * (2 * CHUNK_SIZE))

    words_per_file = 2 * CHUNK_SIZE // 8
    expected = (2 * CHUNK_SIZE + words_per_file * (2**64 - 1)) % 2**64
    assert movie_hash(video) == f"{expected:016x}"


def test_small_files_have_no_hash(tmp_path):
    video = tmp_path / "tiny.mkv"
    video.write_bytes(bytes(2 * CHUNK_SIZE - 1))

    assert movie_hash(video) is None
