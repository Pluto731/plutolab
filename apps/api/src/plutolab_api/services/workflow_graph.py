"""Bounded, deterministic DAG planning; isolated nodes are valid independent roots."""

from plutolab_api.schemas.agent import WorkflowGraph


def plan_layers(graph: WorkflowGraph) -> tuple[tuple[str, ...], ...]:
    # Revalidate mutable nested models at the execution boundary.
    graph = WorkflowGraph.model_validate(graph.model_dump())
    children: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
    degree = dict.fromkeys(children, 0)
    for edge in graph.edges:
        children[edge.source].append(edge.target)
        degree[edge.target] += 1
    ready = sorted(node for node, count in degree.items() if count == 0)
    layers: list[tuple[str, ...]] = []
    visited = 0
    while ready:
        layers.append(tuple(ready))
        visited += len(ready)
        following = []
        for node in ready:
            for child in children[node]:
                degree[child] -= 1
                if degree[child] == 0:
                    following.append(child)
        ready = sorted(following)
    if visited != len(children):
        raise ValueError("Workflow must be acyclic")
    return tuple(layers)
