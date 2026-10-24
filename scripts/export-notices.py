"""Generate notices from installed Python metadata and the real npm lockfile."""

import importlib.metadata as md
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rows = []
for dist in sorted(md.distributions(), key=lambda d: d.metadata["Name"].lower()):
    name = dist.metadata["Name"]
    if name == "credit-cabinet-api":
        continue
    declared = dist.metadata.get("License-Expression") or dist.metadata.get("License")
    if not declared:
        classifiers = [
            v.rsplit(" :: ", 1)[-1]
            for v in dist.metadata.get_all("Classifier", [])
            if v.startswith("License ::")
        ]
        declared = "; ".join(classifiers) or "Not declared in installed metadata"
    files = [str(f) for f in dist.files or [] if "license" in str(f).lower() or "copying" in str(f).lower()]
    rows.append(
        {
            "ecosystem": "Python",
            "name": name,
            "version": dist.version,
            "license": declared.splitlines()[0],
            "license_files": files,
            "source": "installed dist-info metadata",
        }
    )
lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
for package, meta in sorted(lock["packages"].items()):
    if not package:
        continue
    name = package.rsplit("node_modules/", 1)[-1]
    folder = ROOT / "frontend" / package
    files = (
        [
            str(f.relative_to(ROOT)).replace("\\", "/")
            for f in folder.iterdir()
            if f.is_file() and ("license" in f.name.lower() or "copying" in f.name.lower())
        ]
        if folder.exists()
        else []
    )
    rows.append(
        {
            "ecosystem": "npm",
            "name": name,
            "version": meta.get("version"),
            "license": meta.get("license", "Not declared in lockfile"),
            "license_files": files,
            "dev": meta.get("dev", False),
            "source": "package-lock.json package metadata",
        }
    )
FONTS = [
    ("Manrope Variable", "frontend/src/fonts/manrope-*.woff2", "@fontsource-variable/manrope"),
    ("Unbounded Variable", "frontend/src/fonts/unbounded-*.woff2", "@fontsource-variable/unbounded"),
]
FONT_VERSION = "5.3.0"
for name, path, origin in FONTS:
    rows.append(
        {
            "ecosystem": "font (vendored)",
            "name": name,
            "version": FONT_VERSION,
            "license": "OFL-1.1",
            "license_files": [],
            "source": f"{path}, from {origin}",
        }
    )
(ROOT / "docs/third-party-inventory.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
lines = [
    "# Third-party notices",
    "",
    "Inventory generated from actual installed distribution metadata and frontend/package-lock.json. License identifiers below are the packages’ own declarations, not an independent legal assessment. Full license texts remain in the referenced package distributions; source paths are recorded in docs/third-party-inventory.json.",
    "",
    "Reproduce with backend/.venv/Scripts/python.exe scripts/export-notices.py after dependency installation. Includes development and transitive dependencies. OS-specific optional npm packages are recorded from the lockfile even when not installed on this host.",
    "",
    "| Ecosystem | Package | Version | Declared license |",
    "|---|---|---|---|",
]
for r in (r for r in rows if r["ecosystem"] != "font (vendored)"):
    lines.append(
        "| "
        + " | ".join(str(r[k]).replace("|", " / ") for k in ["ecosystem", "name", "version", "license"])
        + " |"
    )
lines += [
    "",
    "Container infrastructure: PostgreSQL 16, WireMock 3.13.2, Nginx, Python, Node.js, uv. Container OS dependencies have their own notices in the images and are outside this package metadata inventory. Check upstream image notices before redistribution.",
    "",
    "EGRUL, FNS and BKI are simulated locally in WireMock; no external financial data, model weights or real bank integrations are distributed.",
    "",
    "## Vendored font files (not npm packages)",
    "",
    "| Asset | Version | Declared license |",
    "|---|---|---|",
]
for name, path, origin in FONTS:
    lines.append(f"| {name} ({path}, from {origin}) | {FONT_VERSION} | OFL-1.1 |")
lines += [
    "",
    "Both fonts are licensed under the SIL Open Font License 1.1 (https://openfontlicense.org/).",
]
(ROOT / "THIRD_PARTY_NOTICES").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Generated notices for {len(rows)} package records")
