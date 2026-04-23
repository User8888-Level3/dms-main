from pathlib import Path
from photo_index.hasher import sha1_of_file

def test_sha1_matches_known_value(tmp_path: Path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    # sha1("hello world") = 2aae6c35c94fcfb415dbe95f408b9ce91ee846ed
    assert sha1_of_file(p) == "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"
