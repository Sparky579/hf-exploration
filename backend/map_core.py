"""
Module purpose:
- Maintain map nodes, node states, neighbor edges, and role placement on the campus map.

Classes:
- MapNode
  - add_state(sentence): append one description sentence to node state list.
  - set_states(sentences): replace current node state list.
  - add_role(role_name): register role name at this node.
  - remove_role(role_name): remove role name from this node.
- CampusMap
  - add_node(name, states): create a node.
  - get_node(name): fetch a node or raise if missing.
  - connect_nodes(a, b, bidirectional): create an edge.
  - set_node_states(node_name, states): replace a node's state sentences.
  - get_adjacent_nodes(node_name): return sorted neighbor names.
  - add_role(role, start_node_name): place a role at a start node.
  - transfer_role(role_name, from_node_name, to_node_name): move role between nodes.

Functions:
- build_default_campus_map(): build default topology based on the provided campus sketch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .roles import Role


@dataclass
class MapNode:
    name: str
    states: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    neighbors: set[str] = field(default_factory=set)

    def add_state(self, sentence: str) -> None:
        self.states.append(sentence)

    def set_states(self, sentences: list[str]) -> None:
        self.states = list(sentences)

    def add_role(self, role_name: str) -> None:
        if role_name not in self.roles:
            self.roles.append(role_name)

    def remove_role(self, role_name: str) -> None:
        if role_name in self.roles:
            self.roles.remove(role_name)


class CampusMap:
    """Map container that manages nodes, edges, and role placement."""

    def __init__(self) -> None:
        self.nodes: dict[str, MapNode] = {}
        self.roles: dict[str, Role] = {}

    def add_node(self, name: str, states: list[str] | None = None) -> MapNode:
        if name in self.nodes:
            raise ValueError(f"node already exists: {name}")
        node = MapNode(name=name, states=list(states or []))
        self.nodes[name] = node
        return node

    def get_node(self, name: str) -> MapNode:
        if name not in self.nodes:
            raise KeyError(f"node not found: {name}")
        return self.nodes[name]

    def connect_nodes(self, node_a: str, node_b: str, bidirectional: bool = True) -> None:
        a = self.get_node(node_a)
        b = self.get_node(node_b)
        a.neighbors.add(b.name)
        if bidirectional:
            b.neighbors.add(a.name)

    def set_node_states(self, node_name: str, states: list[str]) -> None:
        self.get_node(node_name).set_states(states)

    def get_adjacent_nodes(self, node_name: str) -> list[str]:
        return sorted(self.get_node(node_name).neighbors)

    def add_role(self, role: Role, start_node_name: str) -> None:
        if role.name in self.roles:
            raise ValueError(f"role already exists: {role.name}")
        node = self.get_node(start_node_name)
        node.add_role(role.name)
        self.roles[role.name] = role

    def transfer_role(self, role_name: str, from_node_name: str, to_node_name: str) -> None:
        from_node = self.get_node(from_node_name)
        to_node = self.get_node(to_node_name)
        from_node.remove_role(role_name)
        to_node.add_role(role_name)


def build_default_campus_map() -> CampusMap:
    """Build a default campus topology based on the provided sketch."""

    campus_map = CampusMap()

    node_names = [
        "正门",
        "国际部",
        "东教学楼南",
        "南教学楼",
        "西教学楼南",
        "德政楼",
        "宿舍",
        "东教学楼内部",
        "图书馆",
        "小卖部",
        "东教学楼北",
        "生化楼",
        "西教学楼北",
        "体育馆",
        "食堂",
        "田径场",
        "后门",
    ]
    for name in node_names:
        campus_map.add_node(name)

    edges = [
        ("正门", "东教学楼南"),
        ("正门", "西教学楼南"),
        ("正门", "南教学楼"),
        ("国际部", "东教学楼南"),
        ("东教学楼南", "南教学楼"),
        ("南教学楼", "西教学楼南"),
        ("西教学楼南", "德政楼"),
        ("宿舍", "国际部"),
        ("宿舍", "小卖部"),
        ("食堂", "小卖部"),
        ("东教学楼南", "东教学楼内部"),
        ("东教学楼内部", "东教学楼北"),
        ("东教学楼南", "西教学楼南"),
        ("小卖部", "东教学楼北"),
        ("东教学楼北", "生化楼"),
        ("生化楼", "西教学楼北"),
        ("西教学楼北", "体育馆"),
        ("西教学楼南", "西教学楼北"),
        ("德政楼", "图书馆"),
        ("图书馆", "体育馆"),
        ("西教学楼南", "图书馆"),
        ("西教学楼北", "图书馆"),
        ("小卖部", "生化楼"),
        ("小卖部", "田径场"),
        ("生化楼", "田径场"),
        ("后门", "田径场"),
        ("食堂", "后门"),
        ("田径场", "体育馆"),
    ]
    for n1, n2 in edges:
        campus_map.connect_nodes(n1, n2)

    return campus_map
