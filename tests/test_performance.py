"""T-NFR: 대규모 네트워크 성능 — 1000노드 해석이 충분히 빨라야 한다.

목표(NFR): 1000노드 < 1s. CI 변동을 고려해 1.5s 마진으로 검증한다.
핵심 최적화: solver._get_pipe 의 (start,end)→pipe O(1) 조회.
"""
import sys
import time
sys.path.insert(0, "src")

from fhdl.core.pipeline import AnalysisPipeline


def _chain(n: int) -> str:
    L = ["system m { unit_system=METRIC; fluid=water; temp=20; }",
         "tank src { z=100m; }"]
    prev = "src"
    conns = ["connect src"]
    for i in range(n):
        L.append(f"junction j{i} {{ z={100 - i * 0.05}m; }}")
        L.append(f"pipe p{i} {{ start={prev}; end=j{i}; length=10m; diameter=150mm; material=Steel; }}")
        conns.append(f"-> j{i}")
        prev = f"j{i}"
    L.append("terminal t { z=10m; required_q=200lpm; }")
    L.append(f"pipe pt {{ start={prev}; end=t; length=10m; diameter=150mm; material=Steel; }}")
    conns.append("-> t")
    L.append(" ".join(conns) + ";")
    return "\n".join(L)


def test_1000_nodes_under_budget():
    AnalysisPipeline().run(_chain(20))          # 워밍업
    code = _chain(1000)
    t = time.perf_counter()
    r = AnalysisPipeline().run(code)
    dt = time.perf_counter() - t
    assert len(r.node_results) == 1002
    assert r.status != "FAILED"
    assert dt < 1.5, f"1000노드 해석이 너무 느림: {dt*1000:.0f}ms"


def test_pipe_lookup_scales():
    """노드 수가 2배여도 시간이 4배 이상 늘지 않아야 한다(선형 탐색 회귀 방지)."""
    AnalysisPipeline().run(_chain(20))

    def t_run(n):
        c = _chain(n)
        s = time.perf_counter()
        AnalysisPipeline().run(c)
        return time.perf_counter() - s

    t500 = t_run(500)
    t1000 = t_run(1000)
    # O(N^2) 였다면 ~4배. O(N) 이면 ~2배. 3배 미만이면 통과.
    assert t1000 < t500 * 3.0 + 0.05
