"""
Passenger tickets data structures:
- HashTable for ticket lookup
- Graph adjacency list for stops
- BFS path finding with LinkedList path
"""
from __future__ import annotations

import json
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


class HashTable:
    """Simple hash table with chaining for ticket lookup."""

    def __init__(self, size: int = 128) -> None:
        self.size = max(8, size)
        self.buckets: List[List[tuple[str, Any]]] = [[] for _ in range(self.size)]

    def _index(self, key: str) -> int:
        return hash(key) % self.size

    def set(self, key: str, value: Any) -> None:
        index = self._index(key)
        bucket = self.buckets[index]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)
                return
        bucket.append((key, value))

    def get(self, key: str) -> Optional[Any]:
        index = self._index(key)
        for k, value in self.buckets[index]:
            if k == key:
                return value
        return None

    def values(self) -> List[Any]:
        items: List[Any] = []
        for bucket in self.buckets:
            for _, value in bucket:
                items.append(value)
        return items


class LinkedListNode:
    def __init__(self, value: str) -> None:
        self.value = value
        self.next: Optional[LinkedListNode] = None


class LinkedList:
    """Singly linked list for representing a path."""

    def __init__(self) -> None:
        self.head: Optional[LinkedListNode] = None
        self.tail: Optional[LinkedListNode] = None
        self.length = 0

    def append(self, value: str) -> None:
        node = LinkedListNode(value)
        if not self.head:
            self.head = self.tail = node
        else:
            assert self.tail is not None
            self.tail.next = node
            self.tail = node
        self.length += 1

    def to_list(self) -> List[str]:
        values: List[str] = []
        current = self.head
        while current:
            values.append(current.value)
            current = current.next
        return values


class StopGraph:
    """Adjacency list graph for stops connectivity."""

    def __init__(self) -> None:
        self.adj: Dict[str, List[str]] = {}
        self.weights: Dict[str, Dict[str, float]] = {}

    def add_stop(self, stop_name: str) -> None:
        if stop_name and stop_name not in self.adj:
            self.adj[stop_name] = []
            self.weights[stop_name] = {}

    def add_edge(self, stop_a: str, stop_b: str, weight: float) -> None:
        if stop_a == stop_b:
            return
        self.add_stop(stop_a)
        self.add_stop(stop_b)
        if stop_b not in self.adj[stop_a]:
            self.adj[stop_a].append(stop_b)
        if stop_a not in self.adj[stop_b]:
            self.adj[stop_b].append(stop_a)
        self.weights[stop_a][stop_b] = weight
        self.weights[stop_b][stop_a] = weight

    def neighbors(self, stop_name: str) -> List[str]:
        return self.adj.get(stop_name, [])

    def has_stop(self, stop_name: str) -> bool:
        return stop_name in self.adj

    def weight(self, stop_a: str, stop_b: str) -> float:
        return self.weights.get(stop_a, {}).get(stop_b, 1.0)


@dataclass
class StopInfo:
    name: str


class RoutePlanner:
    """Loads routes.json and provides BFS path lookup."""

    def __init__(self, routes_path: str) -> None:
        self.routes_path = routes_path
        self.stops: Dict[str, StopInfo] = {}
        self.edges: List[Dict[str, Any]] = []
        self.graph = StopGraph()
        self.reload()

    def reload(self) -> None:
        self.stops = {}
        self.edges = []
        self.graph = StopGraph()
        routes_data = self._load_routes()
        for route in routes_data.get("routes", []):
            stops = route.get("stops", [])
            for stop in stops:
                name = (stop.get("stop_name") or "").strip()
                if not name:
                    continue
                if name not in self.stops:
                    self.stops[name] = StopInfo(
                        name=name,
                    )
                self.graph.add_stop(name)
            for idx in range(len(stops) - 1):
                current = (stops[idx].get("stop_name") or "").strip()
                nxt = (stops[idx + 1].get("stop_name") or "").strip()
                weight = self._distance_value(stops[idx + 1].get("distance_from_previous"))
                if current and nxt:
                    self.graph.add_edge(current, nxt, weight)
                    self.edges.append({
                        "from": current,
                        "to": nxt,
                        "weight": weight,
                        "route_id": route.get("route_id"),
                        "route_name": route.get("route_name"),
                    })

    def _load_routes(self) -> Dict[str, Any]:
        if not os.path.exists(self.routes_path):
            return {"routes": []}
        with open(self.routes_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _distance_value(self, value: Any) -> float:
        try:
            if value is None:
                return 1.0
            parsed = float(value)
            return parsed if parsed > 0 else 1.0
        except (TypeError, ValueError):
            return 1.0

    def validate_stop(self, stop_name: str) -> bool:
        return stop_name in self.stops

    def list_stops(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": info.name,
            }
            for info in self.stops.values()
        ]

    def list_edges(self) -> List[Dict[str, Any]]:
        return self.edges

    def bfs_path(self, start: str, end: str) -> Optional[LinkedList]:
        if not self.validate_stop(start) or not self.validate_stop(end):
            return None
        if start == end:
            path = LinkedList()
            path.append(start)
            return path

        queue = deque([start])
        visited = {start}
        prev: Dict[str, Optional[str]] = {start: None}

        while queue:
            current = queue.popleft()
            if current == end:
                break
            for neighbor in self.graph.neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    prev[neighbor] = current
                    queue.append(neighbor)

        if end not in prev:
            return None

        path_nodes: List[str] = []
        current: Optional[str] = end
        while current is not None:
            path_nodes.append(current)
            current = prev.get(current)
        path_nodes.reverse()

        linked_path = LinkedList()
        for node in path_nodes:
            linked_path.append(node)
        return linked_path

    def shortest_path(self, start: str, end: str) -> Optional[Dict[str, Any]]:
        if not self.validate_stop(start) or not self.validate_stop(end):
            return None
        if start == end:
            return {"path": [start], "distance": 0.0, "segments": []}

        distances: Dict[str, float] = {stop: float("inf") for stop in self.graph.adj}
        previous: Dict[str, Optional[str]] = {start: None}
        distances[start] = 0.0
        visited = set()

        while True:
            current = None
            current_distance = float("inf")
            for stop, dist in distances.items():
                if stop not in visited and dist < current_distance:
                    current = stop
                    current_distance = dist
            if current is None:
                break
            if current == end:
                break
            visited.add(current)
            for neighbor in self.graph.neighbors(current):
                weight = self.graph.weight(current, neighbor)
                new_distance = current_distance + weight
                if new_distance < distances[neighbor]:
                    distances[neighbor] = new_distance
                    previous[neighbor] = current

        if distances[end] == float("inf"):
            return None

        path_nodes: List[str] = []
        current: Optional[str] = end
        while current is not None:
            path_nodes.append(current)
            current = previous.get(current)
        path_nodes.reverse()

        segments: List[Dict[str, Any]] = []
        for index in range(len(path_nodes) - 1):
            from_stop = path_nodes[index]
            to_stop = path_nodes[index + 1]
            segments.append({
                "from": from_stop,
                "to": to_stop,
                "weight": self.graph.weight(from_stop, to_stop),
            })

        return {
            "path": path_nodes,
            "distance": distances[end],
            "segments": segments,
        }


class TicketStore:
    """Ticket store with hash table lookup by ticket_id."""

    def __init__(self, tickets_path: str) -> None:
        self.tickets_path = tickets_path
        self.tickets: List[Dict[str, Any]] = []
        self._data: Dict[str, Any] = {"tickets": []}
        self.table = HashTable()
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.tickets_path):
            os.makedirs(os.path.dirname(self.tickets_path), exist_ok=True)
            with open(self.tickets_path, "w", encoding="utf-8") as handle:
                json.dump({"tickets": []}, handle, indent=2)
            self._data = {"tickets": []}
            self.tickets = []
            return

        with open(self.tickets_path, "r", encoding="utf-8") as handle:
            self._data = json.load(handle) or {}
            self.tickets = self._data.get("tickets", [])
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self.table = HashTable(size=max(128, len(self.tickets) * 2 + 1))
        for ticket in self.tickets:
            ticket_id = ticket.get("ticket_id")
            if ticket_id:
                self.table.set(ticket_id, ticket)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.tickets_path), exist_ok=True)
        with open(self.tickets_path, "w", encoding="utf-8") as handle:
            data = dict(self._data)
            data["tickets"] = self.tickets
            json.dump(data, handle, indent=2)

    def list_for_passenger(self, passenger_id: str) -> List[Dict[str, Any]]:
        return [ticket for ticket in self.tickets if ticket.get("passenger_id") == passenger_id]

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        return self.table.get(ticket_id)

    def add_ticket(
        self,
        passenger_id: str,
        passenger_name: str,
        start_stop: str,
        end_stop: str,
        path: List[str],
        bus_number: str,
        fare: float,
        distance: float,
        eta: Optional[str],
    ) -> Dict[str, Any]:
        ticket_id = f"T-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{len(self.tickets) + 1}"
        ticket = {
            "ticket_id": ticket_id,
            "passenger_id": passenger_id,
            "passenger_name": passenger_name,
            "from_stop": start_stop,
            "to_stop": end_stop,
            "path": path,
            "status": "open",
            "fare": fare,
            "distance": distance,
            "bus_number": bus_number,
            "eta": eta,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.tickets.insert(0, ticket)
        self.table.set(ticket_id, ticket)
        self._save()
        return ticket


class BusStore:
    """Loads buses.json for passenger selection."""

    def __init__(self, buses_path: str) -> None:
        self.buses_path = buses_path

    def list_buses(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.buses_path):
            return []
        with open(self.buses_path, "r", encoding="utf-8") as handle:
            data = json.load(handle) or []
        if isinstance(data, dict):
            data = data.get("buses", [])
        return [
            bus
            for bus in data
            if bus.get("status", "").lower() != "inactive"
        ]
