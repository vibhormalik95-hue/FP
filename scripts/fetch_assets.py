"""Download the KuaiRec assets the app needs, verify every SHA-256, and put them in place.

    python scripts/fetch_assets.py            (or fetch-assets.cmd / ./fetch-assets.sh)

The assets are published as a GitHub Release asset of this repository under CC BY-SA 4.0, with
the KuaiRec attribution (ATTRIBUTION.md inside the archive). They are written to the ignored
folders data/ and results/models/. A file whose hash differs is reported, kept, and the exit code
is 1, unless --force is given. Each write is atomic.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "https://github.com/vibhormalik95-hue/FP/releases/download/comp9500-kuairec-assets-v1/comp9500-kuairec-assets-v1.zip"
ARCHIVE_SHA256 = "fd8a158a91b06e86fb377b5821832df597a4285917b41cf56293d6326236d2b6"
FILES = {   # path inside the repository -> SHA-256
    "data/processed.json": "96e63b901198e05c60034858fd6f437c2172dbfd71c257818673204cc81cb13c",
    "data/raw/kuairec_caption_category.csv": "7ccf10f348da6041742222f107da32e1be8b1c8c7b710d65963fa10d56a014f5",
    "data/kuairec_gloss_en.json": "44faf92121e75f22dd382f86dde132448ef3a4f0e006f97875de0430b1f2592f",
    "results/models/seed_42/model.pt": "ca74de406a94d2fdcd587c7d93b376eb95accabd25dc282feee07704091cfea0",
    "results/models/seed_42/metadata.json": "4ccf55d810be195f1a20e06307b27c24575d7234459075e00007e5197d58e92c",
    "results/models/seed_43/model.pt": "90cc82592c4c9dc3a8bc1abacf9a42181b20617a3af587bd4aafb0b492c2d667",
    "results/models/seed_43/metadata.json": "08823319f850e91f4c3120a3aa65cc12a9b272912bbb65a6de4601b01c45086b",
    "results/models/seed_44/model.pt": "a7a141e7e9496db8d6b1f738682358cda76e19236af83d8edeb58070233bc3b9",
    "results/models/seed_44/metadata.json": "f6a713bb248568d49bc4074ad131fc874eff9df31e84bee2ed1fcb936bf5529b",
    "data/ATTRIBUTION.md": "172435ae07758c26622ff274fb9674dce0c1920c6caf0deb79cb68437fe8338f",
}
INSIDE = {"data/ATTRIBUTION.md": "ATTRIBUTION.md"}


def download(url):
    """The system certificate store first; certifi's store if this Python cannot verify GitHub's certificate."""
    import ssl
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            return response.read()
    except urllib.error.URLError as exc:
        if not isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise
        try:
            import certifi
        except ImportError:
            raise exc from None
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(url, timeout=300, context=context) as response:
            return response.read()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=RELEASE)
    ap.add_argument("--archive", help="use a downloaded archive instead of the URL")
    ap.add_argument("--force", action="store_true", help="replace files whose hash differs")
    args = ap.parse_args(argv)
    if all((ROOT / p).is_file() and sha((ROOT / p).read_bytes()) == h for p, h in FILES.items()):
        print("All assets are present and verified. Nothing to do.")
        return 0
    if args.archive:
        blob = Path(args.archive).read_bytes()
    else:
        print(f"Downloading {args.url} ...", flush=True)
        try:
            blob = download(args.url)
        except OSError as exc:
            print(f"FAILED: could not download the archive ({exc}). Check the network and try again. Nothing was written.")
            return 1
    if sha(blob) != ARCHIVE_SHA256:
        print(f"FAILED: the archive SHA-256 is {sha(blob)}, expected {ARCHIVE_SHA256}. Nothing was written.")
        return 1
    print(f"Archive verified ({len(blob):,} bytes).")
    kept = 0
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for path, expected in FILES.items():
            data = archive.read("comp9500-kuairec-assets/" + INSIDE.get(path, path))
            if sha(data) != expected:
                print(f"FAILED: {path} has SHA-256 {sha(data)}, expected {expected}. Nothing more is written.")
                return 1
            target = ROOT / path
            if target.is_file() and sha(target.read_bytes()) == expected:
                print(f"ok      {path} (already present)")
                continue
            if target.is_file() and not args.force:
                print(f"KEPT    {path}: a different file is there; rerun with --force to replace it")
                kept += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".partial")
            partial.write_bytes(data)
            partial.replace(target)            # atomic: a file is either the old one or the verified new one
            print(f"written {path}")
        licence = archive.read("comp9500-kuairec-assets/LICENSE-CC-BY-SA-4.0.txt")
        (ROOT / "data").mkdir(exist_ok=True)
        licence_path = ROOT / "data" / "LICENSE-CC-BY-SA-4.0.txt"
        if not licence_path.is_file() or licence_path.read_bytes() != licence:
            licence_path.write_bytes(licence)
    if kept:
        print(f"{kept} file(s) differ from the published assets and were kept. Rerun with --force to replace them.")
        return 1
    print("Done. KuaiRec assets are CC BY-SA 4.0: see notices/KUAIREC-ASSETS-ATTRIBUTION.md. Start the app with run-app.cmd.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
