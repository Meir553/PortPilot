"""Generate a minimal placeholder icon for PortPilot. Only runs if icon.ico doesn't exist.
   Run with --force to overwrite: python scripts/build_icon.py --force"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Install Pillow: pip install Pillow")
    raise SystemExit(1)


def main() -> None:
    out = Path(__file__).parent.parent / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and "--force" not in sys.argv:
        print(f"Icon exists: {out} (use --force to overwrite)")
        return
    img = Image.new("RGBA", (32, 32), (37, 99, 235, 255))  # Blue (#2563eb)
    img.save(out, format="ICO", sizes=[(32, 32), (16, 16)])
    print(f"Created {out}")


if __name__ == "__main__":
    main()
