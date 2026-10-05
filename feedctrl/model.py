"""Compact, independently implemented SASRec architecture with sampled logistic loss.

Reference: Kang & McAuley, ICDM 2018, https://arxiv.org/abs/1808.09781.
This is a research implementation, not a claim of exact original benchmark reproduction.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError('SASRec requires PyTorch; install requirements. No silent substitute is used.') from exc
    return torch


def _build_network(item_count, max_len=50, hidden_dim=32, layers=2, heads=1, dropout=.2):
    torch = _torch()
    nn = torch.nn
    if hidden_dim % heads:
        raise ValueError('hidden_dim must be divisible by heads')

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm_attention = nn.LayerNorm(hidden_dim, eps=1e-8)
            self.norm_ff = nn.LayerNorm(hidden_dim, eps=1e-8)
            self.q = nn.Linear(hidden_dim, hidden_dim)
            self.k = nn.Linear(hidden_dim, hidden_dim)
            self.v = nn.Linear(hidden_dim, hidden_dim)
            self.attention_out = nn.Linear(hidden_dim, hidden_dim)
            self.ff1 = nn.Linear(hidden_dim, hidden_dim)
            self.ff2 = nn.Linear(hidden_dim, hidden_dim)
            self.drop = nn.Dropout(dropout)

        def forward(self, x, valid):
            batch, length, width = x.shape
            query_input = self.norm_attention(x)
            def split(tensor):
                return tensor.reshape(batch, length, heads, width // heads).transpose(1, 2)
            q, k, v = split(self.q(query_input)), split(self.k(x)), split(self.v(x))
            logits = q @ k.transpose(-2, -1) / math.sqrt(width // heads)
            causal = torch.ones(length, length, dtype=torch.bool, device=x.device).tril()
            allowed = causal[None, None] & valid[:, None, None, :]
            # Padding queries attend themselves to avoid all-masked NaNs; erased below.
            diagonal = torch.eye(length, dtype=torch.bool, device=x.device)[None, None]
            allowed = allowed | ((~valid)[:, None, :, None] & diagonal)
            weights = torch.softmax(logits.masked_fill(~allowed, float('-inf')), dim=-1)
            attended = (self.drop(weights) @ v).transpose(1, 2).reshape(batch, length, width)
            x = query_input + self.drop(self.attention_out(attended))
            z = self.norm_ff(x)
            x = z + self.drop(self.ff2(self.drop(torch.relu(self.ff1(z)))))
            return x * valid.unsqueeze(-1)

    class SASRec(nn.Module):
        def __init__(self):
            super().__init__()
            self.item_embedding = nn.Embedding(item_count + 1, hidden_dim, padding_idx=0)
            self.position_embedding = nn.Embedding(max_len, hidden_dim)
            self.dropout = nn.Dropout(dropout)
            self.blocks = nn.ModuleList([Block() for _ in range(layers)])
            self.final_norm = nn.LayerNorm(hidden_dim, eps=1e-8)
            nn.init.normal_(self.item_embedding.weight, std=.02)
            nn.init.normal_(self.position_embedding.weight, std=.02)
            with torch.no_grad():
                self.item_embedding.weight[0].zero_()

        def forward(self, tokens):
            valid = tokens != 0
            positions = torch.arange(tokens.shape[1], device=tokens.device)
            x = self.item_embedding(tokens) * math.sqrt(hidden_dim) + self.position_embedding(positions)[None]
            x = self.dropout(x) * valid.unsqueeze(-1)
            for block in self.blocks:
                x = block(x, valid)
            return self.final_norm(x) * valid.unsqueeze(-1)

    return SASRec()


def _training_examples(data, mapping, max_len):
    """Chunk every train transition once; no request or test items are read."""
    examples = []
    for user in data['users']:
        sequence = [mapping[i] for i in user['train']]
        known = frozenset(sequence)
        for start in range(0, len(sequence) - 1, max_len):
            inputs = sequence[start:start + max_len]
            targets = sequence[start + 1:start + max_len + 1]
            inputs = inputs[:len(targets)]
            if not targets:
                continue
            padding = max_len - len(targets)
            examples.append(([0] * padding + inputs, [0] * padding + targets, known))
    return examples


def train_model(data, output_dir, seed=42, epochs=3, max_len=50, hidden_dim=32,
                layers=2, heads=1, dropout=.2, batch_size=64, learning_rate=.001,
                device='cpu', num_threads=2, **kwargs):
    """Fit one frozen backbone. Hyperparameters are fixed before examining test results."""
    from feedctrl.data import validate_data
    validate_data(data)
    if kwargs:
        raise TypeError(f'Unknown training options: {sorted(kwargs)}')
    if epochs < 1 or max_len < 2 or hidden_dim < 2 or layers < 1 or heads < 1 or batch_size < 1:
        raise ValueError('Invalid training dimensions')
    if not 0 <= dropout < 1 or learning_rate <= 0:
        raise ValueError('Invalid dropout or learning rate')
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    torch = _torch()
    torch.set_num_threads(num_threads)
    torch.manual_seed(seed)
    random.seed(seed)
    torch.use_deterministic_algorithms(True)
    if device.startswith('cuda') and not torch.cuda.is_available():
        raise RuntimeError('CUDA was requested but is unavailable')
    mapping = {i: j + 1 for j, i in enumerate(sorted(x['item_id'] for x in data['items']))}
    config = dict(item_count=len(mapping), max_len=max_len, hidden_dim=hidden_dim, layers=layers,
                  heads=heads, dropout=dropout)
    model = _build_network(**config).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, betas=(.9, .98))
    examples = _training_examples(data, mapping, max_len)
    # Negative pools use only training positives. Held-out positives are never excluded.
    catalogue = set(mapping.values())
    pools = {known: sorted(catalogue - known) for _, _, known in examples}
    examples = [e for e in examples if pools[e[2]]]
    if not examples:
        raise ValueError('No usable training examples with unobserved training negatives')
    rng = random.Random(seed)
    losses = []
    start = time.perf_counter()
    model.train()
    for epoch in range(epochs):
        order = list(range(len(examples)))
        rng.shuffle(order)
        total_loss, total_positions = 0.0, 0
        for index in range(0, len(order), batch_size):
            batch = [examples[j] for j in order[index:index + batch_size]]
            tokens = torch.tensor([e[0] for e in batch], dtype=torch.long, device=device)
            targets = torch.tensor([e[1] for e in batch], dtype=torch.long, device=device)
            negatives = torch.tensor([[rng.choice(pools[e[2]]) if t else 0 for t in e[1]] for e in batch],
                                     dtype=torch.long, device=device)
            hidden = model(tokens)
            mask = targets != 0
            positive_logits = (hidden * model.item_embedding(targets)).sum(-1)[mask]
            negative_logits = (hidden * model.item_embedding(negatives)).sum(-1)[mask]
            loss = (torch.nn.functional.softplus(-positive_logits) + torch.nn.functional.softplus(negative_logits)).mean()
            if not torch.isfinite(loss):
                raise RuntimeError('Nonfinite SASRec training loss')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            count = int(mask.sum())
            total_loss += float(loss.detach()) * count
            total_positions += count
        mean = total_loss / total_positions
        losses.append(mean)
        print(f'SASRec seed={seed} epoch={epoch + 1}/{epochs} train_loss={mean:.6f}', flush=True)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {'config': config, 'item_mapping': mapping, 'state_dict': model.cpu().state_dict()}
    torch.save(payload, output_dir / 'model.pt')
    train_payload = [{'user_id': u['user_id'], 'train': u['train']} for u in data['users']]
    train_hash = hashlib.sha256(json.dumps(train_payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    metadata = {
        'model': 'SASRec', 'implementation': 'independent PyTorch causal self-attention + pointwise FFN; sampled logistic loss',
        'reference': 'https://arxiv.org/abs/1808.09781', 'seed': seed, 'epochs': epochs,
        'config': config, 'batch_size': batch_size, 'learning_rate': learning_rate,
        'negative_sampling': 'one uniform negative per valid timestep; excludes user train positives only',
        'loss_by_epoch': losses, 'training_chunks': len(examples), 'train_sequence_sha256': train_hash,
        'training_transitions': sum(sum(t != 0 for t in e[1]) for e in examples),
        'device': device, 'torch_version': torch.__version__, 'num_threads': num_threads,
        'wall_seconds': time.perf_counter() - start, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'dataset_kind': data['metadata'].get('kind'),
        'status': 'fixed-epoch exploratory backbone; no hyperparameter tuning or convergence claim',
        'checkpoint_sha256': hashlib.sha256((output_dir / 'model.pt').read_bytes()).hexdigest(),
        'training_scope': 'train only; neither request_history nor test used for gradients or negative exclusion',
    }
    (output_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


class SASRecPredictor:
    def __init__(self, payload, metadata=None):
        self.torch = _torch()
        self.mapping = {int(k): int(v) for k, v in payload['item_mapping'].items()}
        self.config = payload['config']
        self.model = _build_network(**self.config)
        self.model.load_state_dict(payload['state_dict'])
        self.model.eval()
        self.metadata = metadata or {}

    def score(self, history, item_ids):
        if not item_ids:
            return []
        if any(i not in self.mapping for i in item_ids):
            raise ValueError('Candidate contains item outside model catalogue')
        if any(i not in self.mapping for i in history):
            raise ValueError('History contains item outside model catalogue')
        if not history:
            raise ValueError('SASRec needs at least one historical item')
        sequence = [self.mapping[i] for i in history[-self.config['max_len']:]]
        tokens = [0] * (self.config['max_len'] - len(sequence)) + sequence
        with self.torch.no_grad():
            hidden = self.model(self.torch.tensor([tokens], dtype=self.torch.long))[0, -1]
            candidates = self.torch.tensor([self.mapping[i] for i in item_ids], dtype=self.torch.long)
            scores = self.model.item_embedding(candidates) @ hidden
        result = scores.tolist()
        if not all(math.isfinite(s) for s in result):
            raise RuntimeError('Nonfinite model scores')
        return result


def load_model(output_dir):
    output_dir = Path(output_dir)
    torch = _torch()
    metadata_path = output_dir / 'metadata.json'
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    expected = metadata.get('checkpoint_sha256')
    if expected and hashlib.sha256((output_dir / 'model.pt').read_bytes()).hexdigest() != expected:
        raise ValueError('Checkpoint checksum mismatch; model and provenance do not match')
    # weights_only rejects arbitrary pickle globals; only our tensors/primitives are loaded.
    payload = torch.load(output_dir / 'model.pt', map_location='cpu', weights_only=True)
    torch.set_num_threads(int(metadata.get('num_threads', 2)))
    return SASRecPredictor(payload, metadata)


class FixturePredictor:
    """Transparent non-SASRec fixture scorer for UI/tests when no checkpoint is available."""
    metadata = {'model': 'deterministic fixture scorer', 'status': 'software demo, not research evidence'}
    def score(self, history, item_ids):
        counts = Counter(history)
        return [float(counts[i]) + 1 / (1 + int(i)) for i in item_ids]
