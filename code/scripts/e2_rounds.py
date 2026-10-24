"""Reproduce one E2 instance with durable, verified per-round shot records.

The scientific implementation is in the adjacent code/ directory.
This runner handles orchestration, persistence and validation. It compares the
old and corrected decisions on the same samples and checks the old results
against the historical archive. Default execution is a one-trajectory benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time

PACKAGE = Path(__file__).resolve().parent


def generation_identity(corrected, config, versions, threads, blas_threads):
    """Fingerprint measurements separately from the downstream ZNE analysis.

    Reused rounds must still match their newly generated candidate angles exactly.
    A change to the simulator, graph, seeds or proposal helpers invalidates data;
    changing the decision rule alone can be replayed without new Aer jobs.
    """
    import daqem.candidates as candidates
    import daqem.dynamic as dynamic
    import daqem.noise as noise
    import daqem.qaoa as qaoa
    import daqem.rng as rng
    from daqem.decisions import integer_shot_sums
    fields = ['qubits','graph_degree','depth','zne_lambdas','budget_grid','B_max',
              'max_rounds','candidates_per_round','candidate_radius','initial_landscape_count',
              'local_radius','search_radius','search_count','instance_ids','proposal_update_reference']
    helpers = [corrected._evaluate_candidate_batch, corrected._prefix_objective_stats,
               corrected._trajectory_initial_angles, corrected._candidate_ideal_values,
               dynamic.generate_candidate_batch, integer_shot_sums]
    return {'schema':'e2-measurements-v2', 'config':{k:config[k] for k in fields},
            'raw_proposal_rule':'first minimum of integer Raw shot sums at B_max',
            'noise_probabilities':[noise.ONE_QUBIT_DEPOLARIZING,noise.TWO_QUBIT_DEPOLARIZING],
            'random_stream':[rng.ROOT_SEED,rng.BIT_GENERATOR],
            'threads':threads, 'blas_threads':blas_threads, 'python':platform.python_version(),
            'versions':versions, 'modules':{m.__name__:sha(m.__file__) for m in [candidates,noise,qaoa,rng]},
            'helpers':{f.__module__+'.'+f.__name__:hashlib.sha256(inspect.getsource(f).encode()).hexdigest() for f in helpers}}


from reproducibility.run_all import RunLock as OutputLock


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding='utf-8')
    tmp.replace(path)


class RoundStore:
    """A round is reusable only after its data and checksum have been committed."""

    def __init__(self, root, identity):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.identity = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        self.measurement_config = identity.get('config') if identity.get('schema') == 'e2-measurements-v2' else None
        identity_path = self.root / 'identity.json'
        if identity_path.exists():
            if json.loads(identity_path.read_text(encoding='utf-8')) != identity:
                raise RuntimeError('Checkpoint identity changed: use a new output directory.')
        elif any(self.root.iterdir()):
            raise RuntimeError('Nonempty checkpoint directory without an identity.')
        else:
            write_json(identity_path, identity)

    def paths(self, trajectory, round_id):
        stem = f't{trajectory:03d}_r{round_id:03d}'
        return self.root / (stem + '.npz'), self.root / (stem + '.json')

    def load(self, trajectory, round_id, angles, *, include_states=False):
        import numpy as np
        path, commit = self.paths(trajectory, round_id)
        if not commit.exists():
            return None
        metadata = json.loads(commit.read_text(encoding='utf-8'))
        if metadata['identity'] != self.identity or not path.exists() or sha(path) != metadata['sha256']:
            raise RuntimeError(f'Checkpoint integrity failure: {path}')
        with np.load(path, allow_pickle=False) as data:
            if (int(data['trajectory']), int(data['round'])) != (trajectory, round_id):
                raise RuntimeError('Checkpoint trajectory/round does not match.')
            np.testing.assert_array_equal(data['angles'], angles)
            means, variances = data['means'].copy(), data['variances'].copy()
            if means.shape != variances.shape or not np.isfinite(means).all() or not np.isfinite(variances).all():
                raise RuntimeError('Invalid checkpoint statistics.')
            cost = dict(zip(('aer_runs', 'circuits', 'shots'), map(int, data['cost'])))
            states = None
            if self.measurement_config is not None:
                cfg = self.measurement_config
                shape = (len(cfg['zne_lambdas']), cfg['candidates_per_round'], cfg['B_max'])
                states = data['shot_states'] if 'shot_states' in data else None
                if (states is None or states.shape != shape or states.dtype != np.uint16
                        or np.any(states >= 2**cfg['qubits'])):
                    raise RuntimeError('Invalid or missing original shot states')
                if means.shape != shape[:2] + (len(cfg['budget_grid']),):
                    raise RuntimeError('Unexpected primitive-statistics dimensions')
                expected = {'aer_runs':shape[0], 'circuits':shape[0]*shape[1], 'shots':int(np.prod(shape))}
                if cost != expected:
                    raise RuntimeError('Unexpected sampling cost')
        return (means, variances, cost, states) if include_states else (means, variances, cost)

    def save(self, trajectory, round_id, angles, means, variances, cost, shot_states=None):
        import numpy as np
        path, commit = self.paths(trajectory, round_id)
        tmp = path.with_name(path.name + '.tmp')
        with tmp.open('wb') as handle:
            extra = {} if shot_states is None else {'shot_states': shot_states}
            np.savez_compressed(handle, trajectory=trajectory, round=round_id,
                                angles=angles, means=means, variances=variances,
                                cost=[cost[k] for k in ('aer_runs', 'circuits', 'shots')], **extra)
        tmp.replace(path)
        write_json(commit, {'identity': self.identity, 'sha256': sha(path)})


def validate_shot_statistics(states, graph, budgets, means, variances):
    """Recalculate physical cut values using bit arithmetic, independently of
    the string decoder and prefix helper used by the scientific implementation.
    """
    import numpy as np
    basis = np.arange(2**graph.number_of_nodes(), dtype=np.uint64)
    cuts = np.zeros(len(basis), dtype=np.int64)
    for i,j in graph.edges():
        cuts += (((basis >> int(i)) ^ (basis >> int(j))) & 1).astype(np.int64)
    values = -cuts[states].astype(float)
    cumulative = np.cumsum(values, axis=-1)
    expected_means = np.stack([cumulative[:,:,b-1]/b for b in budgets],axis=-1)
    expected_var = np.stack([np.var(values[:,:,:b],axis=-1,ddof=1)/b if b>1 else
                             np.zeros(values.shape[:2]) for b in budgets],axis=-1)
    np.testing.assert_array_equal(means, expected_means)
    np.testing.assert_array_equal(variances, expected_var)

