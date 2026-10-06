"""Check final ZIP contents, hashes, portable Data location and packaged GUI workflows."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
archive = ROOT / "Builds/Windows/Translation-Studio-Windows-Portable.zip"
destination = Path(tempfile.mkdtemp(prefix="portable-zip-", dir=ROOT / "Work/QA"))
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    for name in bundle.namelist():
        path = Path(name)
        assert not path.is_absolute() and ".." not in path.parts
        assert not any(part in ("Data", "Work", "Internal", "__pycache__") for part in path.parts)
        assert path.name not in {"DevelopmentPlan.md", "ImplementationPlan.md", "Specification.md",
                                 "UsabilityPlan.md", "FederationForceIntegration.md", "Verification.md"}
    bundle.extractall(destination)
package = destination / "Translation Studio"
for line in (package / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
    expected, relative = line.split("  ", 1)
    assert hashlib.sha256((package / relative).read_bytes()).hexdigest() == expected, relative
subprocess.run([sys.executable, str(ROOT / "Scripts/verify_package.py"), "--package", str(package),
                "--portable-profile"], cwd=ROOT, check=True)
result = {"ok": True, "archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
          "sizeBytes": archive.stat().st_size, "extractedPackage": str(package)}
(ROOT / "Work/QA/archive-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
