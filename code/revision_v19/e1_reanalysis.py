"""Retrospective E1 audit: three disjoint data splits and exact shot accounting.

Only archived cumulative means are consumed. No quantum jobs or new simulators.
Protocol is fixed in protocol.json before the first analysis run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd
from scipy.stats import multivariate_normal, norm
from sklearn.covariance import LedoitWolf
from daqem.decisions import zne_failures

HERE = Path(__file__).resolve().parent
METHODS = ("Raw", "Accuracy-ZNE", "Decision-ZNE")
POLICIES = (*METHODS, "MSE-selector", "GRI-selector")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_replicates(instance_id, count=40):
    if count != 40:
        raise ValueError("Protocol requires exactly 40 archived repetitions")
    ordered = sorted(range(count), key=lambda r: hashlib.sha256(
        f"v19-e1-independent-2026-10-22|{instance_id}|{r}".encode()).hexdigest())
    return {"fit": np.array(ordered[:10]), "select": np.array(ordered[10:20]),
            "test": np.array(ordered[20:])}


def block_mean(estimates, budgets, blocks):
    """Exactly recover means over a union of disjoint cumulative-shot blocks."""
    bounds = sorted(blocks)
    if any(lo < 0 or hi <= lo for lo, hi in bounds):
        raise ValueError("Invalid shot interval")
    if any(bounds[k][1] > bounds[k+1][0] for k in range(len(bounds)-1)):
        raise ValueError("Shot blocks overlap")
    lookup = {int(b): k for k, b in enumerate(budgets)}
    total = np.zeros(estimates.shape[:-1])
    shots = 0
    for lo, hi in bounds:
        total += hi * estimates[..., lookup[hi]]
        if lo:
            total -= lo * estimates[..., lookup[lo]]
        shots += hi-lo
    return total / shots


def gaps(values, optimum):
    keep = [k for k in range(values.shape[-1]) if k != optimum]
    return values[..., keep] - values[..., [optimum]]


def fit_coefficients(fit_primitives, ideal, optimum):
    """Fit only on training records; never receives select/test records."""
    A = np.array([[1., 1., 1.], [1., 2., 3.]])
    rhs = np.array([1., 0.])
    acc = np.array([4.,1.,-2.])/3
    primitive_gaps = gaps(fit_primitives, optimum)
    from daqem.qem_methods import decision_optimal_zne_coeffs
    reference = gaps(ideal, optimum)
    q_list = [np.cov(primitive_gaps[:, :, k], rowvar=False, ddof=1)
              for k in range(len(reference))]
    dc,diagnostics = decision_optimal_zne_coeffs(q_list, reference, A, rhs,return_diagnostics=True)
    # Store the one free parameter on the exactly specified Richardson line.
    t=float(dc[2]);dc=np.array([2+t,-1-2*t,t])
    return {"Accuracy-ZNE": acc, "Decision-ZNE": dc}, diagnostics


def risk_score(values, optimum, seed):
    from daqem.risk import gri_risk
    x = gaps(values, optimum)
    # A common scale preserves geometry and prevents absolute-unit thresholds.
    scale = float(np.max(np.abs(x)))
    if scale == 0:
        return 1.0
    x = x / scale
    return gri_risk(x.mean(axis=0), LedoitWolf().fit(x).covariance_, seed=seed)


def evaluate_methods(primitives, raw_values, coefficients):
    return {"Raw": raw_values,
            **{m: np.einsum("s,rsc->rc", coefficients[m], primitives)
               for m in ("Accuracy-ZNE", "Decision-ZNE")}}


def choose_methods(select_values, ideal, optimum, seed):
    scores = {m: {"mse": float(np.mean((v-ideal[None, :])**2)),
                  "gri": risk_score(v, optimum, seed)}
              for m, v in select_values.items()}
    choices = {"MSE-selector": min(METHODS, key=lambda m: (scores[m]["mse"], m)),
               "GRI-selector": min(METHODS, key=lambda m: (scores[m]["gri"], m))}
    return choices, scores


def budget_ledger(t, candidates, policy, comparison):
    fit = 30*t if policy in ("Decision-ZNE", "MSE-selector", "GRI-selector") else 0
    select = 60*t if policy.endswith("selector") else 0
    per_decision = 3*t
    if comparison == "end_to_end":
        if policy in ("Raw", "Accuracy-ZNE"):
            per_decision = 15*t//2
        elif policy == "Decision-ZNE":
            per_decision = 6*t
    evaluation = 20*per_decision
    return {"fit_shots": fit*candidates, "selection_shots": select*candidates,
            "evaluation_shots": evaluation*candidates,
            "total_shots_20_decisions": (fit+select+evaluation)*candidates,
            "evaluation_shots_per_decision": per_decision*candidates,
            "amortized_total_per_decision": (fit+select+evaluation)*candidates/20}


def analyse_instance(path, ts):
    with np.load(path, allow_pickle=False) as a:
        instance = str(a["instance_id"].item())
        estimates = np.array(a["primitive_objective_estimates"], dtype=float)
        budgets = np.array(a["budgets"], dtype=int)
        ideal = np.array(a["ideal_values"], dtype=float)
        optimum = int(a["x_star"])
    if estimates.shape[:3] != (40, 3, 25) or optimum != int(np.argmin(ideal)):
        raise ValueError(f"Unexpected input schema: {instance}")
    for k, b in enumerate(budgets):
        if not np.allclose(estimates[..., k]*b, np.round(estimates[..., k]*b), atol=1e-7, rtol=0):
            raise ValueError("Archived means are not integer MaxCut shot sums")
    split = split_replicates(instance)
    records, diagnostics, ledgers = [], [], []
    for t in ts:
        primitive = block_mean(estimates, budgets, [(0,t)])
        raw = block_mean(estimates, budgets, [(t,4*t)])[:, 0, :]
        coefficients, solver_status = fit_coefficients(primitive[split["fit"]], ideal, optimum)
        selection_values = evaluate_methods(primitive[split["select"]], raw[split["select"]], coefficients)
        seed = int.from_bytes(hashlib.sha256(f"v19-cdf|{instance}|{t}".encode()).digest()[:8], "little")
        choices, scores = choose_methods(selection_values, ideal, optimum, seed)
        # Only after choices are fixed do test arrays enter the calculation.
        test = split["test"]
        equal_eval = evaluate_methods(primitive[test], raw[test], coefficients)
        raw_full = block_mean(estimates, budgets, [(t//2,8*t)])[test, 0, :]
        acc_full = block_mean(estimates, budgets, [(t//2,t),(2*t,4*t)])[test]
        da_full = block_mean(estimates, budgets, [(0,2*t)])[test]
        full = {
            "Raw": raw_full,
            "Accuracy-ZNE": np.einsum("s,rsc->rc", coefficients["Accuracy-ZNE"], acc_full),
            "Decision-ZNE": np.einsum("s,rsc->rc", coefficients["Decision-ZNE"], da_full),
            **{p: equal_eval[m] for p,m in choices.items()}}
        equal_eval.update({p: equal_eval[m] for p,m in choices.items()})
        eval_fail={m:np.any(gaps(equal_eval[m],optimum)<=0,axis=1) for m in METHODS}
        eval_fail['Accuracy-ZNE']=zne_failures(primitive[test],optimum,t)
        eval_fail['Decision-ZNE']=zne_failures(primitive[test],optimum,t,coefficients=coefficients['Decision-ZNE'])
        full_fail={'Raw':np.any(gaps(full['Raw'],optimum)<=0,axis=1),
            'Accuracy-ZNE':zne_failures(acc_full,optimum,5*t//2),
            'Decision-ZNE':zne_failures(da_full,optimum,2*t,coefficients=coefficients['Decision-ZNE'])}
        for p,m in choices.items():
            full_fail[p]=eval_fail[m]
        eval_fail.update({p:eval_fail[m] for p,m in choices.items()})
        for comparison, values in (("evaluation", equal_eval),("end_to_end",full)):
            for policy in POLICIES:
                failure = (eval_fail if comparison=='evaluation' else full_fail)[policy]
                for rep, fail in zip(test, failure, strict=True):
                    records.append({"instance":instance,"base_t":t,"comparison":comparison,
                        "policy":policy,"replicate_id":int(rep),"failure":int(fail)})
                ledger = budget_ledger(t,len(ideal),policy,comparison)
                ledgers.append({"instance":instance,"base_t":t,"comparison":comparison,"policy":policy,**ledger})
        diagnostics.append({"instance":instance,"base_t":t,"solver_status":solver_status,
            "fit_ids":split["fit"].tolist(),"select_ids":split["select"].tolist(),
            "test_ids":test.tolist(),"coefficients":{k:v.tolist() for k,v in coefficients.items()},
            "scores":scores,"choices":choices})
    return records, diagnostics, ledgers


def summarize(outcomes):
    rows = []
    for (t,comparison), group in outcomes.groupby(["base_t","comparison"],sort=True):
        rates = group.groupby(["instance","policy"])["failure"].mean().unstack("policy").reindex(columns=POLICIES)
        draws = np.random.default_rng(20261022).integers(0,len(rates),(10000,len(rates)))
        bootstrap = rates.to_numpy()[draws].mean(axis=1)
        for p in POLICIES:
            k = POLICIES.index(p)
            lo, hi = np.quantile(bootstrap[:,k],[.025,.975])
            rows.append({"base_t":t,"comparison":comparison,"kind":"failure_rate","policy":p,
                "reference":"","estimate":float(rates[p].mean()),"ci_low":float(lo),"ci_high":float(hi)})
        for reference in ("Raw","MSE-selector","Accuracy-ZNE","Decision-ZNE"):
            k,j = POLICIES.index("GRI-selector"),POLICIES.index(reference)
            lo,hi=np.quantile(bootstrap[:,k]-bootstrap[:,j],[.025,.975])
            rows.append({"base_t":t,"comparison":comparison,"kind":"paired_difference",
                "policy":"GRI-selector","reference":reference,
                "estimate":float((rates["GRI-selector"]-rates[reference]).mean()),
                "ci_low":float(lo),"ci_high":float(hi)})
    return pd.DataFrame(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--raw",type=Path,default=HERE.parent/"reproducibility/reference_confirmatory/raw")
    parser.add_argument("--output",type=Path,default=HERE/"results")
    args=parser.parse_args()
    protocol=json.loads((HERE/"protocol.json").read_text(encoding="utf-8"))
    paths=[args.raw/f"C{i:03d}.npz" for i in range(1,49)]
    args.output.mkdir(parents=True,exist_ok=True)
    manifest={"protocol_sha256":sha256(HERE/"protocol.json"),"script_sha256":sha256(__file__),
        "input_sha256":{p.name:sha256(p) for p in paths},
        "versions":{p:importlib.metadata.version(p) for p in ("numpy","scipy","pandas","cvxpy","scikit-learn")}}
    records,diagnostics,ledgers=[],[],[]
    for path in paths:
        r,d,l=analyse_instance(path,protocol["base_shots_per_scale"])
        records.extend(r);diagnostics.extend(d);ledgers.extend(l)
        print(f"{path.stem}: independent fits/selections/tests complete",flush=True)
    outcomes=pd.DataFrame(records)
    summaries=summarize(outcomes)
    outcomes.to_csv(args.output/"outcomes.csv",index=False)
    summaries.to_csv(args.output/"summary.csv",index=False)
    pd.DataFrame(ledgers).to_csv(args.output/"budget_ledger.csv",index=False)
    (args.output/"diagnostics.json").write_text(json.dumps(diagnostics,indent=2),encoding="utf-8")
    for p in sorted(args.output.iterdir()):
        if p.name != "manifest.json":
            manifest.setdefault("output_sha256",{})[p.name]=sha256(p)
    (args.output/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding="utf-8")
    print(summaries.to_string(index=False))


if __name__ == "__main__":
    main()
