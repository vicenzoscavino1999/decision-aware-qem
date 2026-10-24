"""Explicit-graph primitive simulation for the auxiliary noise controls."""
from pathlib import Path

import numpy as np
from qiskit import transpile
from qiskit_aer import AerSimulator

from daqem.candidates import build_candidate_landscape_for_graph, maxcut_values_for_graph
from daqem.qaoa import qaoa_maxcut_circuit


def validate_layout(graph, gate0_config):
    n=gate0_config['qubits']
    if int(n)!=n or set(graph.nodes)!=set(range(int(n))):
        raise ValueError('graph nodes must match the configured qubit labels 0..n-1')
    if any(degree!=gate0_config['graph_degree'] for _,degree in graph.degree):
        raise ValueError('graph degree differs from the configured cell')
    if list(gate0_config['zne_lambdas'])!=[1.,2.,3.] or gate0_config['zne_order']!=1:
        raise ValueError('auxiliary controls require scales [1,2,3] and order one')
    for key in ('depth','candidate_count','search_count'):
        value=gate0_config[key]
        if int(value)!=value or value<1:
            raise ValueError(f'{key} must be a positive integer')
    budgets=gate0_config['budget_grid']
    if not budgets or len(set(budgets))!=len(budgets) or any(int(b)!=b or b<=0 for b in budgets):
        raise ValueError('budgets must be distinct positive integer primitive shot counts')


def full_probability_vector(values, state_count):
    arr=np.asarray(values,dtype=float)
    if arr.shape!=(state_count,) or not np.isfinite(arr).all() or np.any(arr < -1e-14):
        raise ValueError('invalid full probability vector')
    if abs(float(arr.sum())-1.)>1e-12:
        raise ValueError('probability mass was lost before normalization')
    arr=np.maximum(arr,0.)
    return arr/arr.sum()


def simulate_primitives(*, instance_id, graph, gate0_config, noise_model_factory):
    """Use the supplied graph throughout, without changing A3 module globals."""
    validate_layout(graph,gate0_config)
    depth=int(gate0_config['depth'])
    landscape=build_candidate_landscape_for_graph(instance_id,graph,
        candidate_count=int(gate0_config['candidate_count']),depth=depth,
        local_radius=float(gate0_config['local_radius']),search_radius=float(gate0_config['search_radius']),
        search_count=int(gate0_config['search_count']))
    values=-maxcut_values_for_graph(graph)
    scales=np.asarray(gate0_config['zne_lambdas'],dtype=float)
    probabilities=np.empty((len(scales),len(landscape.angles),len(values)))
    for scale_index,scale in enumerate(scales):
        simulator=AerSimulator(method='density_matrix',noise_model=noise_model_factory(scale_index,float(scale)),
            max_parallel_threads=1,max_parallel_experiments=1)
        circuits=[]
        for angles in landscape.angles:
            circuit=qaoa_maxcut_circuit(graph,depth=depth,gammas=angles[:depth],betas=angles[depth:],measure=False)
            circuit.save_probabilities()
            circuits.append(circuit)
        circuits=transpile(circuits,simulator,seed_transpiler=260616+scale_index)
        result=simulator.run(circuits).result()
        for j in range(len(circuits)):
            probabilities[scale_index,j]=full_probability_vector(result.data(j)['probabilities'],len(values))
    means=probabilities @ values
    variances=np.sum(probabilities*(values-means[...,None])**2,axis=-1)
    return dict(probabilities=probabilities,values_by_state=values,means=means,variances=variances,
        ideal_values=landscape.ideal_values,x_star=int(landscape.x_star),angles=landscape.angles,
        graph_edges=np.asarray(sorted(tuple(sorted(edge)) for edge in graph.edges()),dtype=int),scales=scales)


def write_primitive_evidence(data, output_dir: Path, instance_id: str):
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output_dir/f'{instance_id}.npz',**data)


def evaluation_shot_counts(budget, candidate_count):
    """R1's historical B is per candidate AND per scale; ZNE uses 3B."""
    if int(budget)!=budget or budget<=0:
        raise ValueError('budget must be a positive integer')
    return {'per_candidate':{'Raw':int(budget),'Accuracy-ZNE':3*int(budget),'Decision-ZNE':3*int(budget)},
            'all_candidates':{'Raw':int(candidate_count)*int(budget),
                'Accuracy-ZNE':3*int(candidate_count)*int(budget),'Decision-ZNE':3*int(candidate_count)*int(budget)}}
