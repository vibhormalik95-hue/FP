"""Download/check the official archive or generate an explicitly synthetic fixture."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl.data import make_fixture, preprocess_kuairec, save_data
from scripts.output_safety import project_path, require_new_output


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='results/reproduction-data/processed.json', help='New data file; existing/frozen outputs are refused')
    p.add_argument('--archive', default='data/raw/KuaiRec.zip')
    p.add_argument('--max-users', type=int, default=256, help='0 uses all eligible users')
    p.add_argument('--cohort-seed', type=int, default=42)
    p.add_argument('--fixture', action='store_true')
    args = p.parse_args()
    try:
        output = require_new_output(args.output, ROOT, directory=False)
        archive = project_path(args.archive, ROOT)
        if output == archive:
            raise ValueError('Data output and raw archive must use different paths')
    except ValueError as exc:
        p.error(str(exc))
    if args.fixture:
        data = make_fixture()
        save_data(data, output)
    else:
        data = preprocess_kuairec(archive, output, args.max_users, args.cohort_seed)
    print(json.dumps(data['metadata'], indent=2))

if __name__ == '__main__':
    main()
