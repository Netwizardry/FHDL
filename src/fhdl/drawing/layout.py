"""좌표 미지정 노드의 자동 배치 (도면용 개략 좌표).

공급원(탱크·펌프)에서의 흐름 깊이를 동쪽(x) 방향 열로, 같은 깊이의 노드를 북쪽(y)으로
벌려 놓는다. z 는 노드 고도를 그대로 쓴다. 좌표를 명시한 노드는 건드리지 않는다.
"""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Tuple

Point3 = Tuple[float, float, float]


def flow_depths(em) -> Dict[str, int]:
    """공급원 기준 BFS 깊이 (도달 불가 노드는 최대 깊이 + 1)."""
    adj: Dict[str, List[str]] = {n: [] for n in em.all_node_ids()}
    for p in em.pipes.values():
        if p.start_id in adj and p.end_id in adj:
            adj[p.start_id].append(p.end_id)
    has_in = {p.end_id for p in em.pipes.values()}
    roots = [n for n in list(em.tanks) + list(em.pumps) if n not in has_in] or \
            [n for n in adj if n not in has_in] or list(adj)[:1]
    depth: Dict[str, int] = {}
    q = deque((r, 0) for r in roots)
    while q:
        n, d = q.popleft()
        if n in depth:
            continue
        depth[n] = d
        for m in adj.get(n, []):
            if m not in depth:
                q.append((m, d + 1))
    top = max(depth.values(), default=0)
    for n in adj:
        depth.setdefault(n, top + 1)
    return depth


def node_positions(em, spacing: float = 0.0) -> Tuple[Dict[str, Point3], List[str]]:
    """(노드 → 3D 좌표, 자동 배치된 노드 목록)."""
    lengths = sorted(p.length for p in em.pipes.values() if p.length > 0)
    step = spacing or (lengths[len(lengths) // 2] if lengths else 10.0)
    depth = flow_depths(em)
    by_depth: Dict[int, List[str]] = {}
    for n, d in depth.items():
        by_depth.setdefault(d, []).append(n)
    pos: Dict[str, Point3] = {}
    auto: List[str] = []
    for nid in em.all_node_ids():
        ent = em.get_node_entity(nid)
        if getattr(ent, "has_xy", False):
            pos[nid] = (float(ent.x), float(ent.y), float(ent.elevation))
            continue
        d = depth[nid]
        col = by_depth[d]
        i = col.index(nid)
        pos[nid] = (d * step, (i - (len(col) - 1) / 2) * step * 0.8, float(ent.elevation))
        auto.append(nid)
    return pos, auto
