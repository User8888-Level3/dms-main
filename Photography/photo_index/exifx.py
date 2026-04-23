import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
import piexif

from .retry import smb_retry

_TAG_DATETIME_ORIGINAL = 0x9003  # ExifIFD
_TAG_MAKE  = 0x010F
_TAG_MODEL = 0x0110


@dataclass(frozen=True)
class ExifData:
    taken_at: str | None = None    # ISO8601
    camera: str | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None


def _gps_to_decimal(ref, vals) -> float | None:
    try:
        d = vals[0][0] / vals[0][1]
        m = vals[1][0] / vals[1][1]
        s = vals[2][0] / vals[2][1]
        dec = d + m / 60 + s / 3600
        if ref in (b"S", b"W", "S", "W"):
            dec = -dec
        return dec
    except Exception:
        return None


@smb_retry()
def extract_exif(p: Path) -> ExifData:
    try:
        raw = piexif.load(str(p))
    except OSError:
        raise  # let smb_retry retry SMB hiccups
    except Exception:
        return ExifData()
    taken_at = None
    dto = raw.get("Exif", {}).get(_TAG_DATETIME_ORIGINAL)
    if dto:
        s = dto.decode("ascii", "ignore").strip("\x00 ")
        # "YYYY:MM:DD HH:MM:SS" → "YYYY-MM-DDTHH:MM:SS"
        if len(s) >= 19 and s[4] == ":" and s[7] == ":":
            taken_at = s[:4] + "-" + s[5:7] + "-" + s[8:10] + "T" + s[11:19]
    make = raw.get("0th", {}).get(_TAG_MAKE, b"").decode("ascii", "ignore").strip("\x00 ")
    model = raw.get("0th", {}).get(_TAG_MODEL, b"").decode("ascii", "ignore").strip("\x00 ")
    camera = _join_camera(make, model)
    gps = raw.get("GPS", {}) or {}
    lat = lon = None
    if gps:
        lat_ref = gps.get(1)
        lat_val = gps.get(2)
        lon_ref = gps.get(3)
        lon_val = gps.get(4)
        if lat_val and lat_ref:
            lat = _gps_to_decimal(lat_ref, lat_val)
        if lon_val and lon_ref:
            lon = _gps_to_decimal(lon_ref, lon_val)
    return ExifData(taken_at=taken_at, camera=camera, gps_lat=lat, gps_lon=lon)


def _join_camera(make: str, model: str) -> str | None:
    """Make + Model without redundant prefix ("Canon" + "Canon EOS RP" → "Canon EOS RP")."""
    make = (make or "").strip()
    model = (model or "").strip()
    if model and make and model.lower().startswith(make.lower()):
        return model
    joined = f"{make} {model}".strip()
    return joined or None


def _parse_exiftool_datetime(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    # exiftool returns "YYYY:MM:DD HH:MM:SS" or with fractional/timezone suffixes
    if len(s) >= 19 and s[4] == ":" and s[7] == ":":
        return s[:4] + "-" + s[5:7] + "-" + s[8:10] + "T" + s[11:19]
    return None


@smb_retry()
def extract_exif_exiftool(p: Path) -> ExifData:
    """Extract EXIF via exiftool JSON. Used for CR3/ARW/NEF/MP4/MOV where piexif fails."""
    try:
        r = subprocess.run(
            ["exiftool", "-json", "-n",
             "-DateTimeOriginal", "-CreateDate", "-MediaCreateDate",
             "-Make", "-Model",
             "-GPSLatitude", "-GPSLongitude",
             str(p)],
            capture_output=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return ExifData()
    if r.returncode != 0 or not r.stdout:
        return ExifData()
    try:
        items = json.loads(r.stdout)
    except json.JSONDecodeError:
        return ExifData()
    if not items:
        return ExifData()
    meta = items[0]
    taken_at = (_parse_exiftool_datetime(meta.get("DateTimeOriginal"))
                or _parse_exiftool_datetime(meta.get("CreateDate"))
                or _parse_exiftool_datetime(meta.get("MediaCreateDate")))
    make = (meta.get("Make") or "").strip()
    model = (meta.get("Model") or "").strip()
    camera = _join_camera(make, model)
    lat = meta.get("GPSLatitude")
    lon = meta.get("GPSLongitude")
    lat = float(lat) if isinstance(lat, (int, float)) else None
    lon = float(lon) if isinstance(lon, (int, float)) else None
    return ExifData(taken_at=taken_at, camera=camera, gps_lat=lat, gps_lon=lon)
