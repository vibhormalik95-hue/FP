import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl.data import load_data
from feedctrl.model import train_model
from scripts.output_safety import project_path, require_new_output


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', default='data/processed.json')
    p.add_argument('--output', default='results/reproduction-training', help='New model directory; existing/frozen outputs are refused')
    p.add_argument('--seeds', type=int, nargs='+', default=[42, 43, 44])
    p.add_argument('--epochs', type=int, default=3)
    p.add_argument('--device', default='cpu')
    p.add_argument('--max-len', type=int, default=50)
    p.add_argument('--hidden-dim', type=int, default=32)
    p.add_argument('--batch-size', type=int, default=64)
    args = p.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        p.error('Seeds must be unique; duplicate seeds would overwrite a checkpoint')
    try:
        output = require_new_output(args.output, ROOT, directory=True)
    except ValueError as exc:
        p.error(str(exc))
    data = load_data(project_path(args.data, ROOT))
    for seed in args.seeds:
        metadata = train_model(data, output / f'seed_{seed}', seed=seed, epochs=args.epochs,
                               device=args.device, max_len=args.max_len, hidden_dim=args.hidden_dim,
                               batch_size=args.batch_size)
        print(json.dumps(metadata, indent=2))

if __name__ == '__main__':
    main()
