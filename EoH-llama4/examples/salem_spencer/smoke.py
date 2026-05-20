# examples/salem_spencer/smoke.py
from eoh.problems.optimization.salem_spencer.run import SALEMSPENCER

code = r"""
def heuristic(n, rng=None):
    # 超簡單的 3-AP-free 貪婪建構器（從小到大挑）
    S = []
    present = set()
    for x in range(1, n+1):
        ok = True
        for b in S:
            if 2*b - x in present:  # 若存在 (2b - x, b, x) 就違規
                ok = False
                break
        if ok:
            S.append(x)
            present.add(x)
    return S
"""

prob = SALEMSPENCER({"n": 82})
print(">>> calling evaluate()", flush=True)
fitness = prob.evaluate(code)
print(">>> fitness =", fitness, flush=True)
