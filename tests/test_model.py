import copy
import math
import pytest
pytest.importorskip('torch')
import torch
from feedctrl.data import make_fixture
from feedctrl.model import _build_network, _training_examples, train_model, load_model, FixturePredictor


def test_causal_attention_cannot_see_future():
    torch.manual_seed(42)
    model = _build_network(20, max_len=8, hidden_dim=8, layers=2, dropout=0)
    model.eval()
    first = torch.tensor([[0, 0, 1, 2, 3, 4, 5, 6]])
    altered = torch.tensor([[0, 0, 1, 2, 3, 15, 16, 17]])
    with torch.no_grad():
        a, b = model(first), model(altered)
    assert torch.isfinite(a).all()
    assert torch.equal(a[:, :5], b[:, :5])
    assert torch.equal(a[:, :2], torch.zeros_like(a[:, :2]))


def test_training_examples_ignore_heldout():
    original = make_fixture()
    modified = copy.deepcopy(original)
    for u in modified['users']:
        u['request_history'] = list(reversed(u['request_history']))
        u['test'] = [2, 3, 4]
    mapping = {i['item_id']: idx + 1 for idx, i in enumerate(original['items'])}
    assert _training_examples(original, mapping, 10) == _training_examples(modified, mapping, 10)


def test_checkpoint_replay_and_train_only_fit(tmp_path):
    original = make_fixture(n_users=4, n_items=30)
    altered = copy.deepcopy(original)
    for user in altered['users']:
        user['test'] = [30, 29, 28]
        user['request_history'] = [27, 26]
    a = train_model(original, tmp_path / 'a', seed=8, epochs=1, hidden_dim=8, max_len=10, dropout=0)
    b = train_model(altered, tmp_path / 'b', seed=8, epochs=1, hidden_dim=8, max_len=10, dropout=0)
    first, second = load_model(tmp_path / 'a'), load_model(tmp_path / 'b')
    scores = first.score([1, 2, 3], [1, 2, 3, 4])
    assert scores == second.score([1, 2, 3], [1, 2, 3, 4])
    assert a['train_sequence_sha256'] == b['train_sequence_sha256']
    assert a['loss_by_epoch'] == b['loss_by_epoch']
    assert all(math.isfinite(x) for x in scores)
    with pytest.raises(ValueError):
        first.score([1], [9999])
    assert scores == load_model(tmp_path / 'a').score([1, 2, 3], [1, 2, 3, 4])


def test_fixture_predictor_is_explicit():
    fixture = FixturePredictor()
    assert 'fixture' in fixture.metadata['model']
    assert fixture.score([1, 2, 1], [1, 2, 3])[0] > fixture.score([1, 2, 1], [1, 2, 3])[1]
