import sys, numpy as np
results = []
def check(name, fn):
    try:
        fn(); print(f"PASS: {name}"); return True
    except Exception as e:
        print(f"FAIL: {name} -> {type(e).__name__}: {e}"); return False

def t_imports():
    import qiskit, qiskit_aer, scipy, pandas, sklearn, cvxpy, networkx
    print("  qiskit", qiskit.__version__, "| aer", qiskit_aer.__version__,
          "| scipy", scipy.__version__, "| cvxpy", cvxpy.__version__)
results.append(check("imports core stack", t_imports))

# qiskit-optimization / algorithms en Qiskit 2.x (warning-only: si falla, reportar pero no abortar)
def t_qiskit_opt():
    import networkx as nx
    from qiskit_optimization.applications import Maxcut
    g = nx.random_regular_graph(3, 6, seed=1)
    qp = Maxcut(nx.to_numpy_array(g)).to_quadratic_program()
    H, off = qp.to_ising()
    print("  Maxcut->Ising ok, num_qubits", H.num_qubits)
opt_ok = check("qiskit-optimization Maxcut->Ising (Qiskit 2.x)", t_qiskit_opt)

def t_aer_landscape():
    import networkx as nx
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, depolarizing_error
    g = nx.random_regular_graph(3, 6, seed=1); edges = list(g.edges()); n = g.number_of_nodes()
    def qaoa(gamma, beta):
        qc = QuantumCircuit(n); qc.h(range(n))
        for (i,j) in edges: qc.rzz(2*gamma, i, j)
        for k in range(n): qc.rx(2*beta, k)
        qc.measure_all(); return qc
    nm = NoiseModel()
    nm.add_all_qubit_quantum_error(depolarizing_error(0.01,1), ['h','rx','rz','sx','x','u','u1','u2','u3'])
    nm.add_all_qubit_quantum_error(depolarizing_error(0.03,2), ['cx','cz','rzz'])
    sim = AerSimulator(noise_model=nm)
    def cut(b):
        x = [int(c) for c in b[::-1]]
        return sum(1 for (i,j) in edges if x[i]!=x[j])
    def landscape(gamma, beta, shots=2048):
        qc = transpile(qaoa(gamma,beta), sim)
        counts = sim.run(qc, shots=shots).result().get_counts()
        return sum(cut(b)*c for b,c in counts.items())/shots
    print("  noisy <C>:", round(landscape(0.6,0.4),3))
results.append(check("AerSimulator + noise model + counts landscape", t_aer_landscape))

def t_gap_kernel():
    n = 5; L = np.zeros((n-1,n))
    for i in range(1,n): L[i-1,0]=-1.0; L[i-1,i]=1.0
    assert np.allclose(L @ np.ones(n), 0.0)
    rng = np.random.default_rng(0); M = rng.standard_normal((n,n)); K = M@M.T
    Sigma = L @ K @ L.T
    assert np.min(np.linalg.eigvalsh(Sigma)) > -1e-9
    print("  L1=0 ok, Sigma PSD ok, dim", Sigma.shape)
results.append(check("gap kernel L, Sigma=LKL^T PSD", t_gap_kernel))

def t_gri():
    from scipy.stats import multivariate_normal as mvn
    Sigma = np.array([[2.0,0.5],[0.5,2.0]]); mu = np.array([1.5,1.2])
    risk = 1.0 - float(mvn(mean=np.zeros(2), cov=Sigma).cdf(mu))
    assert 0.0 <= risk <= 1.0
    print("  GRI risk:", round(risk,4))
results.append(check("GRI MVN orthant (scipy)", t_gri))

def t_socp():
    import cvxpy as cp
    q = 3; lams = np.array([1.0,2.0,3.0])
    A = np.vstack([np.ones(q), lams]); rho = np.array([1.0,0.0])  # sum c=1, sum c*lam=0
    Qi = np.diag([1.0,0.5,0.25]) + 1e-6*np.eye(q); mu_i = 1.0
    Lc = np.linalg.cholesky(Qi)
    c = cp.Variable(q); u = cp.Variable()
    cp.Problem(cp.Minimize(u), [A @ c == rho, cp.norm(Lc.T @ c, 2) <= u*mu_i]).solve()
    assert abs(c.value.sum()-1.0) < 1e-5
    print("  SOCP solved, c=", np.round(c.value,3), "u=", round(float(u.value),4))
results.append(check("DA-ZNE SOCP (cvxpy)", t_socp))

def t_selector_lw():
    from sklearn.covariance import LedoitWolf
    rng = np.random.default_rng(1); X = rng.standard_normal((50,4))
    Shat = LedoitWolf().fit(X).covariance_
    risks = {"Raw":0.3,"ZNE":0.25,"DA-ZNE":0.2}
    sel = min(risks, key=risks.get)
    assert sel=="DA-ZNE" and Shat.shape==(4,4)
    print("  Ledoit-Wolf ok, selector picks:", sel)
results.append(check("selector + Ledoit-Wolf shrinkage", t_selector_lw))

print("\nSUMMARY:", sum(results), "/", len(results), "core stages passed",
      "| qiskit-optimization:", "ok" if opt_ok else "ISSUE")
sys.exit(0 if all(results) else 1)
