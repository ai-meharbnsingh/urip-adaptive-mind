"""
Attack path engine — Project_33a §13 LIVE (MVP scaffold, 15th license module).

Core algorithm
--------------
BFS over (source_id, target_id) edges, starting from every internet-exposed
node, looking for any path that reaches a tier-1 asset.  Each path is
scored = base 50 + (edge weight sum * 5) + (10 if MITRE chain present),
clamped to [0,100].

This is intentionally simple — production implementations layer in CVSS
exploitability, asset-criticality, and probabilistic chaining.  See §13
for the roadmap.
"""
from __future__ import annotations

import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.attack_path import (
    EDGE_TYPE_VALUES,
    NODE_TYPE_VALUES,
    AttackPath,
    AttackPathEdge,
    AttackPathNode,
)

logger = logging.getLogger(__name__)


# Default MITRE ATT&CK chain inferred from edge types (placeholder mapping).
_EDGE_TO_MITRE = {
    "exposed_to": "T1190",                # Exploit Public-Facing Application
    "can_authenticate_to": "T1078",       # Valid Accounts
    "has_access_to": "T1486",             # Data Encrypted for Impact (proxy for "reaches crown jewel")
}


# --------------------------------------------------------------------------- #
async def add_node(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    node_type: str,
    label: str,
    is_internet_exposed: bool = False,
    asset_tier: Optional[int] = None,
    properties: Optional[dict] = None,
) -> AttackPathNode:
    if node_type not in NODE_TYPE_VALUES:
        raise ValueError(f"Invalid node_type {node_type!r}; allowed: {sorted(NODE_TYPE_VALUES)}")
    if not label or not label.strip():
        raise ValueError("label is required")
    if asset_tier is not None and asset_tier not in {1, 2, 3, 4}:
        raise ValueError("asset_tier must be in {1,2,3,4}")

    n = AttackPathNode(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        node_type=node_type,
        label=label.strip(),
        is_internet_exposed=is_internet_exposed,
        asset_tier=asset_tier,
        properties=properties,
    )
    db.add(n)
    await db.flush()
    return n


async def add_edge(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    edge_type: str,
    weight: float = 1.0,
) -> AttackPathEdge:
    if edge_type not in EDGE_TYPE_VALUES:
        raise ValueError(f"Invalid edge_type {edge_type!r}; allowed: {sorted(EDGE_TYPE_VALUES)}")
    if source_id == target_id:
        raise ValueError("source_id and target_id must differ")
    if weight < 0:
        raise ValueError("weight must be >= 0")

    e = AttackPathEdge(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        weight=weight,
    )
    db.add(e)
    await db.flush()
    return e


# --------------------------------------------------------------------------- #
def _compute_score(hop_count: int, edge_weights: list[float], has_chain: bool) -> float:
    base = 50.0
    weight_bonus = sum(edge_weights) * 5.0
    chain_bonus = 10.0 if has_chain else 0.0
    # Penalize very long paths (less likely to be feasible)
    hop_penalty = max(0.0, hop_count - 3) * 5.0
    score = base + weight_bonus + chain_bonus - hop_penalty
    return max(0.0, min(100.0, round(score, 2)))


async def find_critical_paths(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    max_hops: int = 5,
) -> list[dict]:
    """
    BFS from every internet-exposed node looking for tier-1 assets.

    Returns a list of dicts (NOT persisted yet) — caller may persist via
    `recompute_paths`.
    """
    # Load all nodes + edges into memory (MVP scale).
    nodes_rows = (
        await db.execute(select(AttackPathNode).where(AttackPathNode.tenant_id == tenant_id))
    ).scalars().all()
    edges_rows = (
        await db.execute(select(AttackPathEdge).where(AttackPathEdge.tenant_id == tenant_id))
    ).scalars().all()

    nodes_by_id = {n.id: n for n in nodes_rows}
    adj: dict[uuid.UUID, list[AttackPathEdge]] = {}
    for e in edges_rows:
        adj.setdefault(e.source_id, []).append(e)

    sources = [n for n in nodes_rows if n.is_internet_exposed]
    targets = {n.id for n in nodes_rows if n.asset_tier == 1}

    paths: list[dict] = []
    for source in sources:
        # BFS — record path predecessors
        queue = deque([(source.id, [source.id], [], [])])  # (current, node_ids_path, edge_weights, edge_types)
        visited_per_path: set[tuple[uuid.UUID, ...]] = set()
        while queue:
            current, path_nodes, weights, edge_types = queue.popleft()
            if len(path_nodes) - 1 > max_hops:
                continue
            tup = tuple(path_nodes)
            if tup in visited_per_path:
                continue
            visited_per_path.add(tup)

            if current in targets and current != source.id:
                mitre_chain = [
                    _EDGE_TO_MITRE[t] for t in edge_types if t in _EDGE_TO_MITRE
                ]
                paths.append({
                    "source_id": source.id,
                    "target_id": current,
                    "hop_count": len(path_nodes) - 1,
                    "path_node_ids": [str(nid) for nid in path_nodes],
                    "edge_weights": weights,
                    "edge_types": edge_types,
                    "mitre_chain": mitre_chain or None,
                    "risk_score": _compute_score(
                        len(path_nodes) - 1, weights, bool(mitre_chain),
                    ),
                })
                continue

            for e in adj.get(current, []):
                if e.target_id in path_nodes:  # avoid cycles
                    continue
                queue.append((
                    e.target_id,
                    path_nodes + [e.target_id],
                    weights + [e.weight],
                    edge_types + [e.edge_type],
                ))

    # Sort by risk_score desc
    paths.sort(key=lambda p: p["risk_score"], reverse=True)
    return paths


async def recompute_paths(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    max_hops: int = 5,
) -> list[AttackPath]:
    """Drop existing computed paths for tenant, run BFS, persist."""
    await db.execute(delete(AttackPath).where(AttackPath.tenant_id == tenant_id))
    await db.flush()

    candidates = await find_critical_paths(db, tenant_id, max_hops=max_hops)
    persisted: list[AttackPath] = []
    for c in candidates:
        ap = AttackPath(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            source_node_id=c["source_id"],
            target_node_id=c["target_id"],
            hop_count=c["hop_count"],
            risk_score=c["risk_score"],
            is_critical=c["risk_score"] >= 60.0,
            path_node_ids=c["path_node_ids"],
            mitre_chain=c["mitre_chain"],
        )
        db.add(ap)
        persisted.append(ap)
    await db.flush()
    return persisted


async def list_critical_paths(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    only_critical: bool = True,
    limit: int = 100,
) -> list[AttackPath]:
    stmt = select(AttackPath).where(AttackPath.tenant_id == tenant_id)
    if only_critical:
        stmt = stmt.where(AttackPath.is_critical.is_(True))
    stmt = stmt.order_by(AttackPath.risk_score.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_path_details(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    path_id: uuid.UUID,
) -> Optional[dict]:
    """Return path + node details (resolves UUIDs to labels)."""
    ap = (
        await db.execute(
            select(AttackPath).where(
                AttackPath.tenant_id == tenant_id,
                AttackPath.id == path_id,
            )
        )
    ).scalar_one_or_none()
    if ap is None:
        return None

    node_uuids = [uuid.UUID(s) for s in ap.path_node_ids]
    nodes = (
        await db.execute(
            select(AttackPathNode).where(
                AttackPathNode.tenant_id == tenant_id,
                AttackPathNode.id.in_(node_uuids),
            )
        )
    ).scalars().all()
    by_id = {n.id: n for n in nodes}
    ordered_nodes = []
    for s in ap.path_node_ids:
        n = by_id.get(uuid.UUID(s))
        if n:
            ordered_nodes.append({
                "id": str(n.id),
                "label": n.label,
                "node_type": n.node_type,
                "is_internet_exposed": n.is_internet_exposed,
                "asset_tier": n.asset_tier,
            })
    return {
        "id": str(ap.id),
        "hop_count": ap.hop_count,
        "risk_score": ap.risk_score,
        "is_critical": ap.is_critical,
        "mitre_chain": ap.mitre_chain,
        "computed_at": ap.computed_at,
        "nodes": ordered_nodes,
    }
