"""Verify the manuscript's readout example using exact rational arithmetic.

Run with Python 3; no third-party packages, simulator, network or input data.
Only an explicitly requested --output file is written.
"""
import argparse
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path


def verify():
    outcomes = list(product((-1, 1), repeat=3))
    observed = [(F(3, 10), F(1, 20)), (F(1, 10), F(3, 10))]
    models = {'A': (F(4, 5), F(1), F(1, 2)),
              'B': (F(2, 5), F(1), F(4, 5))}
    expected_energies = {'A': [F(19, 40), F(29, 40)],
                         'B': [F(13, 16), F(5, 8)]}
    laws, report = {}, {}
    for name, attenuation in models.items():
        # Construct the full stochastic response matrix on the eight bitstrings.
        channel = {}
        for z in outcomes:
            for y in outcomes:
                prob = F(1)
                for j in range(3):
                    prob *= (1 + attenuation[j] * z[j] * y[j]) / 2
                channel[y, z] = prob
            assert sum(channel[y, z] for y in outcomes) == 1
            assert all(channel[y, z] >= 0 for y in outcomes)

        laws[name], energies, candidate_records = [], [], []
        for u, v in observed:
            state = {
                z: ((1 + (u / attenuation[0]) * z[0]) *
                    (1 + (v / attenuation[2]) * z[2]) / 4
                    if z[1] == 1 else F(0))
                for z in outcomes
            }
            assert sum(state.values()) == 1
            assert all(p >= 0 for p in state.values())
            energy = sum(p * (z[0]*z[1] + z[1]*z[2]) for z, p in state.items())
            measured = {y: sum(channel[y, z]*state[z] for z in outcomes) for y in outcomes}
            expected = {y: ((1 + u*y[0])*(1 + v*y[2])/4 if y[1] == 1 else F(0))
                        for y in outcomes}
            assert measured == expected
            assert sum(measured.values()) == 1
            assert sum(p*y[0]*y[1] for y, p in measured.items()) == u
            assert sum(p*y[1]*y[2] for y, p in measured.items()) == v
            eta = attenuation[0] / attenuation[2]
            assert energy == (u + eta*v) / (attenuation[0]*attenuation[1])
            laws[name].append(measured)
            energies.append(energy)
            candidate_records.append({'ideal_energy_exact': str(energy),
                                      'ideal_energy_decimal': float(energy),
                                      'target_record_law': {str(y): str(p) for y, p in measured.items()}})
        assert energies == expected_energies[name]
        assert energies[0] != energies[1]
        reference = {y: channel[y, (1, 1, 1)] for y in outcomes}
        parity01 = sum(p*y[0]*y[1] for y, p in reference.items())
        parity12 = sum(p*y[1]*y[2] for y, p in reference.items())
        assert parity01 == attenuation[0]*attenuation[1]
        assert parity12 == attenuation[1]*attenuation[2]
        assert parity01/parity12 == attenuation[0]/attenuation[2]
        report[name] = {'attenuations': list(map(str, attenuation)),
                        'candidates': candidate_records,
                        'unique_argmin': min(range(2), key=lambda i: energies[i]),
                        'ideal_gap_exact': str(energies[1]-energies[0]),
                        'calibration_parity_means': [str(parity01), str(parity12)],
                        'relative_weight_eta': str(parity01/parity12)}
    assert laws['A'] == laws['B']
    assert report['A']['unique_argmin'] == 0 and report['B']['unique_argmin'] == 1
    assert report['A']['calibration_parity_means'] != report['B']['calibration_parity_means']
    return {'status': 'PASS', 'arithmetic': 'exact rational (fractions.Fraction)',
            'complete_target_laws_identical': True,
            'opposite_unique_ideal_minimizers': True,
            'calibration_reference_laws_distinguishable': True,
            'worst_model_error_lower_bound': '1/2',
            'bound_reason': 'Identical record laws give one common output probability q for x0; errors are 1-q and q.',
            'models': report}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify()
    serialized = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(serialized, encoding='utf-8')
    print(serialized)
