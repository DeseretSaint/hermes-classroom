"""Normalise a provider's picture before it becomes an artifact.

Item 47 of the fifty upgrades. :meth:`coursebook.media.HostMedia.image` used to hand the store
whatever bytes the image provider emitted: any dimensions, any raster format, and every metadata
block the provider happened to attach (EXIF, XMP, PNG text, ICC). A 6000x4000 photograph with a
camera's EXIF therefore shipped as a lesson figure, and a crafted header could ask a decoder for
gigapixels. This module is the one seam that fixes all three:

* **bytes are capped before decode**, against the artifact's own size ceiling (the provider download
  is already capped in ``media._read_image_location``; this is the second, independent gate);
* **the pixel count is capped before ``load()``**, so a decompression bomb raises a typed refusal
  instead of allocating. Pillow's ``DecompressionBombError`` is process-global and triggers at
  *twice* ``MAX_IMAGE_PIXELS``; the explicit header check below refuses anything over the limit
  rather than relying on that doubling;
* **metadata is stripped, orientation applied, the plate cropped to the role's ratio and downscaled
  to the figure width floor, then re-encoded as PNG**. Re-encoding is what makes the strip real:
  the output image carries no EXIF/XMP/text/ICC because a fresh PNG written from pixel data has
  nowhere to put them. The output bytes are then verified — re-opened and checked for an empty
  ``getexif()`` — so a future Pillow that starts copying metadata fails here rather than shipping.

Every run returns the transform as a plain dict for the artifact's provenance: source bytes and
pixels, the crop, the output pixels, and whether the source was animated. The transform is a record
of what happened to these bytes, never a claim that the picture is good — the review gate decides
that separately.

Licence: Pillow is HPND (the PIL-CMU text, verified in the installed ``LICENSE``); declared in
``plugin.yaml`` because this module imports it at runtime.
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - exercised through ``available()`` on a host without Pillow
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover - the declared dependency is absent
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]
    UnidentifiedImageError = OSError  # type: ignore[assignment,misc]

#: The most pixels one decode may allocate. 40 MP clears every plate a provider returns for a 4:3
#: lesson figure (6000x4000 is 24 MP) while refusing a crafted header long before ``load()`` tries
#: to allocate it. Exposed on the module so a test can prove the fixture sits above it.
MAX_IMAGE_PIXELS = 40_000_000

#: The transform's own version. Bumping it re-names the policy in provenance, so a future change in
#: what "normalised" means is visible in the artifact record rather than assumed.
NORMALISE_POLICY = "provider-image.v1"

#: The raster types this seam accepts. Anything else (SVG included) is not a provider picture and
#: must be handled by the producer that made it.
SUPPORTED_MIME = ("image/png", "image/jpeg", "image/webp", "image/gif")

#: The one format every normalised plate is written as: lossless, no place for EXIF, and
#: deterministic given the same pixels (so the same picture hashes to the same bytes).
OUTPUT_MIME = "image/png"

#: Pillow refuses above ``2 * MAX_IMAGE_PIXELS`` by itself; set the module's limit to ours so its
#: two thresholds bracket our explicit check instead of contradicting it.
if Image is not None:  # pragma: no branch - the branch exists only for a Pillow-free host
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class ImageNormaliseError(ValueError):
    """A provider picture this seam refuses to decode, crop or ship."""


def available() -> bool:
    """Whether the declared Pillow dependency is importable on this host."""
    return Image is not None


@dataclass(frozen=True)
class NormalisedImage:
    """The bytes that ship, their MIME type, and the transform that produced them."""

    data: bytes
    mime: str
    transform: dict[str, Any]


def parse_ratio(value: Any) -> float | None:
    """``"4:3"`` → ``4/3``; ``None`` for any spelling this seam cannot read.

    The caller's ratio arrives from :func:`coursebook.media.figure_aspect_ratio`, so it is already
    role-chosen. An unreadable value is not an error: the plate keeps its own ratio and the
    transform says ``"crop": "none"``, which is what a legacy ``aspect_ratio="landscape"`` gets.
    """
    text = str(value or "").strip()
    if not text or ":" not in text:
        return None
    left, _, right = text.partition(":")
    try:
        width = float(left.strip())
        height = float(right.strip())
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width / height


def _crop_box(image: "Image.Image", ratio: float | None) -> tuple[int, int, int, int] | None:
    """The centred crop box that gives ``image`` the ``ratio``, or ``None`` when it already has it.

    Never stretches: the shorter axis of the source is trimmed symmetrically, so a 16:9 provider
    frame becomes a 4:3 plate instead of a squashed one.
    """
    width, height = image.size
    if ratio is None:
        return None
    source_ratio = width / height if height else ratio
    if abs(source_ratio - ratio) <= 0.01:
        return None
    if source_ratio > ratio:
        new_width = max(1, min(width, int(round(height * ratio))))
        left = (width - new_width) // 2
        return (left, 0, left + new_width, height)
    new_height = max(1, min(height, int(round(width / ratio))))
    top = (height - new_height) // 2
    return (0, top, width, top + new_height)


def _clean(image: "Image.Image") -> "Image.Image":
    """A brand-new image from pixel data only: no ``info``, no EXIF, no ICC, no text chunks."""
    mode = "RGBA" if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info else "RGB"
    canvas = Image.new(mode, image.size)
    canvas.paste(image.convert(mode))
    return canvas


def normalise_image(
    data: bytes,
    *,
    mime: str,
    aspect_ratio: str | None,
    target_width_px: int,
    max_bytes: int,
) -> NormalisedImage:
    """Decode, strip, crop to the role's ratio, downscale and re-encode one provider picture.

    Raises :class:`ImageNormaliseError` for a picture this seam cannot ship: over the byte ceiling,
    over the pixel ceiling (a decompression bomb), undecodable, or still carrying metadata after
    the strip. The caller turns that into a text fallback with a reason; it never ships the raw
    bytes as an exception path.
    """
    if Image is None:  # pragma: no cover - the declared dependency is absent
        raise ImageNormaliseError(
            "Pillow is not installed on this host, so a provider picture cannot be normalised"
        )
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ImageNormaliseError("the provider returned no image bytes")
    if len(data) > max_bytes:
        raise ImageNormaliseError(
            f"the provider returned {len(data)} bytes, over the {max_bytes}-byte ceiling for a visual"
        )
    source_mime = str(mime or "")
    if source_mime not in SUPPORTED_MIME:
        raise ImageNormaliseError(f"{source_mime or 'an unknown type'} is not a raster picture this seam normalises")

    with warnings.catch_warnings():
        # Pillow only *warns* between MAX_IMAGE_PIXELS and twice that; the explicit header check
        # below refuses that band, so the warning is noise beside the typed refusal.
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        try:
            opened = Image.open(io.BytesIO(bytes(data)))
        except UnidentifiedImageError as exc:
            raise ImageNormaliseError(
                "the provider bytes are not an image any decoder recognises"
            ) from exc
        except Image.DecompressionBombError as exc:  # type: ignore[union-attr]
            raise ImageNormaliseError(
                f"the picture exceeds the {MAX_IMAGE_PIXELS}-pixel decode ceiling"
            ) from exc
        except OSError as exc:
            raise ImageNormaliseError(f"the provider bytes could not be decoded ({exc})") from exc
    with opened:
        header_width, header_height = opened.size
        pixels = header_width * header_height
        if pixels > MAX_IMAGE_PIXELS:
            # Header-only check: ``load()`` is what allocates, so this refusal costs no memory.
            raise ImageNormaliseError(
                f"the picture declares {header_width}x{header_height} ({pixels} px), over the "
                f"{MAX_IMAGE_PIXELS}-pixel decode ceiling"
            )
        if pixels <= 0:
            raise ImageNormaliseError("the picture declares no pixels")
        source_pixels = [int(header_width), int(header_height)]
        animated = int(getattr(opened, "n_frames", 1) or 1) > 1
        metadata_present = sorted(
            {
                str(key)
                for key in opened.info
                if str(key).lower() in ("exif", "xmp", "icc_profile", "comment", "description")
            }
        )
        had_exif = bool(opened.getexif())
        try:
            transposed = ImageOps.exif_transpose(opened)
            transposed.load()
        except Image.DecompressionBombError as exc:  # type: ignore[union-attr]
            raise ImageNormaliseError(
                f"the picture exceeds the {MAX_IMAGE_PIXELS}-pixel decode ceiling"
            ) from exc
        except OSError as exc:
            raise ImageNormaliseError(f"the provider bytes could not be decoded ({exc})") from exc

        rotated = transposed.size != opened.size
        box = _crop_box(transposed, parse_ratio(aspect_ratio))
        crop_note = "centre" if box is not None else "none"
        working = transposed if box is None else transposed.crop(box)
        width, height = working.size
        floor = max(1, int(target_width_px))
        downscaled = width > floor
        if downscaled:
            scaled_height = max(1, int(round(height * (floor / width))))
            working = working.resize((floor, scaled_height), Image.Resampling.LANCZOS)
        cleaned = _clean(working)
        buffer = io.BytesIO()
        cleaned.save(buffer, format="PNG")
    output = buffer.getvalue()

    # The strip is verified, not assumed: re-open what will ship and prove it carries no EXIF.
    check = Image.open(io.BytesIO(output))
    with check:
        if check.format != "PNG":
            raise ImageNormaliseError(f"re-encoding produced {check.format}, not PNG")
        if dict(check.getexif()):
            raise ImageNormaliseError("re-encoded picture still carries EXIF")
        leaked = sorted(
            str(key)
            for key in check.info
            if str(key).lower() in ("exif", "xmp", "icc_profile", "comment", "description")
        )
        if leaked:
            raise ImageNormaliseError(f"re-encoded picture still carries {', '.join(leaked)}")

    transform = {
        "policy": NORMALISE_POLICY,
        "source_mime": source_mime,
        "source_bytes": int(len(data)),
        "source_pixels": source_pixels,
        "output_mime": OUTPUT_MIME,
        "output_bytes": int(len(output)),
        "output_pixels": [int(cleaned.size[0]), int(cleaned.size[1])],
        "aspect_ratio": str(aspect_ratio or "") or None,
        "crop": crop_note,
        "width_floor_px": floor,
        "downscaled": bool(downscaled),
        "orientation_applied": bool(rotated),
        "animated_to_first_frame": bool(animated),
        "metadata_present": metadata_present,
        "exif_present": bool(had_exif),
        "metadata_stripped": True,
    }
    return NormalisedImage(data=output, mime=OUTPUT_MIME, transform=transform)
