"""Recompute the pins of this validation profile after a reviewed source change.

Run from the repository root:

    python tools/hosted_validation_current/refresh_pins.py NEW-PROFILE-ID "what changed"

It rewrites, in this order: the pinned first category request (only its system
prompt, taken from the code), the input manifest, the manifest hash and profile
identifier in driver.py, and the driver, manifest, profile and source pins in
both configuration templates. It then records the change in
PROFILE-PROVENANCE.json. It never sets an execution gate, never fills in a
path, token or price, and never runs a model. The templates stay incomplete.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def main():
    if len(sys.argv) != 3 or not re.fullmatch(r'[a-z0-9-]{8,80}', sys.argv[1]) or not sys.argv[2].strip():
        raise SystemExit(__doc__)
    profile, change = sys.argv[1], sys.argv[2].strip()
    from feedctrl.staged_induction import DEFINITION_PROMPT, DEFINITION_SCHEMA, MEMBERSHIP_PROMPT

    first_path = HERE / 'inputs' / '01-category-discovery' / 'first-model-input.json'
    first = json.loads(first_path.read_text(encoding='utf-8'))
    previous_first = sha(first_path)
    first['payload']['system'] = DEFINITION_PROMPT
    if first['schema'] != DEFINITION_SCHEMA:
        raise SystemExit('The response schema changed; review the pinned request by hand')
    first_path.write_bytes(canonical(first))

    manifest_path = HERE / 'inputs' / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for name in manifest:
        target = HERE / 'inputs' / name
        manifest[name] = {'sha256': sha(target), 'bytes': target.stat().st_size}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    manifest_sha = sha(manifest_path)

    driver_path = HERE / 'driver.py'
    driver = driver_path.read_text(encoding='utf-8')
    previous_profile = re.search(r"^PROFILE_ID = '([^']+)'", driver, re.M).group(1)
    driver, a = re.subn(r"^INPUT_MANIFEST_SHA256 = '[0-9a-f]{64}'", f"INPUT_MANIFEST_SHA256 = '{manifest_sha}'", driver, flags=re.M)
    driver, b = re.subn(r"^PROFILE_ID = '[^']+'", f"PROFILE_ID = '{profile}'", driver, flags=re.M)
    if (a, b) != (1, 1):
        raise SystemExit('driver.py constants not found')
    driver_path.write_text(driver, encoding='utf-8')
    driver_sha = sha(driver_path)

    sources = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / 'feedctrl').glob('*.py'))}
    for name in ('reviewed-config.TEMPLATE.json', 'reviewed-indirect-config.TEMPLATE.json'):
        path = HERE / name
        config = json.loads(path.read_text(encoding='utf-8'))
        config.update(driver_sha256=driver_sha, input_manifest_sha256=manifest_sha,
                      profile_id=profile, source_sha256=sources)
        path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')

    provenance_path = HERE / 'PROFILE-PROVENANCE.json'
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    provenance.update({
        'profile_id': profile, 'previous_profile_id': previous_profile,
        'previous_first_request_sha256': previous_first,
        'current_first_request_sha256': sha(first_path), 'current_manifest_sha256': manifest_sha,
        'membership_prompt_utf8_sha256': hashlib.sha256(MEMBERSHIP_PROMPT.encode('utf-8')).hexdigest(),
        'sole_model_input_delta': change,
        'authorization': 'INCOMPLETE FALSE-GATED TEMPLATE. No fresh hosted batch authorized.',
    })
    provenance_path.write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'profile_id': profile, 'input_manifest_sha256': manifest_sha,
                      'driver_sha256': driver_sha, 'first_request_sha256': sha(first_path),
                      'source_files_pinned': len(sources)}, indent=2))


if __name__ == '__main__':
    main()
