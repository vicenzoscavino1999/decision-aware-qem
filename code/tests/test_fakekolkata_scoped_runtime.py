"""Regressions for isolated FakeKolkata runtime settings and early validation."""
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import numpy as np
import pytest

import run_fakekolkata_v21 as fk


def test_import_does_not_modify_shared_rng_threads_or_environment(monkeypatch):
    sampling_rng = lambda **kwargs: None
    calibration_rng = lambda **kwargs: None
    monkeypatch.setattr(fk.old, 'make_rng', sampling_rng)
    monkeypatch.setattr(fk.rem_module, 'make_rng', calibration_rng)
    monkeypatch.setattr(fk.old, 'AER_MAX_PARALLEL_THREADS', 7)
    monkeypatch.delenv('OMP_NUM_THREADS', raising=False)
    runpy.run_path(str(Path(fk.__file__)), run_name='fakekolkata_import_check')
    assert fk.old.make_rng is sampling_rng
    assert fk.rem_module.make_rng is calibration_rng
    assert fk.old.AER_MAX_PARALLEL_THREADS == 7
    assert 'OMP_NUM_THREADS' not in os.environ


def test_sampling_keeps_the_same_namespaced_stream_and_restores_functions():
    previous_rng, previous_calibration = fk.old.make_rng, fk.rem_module.make_rng
    identifiers = dict(instance_id='C001', method='Raw', budget=512,
                       replicate_id=17, stream='derisk_multinomial')
    expected = fk.make_rng(**{**identifiers, 'stream': fk.NAMESPACE + '|derisk_multinomial'})
    with fk._sampling_context():
        assert fk.old.make_rng is fk.fresh_rng
        assert fk.rem_module.make_rng is fk.fresh_rng
        np.testing.assert_array_equal(fk.old.make_rng(**identifiers).integers(0, 1000, 20),
                                      expected.integers(0, 1000, 20))
    assert fk.old.make_rng is previous_rng
    assert fk.rem_module.make_rng is previous_calibration


def test_analyze_restores_rngs_if_sampling_fails(monkeypatch):
    previous_rng, previous_calibration = fk.old.make_rng, fk.rem_module.make_rng
    def stop_during_sampling(*args, **kwargs):
        assert fk.old.make_rng is fk.fresh_rng
        assert fk.rem_module.make_rng is fk.fresh_rng
        raise RuntimeError('sampling stopped for regression test')
    monkeypatch.setattr(fk.old, '_primitive_samples', stop_during_sampling)
    with pytest.raises(RuntimeError, match='sampling stopped'):
        fk.analyze(SimpleNamespace(instance_id='C001'))
    assert fk.old.make_rng is previous_rng
    assert fk.rem_module.make_rng is previous_calibration


def test_simulation_thread_setting_is_restored_on_error(monkeypatch):
    monkeypatch.setattr(fk.old, 'AER_MAX_PARALLEL_THREADS', 9)
    with pytest.raises(RuntimeError, match='stop'):
        with fk._simulation_context():
            assert fk.old.AER_MAX_PARALLEL_THREADS == 4
            raise RuntimeError('stop')
    assert fk.old.AER_MAX_PARALLEL_THREADS == 9


def _protocol():
    return {'fakekolkata': {'budget': 512, 'fit_reps': 10, 'selection_reps': 10,
                           'test_reps': 20, 'menu': list(fk.METHODS),
                           'seed_namespace': fk.NAMESPACE}}


@pytest.mark.parametrize('problem', ['missing', 'invalid_json', 'wrong_budget', 'wrong_namespace'])
def test_protocol_error_stops_before_backend_or_output(tmp_path, monkeypatch, problem):
    code = tmp_path / 'code'
    code.mkdir()
    monkeypatch.setattr(fk, 'ROOT', code)
    protocol_path = tmp_path / 'protocol.json'
    protocol = _protocol()
    if problem == 'invalid_json':
        protocol_path.write_text('{invalid', encoding='utf-8')
    elif problem != 'missing':
        key = 'budget' if problem == 'wrong_budget' else 'seed_namespace'
        protocol['fakekolkata'][key] = 1024 if problem == 'wrong_budget' else 'different-stream'
        protocol_path.write_text(json.dumps(protocol), encoding='utf-8')
    def forbidden_backend():
        raise AssertionError('The backend must not be initialized for an invalid protocol')
    monkeypatch.setattr(fk, 'FakeKolkataV2', forbidden_backend)
    output = tmp_path / 'never-created'
    monkeypatch.setattr(sys, 'argv', ['run_fakekolkata_v21.py', '--instances', 'C001', '--output', str(output)])
    with pytest.raises((FileNotFoundError, ValueError)):
        fk.main()
    assert not output.exists()


def test_matching_protocol_is_accepted_without_computation(tmp_path, monkeypatch):
    code = tmp_path / 'code'
    code.mkdir()
    monkeypatch.setattr(fk, 'ROOT', code)
    protocol = _protocol()
    (tmp_path / 'protocol.json').write_text(json.dumps(protocol), encoding='utf-8')
    assert fk._validate_protocol() == protocol
