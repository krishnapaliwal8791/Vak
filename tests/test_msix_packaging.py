"""Automated validation tests for Microsoft Store MSIX packaging."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parent.parent
MSIX_DIR = ROOT / "packaging" / "msix"
MANIFEST_PATH = MSIX_DIR / "AppxManifest.xml"
ASSETS_DIR = MSIX_DIR / "assets"
DIST_VAK = ROOT / "dist" / "Vak"


def _load_manifest_tree() -> tuple[ET.Element, dict[str, str]]:
    assert MANIFEST_PATH.exists(), f"AppxManifest.xml missing at {MANIFEST_PATH}"
    tree = ET.parse(MANIFEST_PATH)
    root = tree.getroot()
    namespaces = {
        "ns": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
        "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
        "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
    }
    return root, namespaces


def test_manifest_identity_values() -> None:
    """Verify that the manifest contains the exact official Microsoft Partner Center identity."""
    root, ns = _load_manifest_tree()
    identity = root.find("ns:Identity", ns)
    assert identity is not None, "<Identity> element missing in manifest"

    assert identity.get("Name") == "KrishnaPaliwal.Vak"
    assert identity.get("Publisher") == "CN=64DF6549-DA84-46CD-9BF7-D9FEDC5BB19B"
    assert identity.get("ProcessorArchitecture") == "x64"

    properties = root.find("ns:Properties", ns)
    assert properties is not None, "<Properties> element missing in manifest"
    display_name = properties.find("ns:DisplayName", ns)
    assert display_name is not None and display_name.text == "Vak", (
        f"Package display name must match reserved Store name 'Vak', got '{display_name.text if display_name is not None else None}'"
    )
    pub_display = properties.find("ns:PublisherDisplayName", ns)
    assert pub_display is not None and pub_display.text == "Krishna Paliwal"


def test_package_version_format() -> None:
    """Verify that the package version uses a valid four-part format (Major.Minor.Build.Revision)."""
    root, ns = _load_manifest_tree()
    identity = root.find("ns:Identity", ns)
    assert identity is not None

    version = identity.get("Version")
    assert version is not None, "Version attribute missing in <Identity>"

    pattern = r"^\d+\.\d+\.\d+\.\d+$"
    assert re.match(pattern, version), f"Version '{version}' is not a valid 4-part quad (e.g. 1.0.0.0)"

    parts = [int(p) for p in version.split(".")]
    assert len(parts) == 4
    # Store policy requirement: revision should be 0 for standard public submissions
    assert parts[3] == 0, f"Revision part of version '{version}' should be 0"


def test_manifest_executable_and_entrypoint() -> None:
    """Verify that the manifest points to the correct executable and FullTrust entry point."""
    root, ns = _load_manifest_tree()
    app = root.find("ns:Applications/ns:Application", ns)
    assert app is not None, "<Application> element missing"

    assert app.get("Id") == "Vak"
    assert app.get("Executable") == "Vak.exe"
    assert app.get("EntryPoint") == "Windows.FullTrustApplication"

    visual = app.find("uap:VisualElements", ns)
    assert visual is not None, "<VisualElements> missing in application"
    assert visual.get("DisplayName") == "Vak"


def test_manifest_referenced_assets_exist_and_valid() -> None:
    """Verify that all visual assets referenced in the manifest exist with valid formats and dimensions."""
    root, ns = _load_manifest_tree()

    # Store logo in Properties
    properties = root.find("ns:Properties", ns)
    assert properties is not None
    logo_elem = properties.find("ns:Logo", ns)
    assert logo_elem is not None and logo_elem.text
    logo_filename = Path(logo_elem.text).name
    logo_file = ASSETS_DIR / logo_filename
    assert logo_file.exists(), f"Store logo asset {logo_file} does not exist"

    # Visual elements
    visual = root.find("ns:Applications/ns:Application/uap:VisualElements", ns)
    assert visual is not None, "<VisualElements> missing in manifest"

    sq150 = visual.get("Square150x150Logo")
    assert sq150 and (ASSETS_DIR / Path(sq150).name).exists()
    sq44 = visual.get("Square44x44Logo")
    assert sq44 and (ASSETS_DIR / Path(sq44).name).exists()

    default_tile = visual.find("uap:DefaultTile", ns)
    assert default_tile is not None
    wide310 = default_tile.get("Wide310x150Logo")
    assert wide310 and (ASSETS_DIR / Path(wide310).name).exists()

    splash = visual.find("uap:SplashScreen", ns)
    assert splash is not None
    splash_img = splash.get("Image")
    assert splash_img and (ASSETS_DIR / Path(splash_img).name).exists()

    # Dimension and PNG integrity checks
    expected_dimensions = {
        "Square44x44Logo.png": (44, 44),
        "Square150x150Logo.png": (150, 150),
        "Wide310x150Logo.png": (310, 150),
        "StoreLogo.png": (50, 50),
        "SplashScreen.png": (620, 300),
    }

    for filename, expected_size in expected_dimensions.items():
        img_path = ASSETS_DIR / filename
        assert img_path.exists(), f"Asset {filename} missing"
        with Image.open(img_path) as img:
            assert img.format == "PNG", f"{filename} is not PNG format"
            assert img.size == expected_size, f"{filename} size {img.size} does not match {expected_size}"


def test_pyinstaller_payload_completeness() -> None:
    """Verify that all required PyInstaller files exist in dist/Vak for packaging."""
    assert DIST_VAK.exists(), f"PyInstaller output directory missing at {DIST_VAK}"

    vak_exe = DIST_VAK / "Vak.exe"
    assert vak_exe.exists() and vak_exe.stat().st_size > 0, "Vak.exe missing or empty"

    internal = DIST_VAK / "_internal"
    assert internal.exists(), "_internal directory missing"

    # Core dependencies
    pyside = internal / "PySide6"
    assert pyside.exists(), "PySide6 missing in _internal"

    sounddevice = internal / "_sounddevice_data"
    assert sounddevice.exists(), "sounddevice data missing in _internal"

    torch_dir = internal / "torch"
    assert torch_dir.exists(), "torch missing in _internal"

    whisper_dlls = list(internal.glob("whisper-*.dll"))
    assert len(whisper_dlls) > 0, "whisper DLLs missing in _internal"


def test_capabilities_justified() -> None:
    """Verify that only justified capabilities are declared in the manifest."""
    root, ns = _load_manifest_tree()
    caps = root.find("ns:Capabilities", ns)
    assert caps is not None, "<Capabilities> missing in manifest"

    declared_caps = set()
    for child in caps:
        name = child.get("Name")
        if name:
            declared_caps.add(name)

    # Expected: runFullTrust, internetClient, microphone
    expected = {"runFullTrust", "internetClient", "microphone"}
    assert declared_caps == expected, f"Unexpected or missing capabilities: {declared_caps} vs {expected}"
