import hashlib
import warnings
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from cognitive_os.domain.errors import ApplicationError


def resolve_file(root: Path, storage_key: str) -> Path:
    base = root.resolve()
    target = (base / storage_key).resolve()
    if not target.is_relative_to(base):
        raise ApplicationError(404, "Evidence file not found")
    return target


def save_image(root: Path, file: BinaryIO, prefix: str, max_bytes: int) -> tuple[str, str, str, int]:
    data = file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ApplicationError(413, "Evidence exceeds the size limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ApplicationError(415, "Only PNG, JPEG and WebP images are supported")
                media_type = Image.MIME[image.format]
                extension = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}[image.format]
                image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ApplicationError(415, "Invalid image") from exc
    key = f"{prefix}/{uuid4()}.{extension}"
    target = resolve_file(root, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(data)
    return key, media_type, hashlib.sha256(data).hexdigest(), len(data)
