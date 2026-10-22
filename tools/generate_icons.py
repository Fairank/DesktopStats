"""Compose the exact approved Niangao vector with a small status pulse.

All Qt work is offscreen. This tool never creates a window or imports the app.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 56, 64, 96, 128, 256)
PNG_SIZES = (*ICO_SIZES, 512, 1024)
INK = "#242b36"
PAPER = "#ffffff"
BLUE = "#087bfa"
SOURCE_BLOB = "4bc4949f8f807b54eb3801e54e3cdbb88d212588"
SOURCE_PATH_SHA = "974330e09361a6b6bc2df3fe16f8ace94c8b09719c2e703c8d2871d2e354d27e"


def optical_svg(size: int) -> str:
    """Adjust only layout/pulse, never the original face path or its proportions."""
    if size < 16:
        raise ValueError("The smallest optical size is 16 pixels")
    source = (ASSETS / "niangao-source.svg").read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    if blob != SOURCE_BLOB:
        raise ValueError("Niangao source differs from the approved FieldDock blob")
    face = re.search(r"<path\b[^>]+/>", source.decode("utf-8")).group(0)
    # Size-specific pixel placement, with exactly the same uniformly scaled face.
    face_width, top, inset, radius, wave_y, peak, low, stroke = {
        16: (12.3, 1.4, 1, 3.4, 13.7, 13.05, 14.3, 1.0),
        20: (15.2, 1.8, 1, 4.3, 17, 15.95, 18, 1.05),
        24: (18.5, 2.1, 1.5, 5.3, 20.5, 19.4, 21.7, 1.3),
        32: (24.7, 2.7, 2, 7.2, 27.6, 25.8, 29.1, 1.45),
        40: (31, 3.5, 2.5, 9, 34.3, 32.7, 36.5, 1.85),
        48: (37, 4.5, 3, 10.8, 41.1, 39.3, 43.7, 2.05),
        56: (43.7, 5, 3.5, 12.6, 48, 45.8, 51, 2.3),
    }.get(size, tuple(value * size / 64 for value in (50, 5.8, 4, 14.4, 55, 52.9, 58, 2.6)))
    scale = face_width / 1089
    left = (size - face_width) / 2
    wave = (
        f"M{size * 0.30:g} {wave_y:g}H{size * 0.41:g}"
        f"L{size * 0.46:g} {peak:g} {size * 0.55:g} {low:g}"
        f" {size * 0.61:g} {wave_y:g}H{size * 0.70:g}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">\n'
        f'<rect x="{inset:g}" y="{inset:g}" width="{size - 2 * inset:g}" '
        f'height="{size - 2 * inset:g}" rx="{radius:g}" fill="{PAPER}"/>\n'
        f'<g id="niangao-original" transform="translate({left:g} {top:g}) '
        f'scale({scale:.12g}) translate(-82 -147)">{face}</g>\n'
        f'<path id="status-pulse" d="{wave}" fill="none" stroke="{BLUE}" stroke-width="{stroke:g}" '
        'stroke-linecap="round" stroke-linejoin="round"/>\n</svg>\n'
    )


def make_ico(frames: dict[int, bytes]) -> bytes:
    """Wrap separately rendered PNG frames without resampling or re-encoding."""
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    directory, payloads = [], []
    for size, png in frames.items():
        directory.append(
            struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset)
        )
        payloads.append(png)
        offset += len(png)
    return header + b"".join(directory) + b"".join(payloads)


def qt_runtime():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication(["desktop-stats-icon-assets"])
    if app.platformName() != "offscreen":
        raise RuntimeError("Asset generation requires the offscreen Qt platform")
    return app


def render_svg(svg: str, size: int):
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("Invalid SVG")
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


def png_bytes(image) -> bytes:
    from PySide6.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise ValueError("PNG encoding failed")
    return bytes(buffer.data())


def generated_files() -> dict[str, bytes]:
    files = {"niangao-source.svg": (ASSETS / "niangao-source.svg").read_bytes()}
    for size in PNG_SIZES:
        svg = optical_svg(size)
        files[f"icon-{size}.svg"] = svg.encode("utf-8")
        files[f"icon-{size}.png"] = png_bytes(render_svg(svg, size))
    files["icon.svg"] = files["icon-1024.svg"]
    files["icon.png"] = files["icon-1024.png"]
    files["icon.ico"] = make_ico({size: files[f"icon-{size}.png"] for size in ICO_SIZES})
    manifest = {
        "format": 1,
        "source": "Unmodified approved FieldDock Niangao path, uniformly scaled; added status pulse",
        "identity_source": {
            "url": "https://github.com/Fairank/FieldDock/blob/main/branding/niangao-v1.svg",
            "git_blob_sha": SOURCE_BLOB,
            "face_path_sha256": SOURCE_PATH_SHA,
            "preservation": "Same complete black evenodd path at every size; no face redesign",
        },
        "generator": "tools/generate_icons.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "ico_sizes": ICO_SIZES,
        "optical_tiers": {
            "16/20/24": "Original face, size-specific uniform placement; thin separated blue pulse",
            "32/40/48/56": "Original face, calibrated padding and pulse weight only",
            "64+": "Original face, proportional composition; no bitmap enlargement",
        },
        "files": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in files.items()
        },
    }
    files["icon-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    return files


def proof_sheet(path: Path):
    """Show actual 1x assets and explicitly labeled nearest-neighbor enlargements."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter

    font_file = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
    if font_file.is_file():
        QFontDatabase.addApplicationFont(str(font_file))
    image = QImage(1060, 800, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#e8edf4"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(QFont("Segoe UI", 15))
    painter.setPen(QColor(INK))
    painter.drawText(30, 38, "Desktop Stats / original Niangao face + status pulse")
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(30, 63, "Asset proof only. Offscreen rendering; no Windows taskbar capture.")
    sizes = (16, 20, 24, 32, 48, 64)
    for index, (color, title, ink) in enumerate(
        (("#ffffff", "Light background", INK), ("#20242b", "Dark background", "#f4f7fb"))
    ):
        y = 85 + index * 345
        painter.fillRect(QRect(20, y, 1020, 335), QColor(color))
        painter.setPen(QColor(ink))
        painter.drawText(40, y + 29, title + " / top: native 1x / bottom: nearest-neighbor 3x")
        for column, size in enumerate(sizes):
            x = 100 + column * 165
            source = render_svg(optical_svg(size), size)
            painter.drawImage(x - size // 2, y + 48, source)
            painter.drawText(
                QRect(x - 60, y + 112, 120, 24), Qt.AlignmentFlag.AlignCenter, str(size)
            )
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            magnified = source.scaled(
                size * 3,
                size * 3,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            painter.drawImage(x - size * 3 // 2, y + 156 - size // 2, magnified)
    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise ValueError("Could not save proof")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify committed assets without writing"
    )
    parser.add_argument("--proof", type=Path, help="Optional asset-only offscreen proof PNG")
    args = parser.parse_args()
    app = qt_runtime()
    files = generated_files()
    mismatch = []
    for name, data in files.items():
        target = ASSETS / name
        if args.check:
            if not target.is_file() or target.read_bytes() != data:
                mismatch.append(name)
        else:
            target.write_bytes(data)
    if args.proof:
        proof = args.proof.resolve()
        if not proof.is_relative_to(ROOT / "qa-private"):
            raise ValueError("Proof output must stay in this project's qa-private directory")
        proof_sheet(proof)
    print(
        json.dumps(
            {
                "ok": not mismatch,
                "files": len(files),
                "mismatches": mismatch,
                "platform": app.platformName(),
                "windows_created": 0,
            }
        )
    )
    return 1 if mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
