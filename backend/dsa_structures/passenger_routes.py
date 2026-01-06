"""
Passenger Ticket Booking System with Data Structures
1. Binary Search Tree (BST) for Passenger Database
2. Graph for City Transport Network
3. Min Heap for Ticket Priority
4. Linked List for Booking History
"""
import json
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import heapq
from collections import deque

# ===================== DATA STRUCTURES =====================

# ---------- Binary Search Tree (BST) for Passengers ----------
class BSTNode:
    """Binary Search Tree Node for Passenger Storage"""
    def __init__(self, passenger_id: str, passenger_data: dict):
        self.passenger_id = passenger_id
        self.data = passenger_data
        self.left = None
        self.right = None

class PassengerBST:
    """Binary Search Tree for Efficient Passenger Search"""
    def __init__(self):
        self.root = None
    
    def insert(self, passenger_id: str, passenger_data: dict) -> None:
        """Insert passenger into BST"""
        if not self.root:
            self.root = BSTNode(passenger_id, passenger_data)
        else:
            self._insert_recursive(self.root, passenger_id, passenger_data)
    
    def _insert_recursive(self, node: BSTNode, passenger_id: str, passenger_data: dict) -> None:
        if passenger_id < node.passenger_id:
            if node.left:
                self._insert_recursive(node.left, passenger_id, passenger_data)
            else:
                node.left = BSTNode(passenger_id, passenger_data)
        else:
            if node.right:
                self._insert_recursive(node.right, passenger_id, passenger_data)
            else:
                node.right = BSTNode(passenger_id, passenger_data)
    
    def search(self, passenger_id: str) -> Optional[dict]:
        """Search passenger by ID using BST O(log n)"""
        return self._search_recursive(self.root, passenger_id)
    
    def _search_recursive(self, node: BSTNode, passenger_id: str) -> Optional[dict]:
        if not node:
            return None
        if passenger_id == node.passenger_id:
            return node.data
        elif passenger_id < node.passenger_id:
            return self._search_recursive(node.left, passenger_id)
        else:
            return self._search_recursive(node.right, passenger_id)
    
    def get_all_passengers(self) -> List[dict]:
        """Get all passengers using inorder traversal"""
        passengers = []
        self._inorder_traversal(self.root, passengers)
        return passengers
    
    def _inorder_traversal(self, node: BSTNode, result: List) -> None:
        if node:
            self._inorder_traversal(node.left, result)
            result.append({
                'passenger_id': node.passenger_id,
                **node.data
            })
            self._inorder_traversal(node.right, result)

# ---------- Graph for City Transport Network ----------
class GraphNode:
    """Graph Node representing a Bus Stop"""
    def __init__(self, stop_name: str, location: str):
        self.stop_name = stop_name
        self.location = location
        self.neighbors = {}  # {stop_name: {'distance': x, 'time': y}}

class TransportGraph:
    """Graph representing City Transport Network"""
    def __init__(self):
        self.nodes = {}
        self.routes = {}
    
    def add_stop(self, stop_name: str, location: str) -> None:
        """Add a bus stop to the graph"""
        if stop_name not in self.nodes:
            self.nodes[stop_name] = GraphNode(stop_name, location)
    
    def add_connection(self, stop1: str, stop2: str, distance: float, time_minutes: int) -> None:
        """Add connection between two stops"""
        if stop1 in self.nodes and stop2 in self.nodes:
            self.nodes[stop1].neighbors[stop2] = {
                'distance': distance,
                'time': time_minutes
            }
            self.nodes[stop2].neighbors[stop1] = {
                'distance': distance,
                'time': time_minutes
            }
    
    def dijkstra_shortest_path(self, start: str, end: str, criteria: str = 'time') -> Dict:
        """Find shortest path using Dijkstra's Algorithm"""
        if start not in self.nodes or end not in self.nodes:
            return {'path': [], 'total': float('inf'), 'message': 'Invalid stops'}
        
        # Priority queue: (distance/time, stop, path)
        pq = [(0, start, [start])]
        visited = set()
        distances = {stop: float('inf') for stop in self.nodes}
        distances[start] = 0
        
        while pq:
            current_dist, current_stop, path = heapq.heappop(pq)
            
            if current_stop in visited:
                continue
            
            visited.add(current_stop)
            
            # If we reached destination
            if current_stop == end:
                return {
                    'path': path,
                    'total_time': current_dist if criteria == 'time' else None,
                    'total_distance': current_dist if criteria == 'distance' else None,
                    'stops': len(path) - 1
                }
            
            # Explore neighbors
            for neighbor, info in self.nodes[current_stop].neighbors.items():
                if neighbor not in visited:
                    new_dist = current_dist + info[criteria]
                    if new_dist < distances[neighbor]:
                        distances[neighbor] = new_dist
                        heapq.heappush(pq, (new_dist, neighbor, path + [neighbor]))
        
        return {'path': [], 'total': float('inf'), 'message': 'No path found'}
    
    def bfs_nearest_stop(self, start: str, target_location: str) -> Dict:
        """Find nearest bus stop using BFS"""
        if start not in self.nodes:
            return {'nearest_stop': None, 'distance': float('inf')}
        
        visited = set()
        queue = deque([(start, 0, [start])])
        
        while queue:
            current_stop, distance, path = queue.popleft()
            
            if target_location.lower() in self.nodes[current_stop].location.lower():
                return {
                    'nearest_stop': current_stop,
                    'location': self.nodes[current_stop].location,
                    'distance': distance,
                    'path': path
                }
            
            visited.add(current_stop)
            
            for neighbor, info in self.nodes[current_stop].neighbors.items():
                if neighbor not in visited:
                    new_distance = distance + info['distance']
                    queue.append((neighbor, new_distance, path + [neighbor]))
        
        return {'nearest_stop': None, 'distance': float('inf')}
    
    def dfs_find_routes(self, start: str, max_depth: int = 3) -> List[List[str]]:
        """Find all routes using DFS up to max_depth"""
        def dfs(current: str, path: List, depth: int, result: List):
            if depth > max_depth:
                return
            
            if len(path) > 1:  # Avoid single stop routes
                result.append(path.copy())
            
            visited.add(current)
            
            for neighbor in self.nodes[current].neighbors:
                if neighbor not in visited:
                    dfs(neighbor, path + [neighbor], depth + 1, result)
            
            visited.remove(current)
        
        visited = set()
        all_routes = []
        dfs(start, [start], 0, all_routes)
        return all_routes
    
    def has_cycle(self) -> bool:
        """Detect cycles in the graph"""
        visited = set()
        
        def dfs_detect_cycle(stop: str, parent: str) -> bool:
            visited.add(stop)
            
            for neighbor in self.nodes[stop].neighbors:
                if neighbor not in visited:
                    if dfs_detect_cycle(neighbor, stop):
                        return True
                elif neighbor != parent:
                    return True
            
            return False
        
        for stop in self.nodes:
            if stop not in visited:
                if dfs_detect_cycle(stop, None):
                    return True
        
        return False

# ---------- Min Heap for Ticket Priority ----------
class TicketPriorityQueue:
    """Min Heap for Managing Ticket Priority"""
    def __init__(self):
        self.heap = []
        self.ticket_map = {}  # ticket_id -> (priority, ticket_data)
    
    def push(self, ticket_id: str, ticket_data: dict, priority: int) -> None:
        """Add ticket to priority queue"""
        # Priority based on: 1. Emergency, 2. Time, 3. Distance
        heapq.heappush(self.heap, (priority, ticket_id))
        self.ticket_map[ticket_id] = ticket_data
    
    def pop(self) -> Optional[dict]:
        """Get highest priority ticket"""
        if not self.heap:
            return None
        
        priority, ticket_id = heapq.heappop(self.heap)
        ticket_data = self.ticket_map.pop(ticket_id, None)
        
        return {
            'ticket_id': ticket_id,
            'priority': priority,
            'data': ticket_data
        }
    
    def peek(self) -> Optional[dict]:
        """Peek highest priority ticket without removing"""
        if not self.heap:
            return None
        
        priority, ticket_id = self.heap[0]
        ticket_data = self.ticket_map.get(ticket_id)
        
        return {
            'ticket_id': ticket_id,
            'priority': priority,
            'data': ticket_data
        }
    
    def update_priority(self, ticket_id: str, new_priority: int) -> bool:
        """Update priority of existing ticket"""
        if ticket_id not in self.ticket_map:
            return False
        
        # Remove old entry
        for i, (priority, t_id) in enumerate(self.heap):
            if t_id == ticket_id:
                self.heap[i] = self.heap[-1]
                self.heap.pop()
                heapq.heapify(self.heap)
                break
        
        # Add with new priority
        heapq.heappush(self.heap, (new_priority, ticket_id))
        return True
    
    def size(self) -> int:
        return len(self.heap)

# ---------- Linked List for Booking History ----------
class HistoryNode:
    """Node for Booking History Linked List"""
    def __init__(self, booking_data: dict):
        self.data = booking_data
        self.next = None
        self.prev = None

class BookingHistory:
    """Doubly Linked List for Booking History"""
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0
    
    def add_booking(self, booking_data: dict) -> None:
        """Add booking to history"""
        new_node = HistoryNode(booking_data)
        
        if not self.head:
            self.head = new_node
            self.tail = new_node
        else:
            new_node.next = self.head
            self.head.prev = new_node
            self.head = new_node
        
        self.size += 1
    
    def get_recent_bookings(self, count: int = 10) -> List[dict]:
        """Get most recent bookings"""
        bookings = []
        current = self.head
        
        while current and len(bookings) < count:
            bookings.append(current.data)
            current = current.next
        
        return bookings
    
    def get_all_bookings(self) -> List[dict]:
        """Get all bookings in chronological order"""
        bookings = []
        current = self.head
        
        while current:
            bookings.append(current.data)
            current = current.next
        
        return bookings
    
    def search_by_ticket(self, ticket_id: str) -> Optional[dict]:
        """Search booking by ticket ID"""
        current = self.head
        
        while current:
            if current.data.get('ticket_id') == ticket_id:
                return current.data
            current = current.next
        
        return None
    
    def search_by_date(self, date: str) -> List[dict]:
        """Search bookings by date"""
        bookings = []
        current = self.head
        
        while current:
            if current.data.get('booking_date') == date:
                bookings.append(current.data)
            current = current.next
        
        return bookings

# ===================== DATA CLASSES =====================
@dataclass
class Ticket:
    """Ticket Data Class"""
    ticket_id: str
    passenger_id: str
    passenger_name: str
    passenger_contact: str
    bus_number: str
    route_id: str
    route_name: str
    from_stop: str
    to_stop: str
    departure_time: str
    arrival_time: str
    travel_date: str
    seat_number: int
    fare: float
    booking_time: str
    status: str = "confirmed"
    qr_code: str = None
    payment_status: str = "pending"
    
    def to_dict(self):
        return asdict(self)

@dataclass
class BusSchedule:
    """Bus Schedule Data Class"""
    bus_number: str
    route_id: str
    departure_time: str
    arrival_time: str
    capacity: int
    available_seats: int
    status: str  # on-time, delayed, cancelled
    driver_name: str
    driver_contact: str

# ===================== MAIN BOOKING SYSTEM =====================
class PassengerBookingSystem:
    """Main Booking System for Passengers"""
    def __init__(self, buses_file: str = 'data/buses.json', routes_file: str = 'data/routes.json'):
        self.buses_file = buses_file
        self.routes_file = routes_file
        
        # Initialize data structures
        self.passenger_bst = PassengerBST()
        self.transport_graph = TransportGraph()
        self.ticket_queue = TicketPriorityQueue()
        self.booking_history = BookingHistory()
        
        # Load data
        self.buses = self._load_json(buses_file)
        self.routes = self._load_json(routes_file)
        
        # Ticket counter
        self.ticket_counter = 1000
        
        # Initialize graph from routes
        self._build_transport_graph()
        
        # Load existing tickets
        self.tickets = self._load_tickets()
        
        # Booked seats tracking
        self.booked_seats = {}  # {bus_number_date: set(seat_numbers)}
    
    def _load_json(self, filename: str) -> Dict:
        """Load JSON file"""
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
    
    def _save_json(self, data: Dict, filename: str) -> bool:
        """Save data to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving to {filename}: {e}")
            return False
    
    def _load_tickets(self) -> Dict:
        """Load tickets from file"""
        try:
            with open('data/tickets.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'tickets': [], 'next_id': 1000}
    
    def _save_tickets(self) -> bool:
        """Save tickets to file"""
        try:
            with open('data/tickets.json', 'w') as f:
                json.dump(self.tickets, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving tickets: {e}")
            return False
    
    def _build_transport_graph(self) -> None:
        """Build transport graph from routes data"""
        if 'routes' not in self.routes:
            return
        
        for route in self.routes['routes']:
            stops = route.get('stops', [])
            route_id = route.get('route_id', '')
            route_name = route.get('route_name', '')
            
            # Add stops to graph
            for stop in stops:
                stop_name = stop.get('stop_name', '')
                location = stop.get('location', '')
                self.transport_graph.add_stop(
                    stop_name=stop_name,
                    location=location
                )
            
            # Add connections between consecutive stops
            for i in range(len(stops) - 1):
                stop1 = stops[i].get('stop_name', '')
                stop2 = stops[i + 1].get('stop_name', '')
                wait_time = stops[i].get('wait_time', 5)
                
                # Add connection with travel time (estimated 5 minutes between stops + wait time)
                self.transport_graph.add_connection(
                    stop1=stop1,
                    stop2=stop2,
                    distance=5.0,  # Estimated 5km between stops
                    time_minutes=5 + wait_time
                )
    
    # ===================== PASSENGER MANAGEMENT =====================
    def register_passenger(self, passenger_data: Dict) -> Dict:
        """Register new passenger in BST"""
        passenger_id = str(uuid.uuid4())[:8]
        
        passenger_record = {
            'passenger_id': passenger_id,
            'full_name': passenger_data.get('full_name', ''),
            'email': passenger_data.get('email', ''),
            'phone': passenger_data.get('phone', ''),
            'address': passenger_data.get('address', ''),
            'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_bookings': 0,
            'total_spent': 0.0
        }
        
        # Insert into BST
        self.passenger_bst.insert(passenger_id, passenger_record)
        
        return {
            'success': True,
            'passenger_id': passenger_id,
            'message': 'Passenger registered successfully'
        }
    
    def search_passenger(self, passenger_id: str) -> Optional[Dict]:
        """Search passenger using BST O(log n)"""
        return self.passenger_bst.search(passenger_id)
    
    def get_passenger_travel_history(self, passenger_id: str) -> List[Dict]:
        """Get passenger's travel history"""
        # Search through booking history
        history = []
        all_bookings = self.booking_history.get_all_bookings()
        
        for booking in all_bookings:
            if booking.get('passenger_id') == passenger_id:
                history.append(booking)
        
        return history
    
    def update_passenger_stats(self, passenger_id: str, fare: float) -> None:
        """Update passenger statistics after booking"""
        passenger = self.passenger_bst.search(passenger_id)
        
        if passenger:
            passenger['total_bookings'] += 1
            passenger['total_spent'] += fare
    
    # ===================== TICKET BOOKING =====================
    def get_available_buses(self, from_stop: str, to_stop: str, date: str) -> List[Dict]:
        """Get available buses for a route on specific date"""
        available_buses = []
        
        if 'buses' not in self.buses:
            return available_buses
        
        current_time = datetime.now()
        travel_datetime = datetime.strptime(f"{date} 00:00", "%Y-%m-%d %H:%M")
        
        for bus in self.buses['buses']:
            # Check if bus is active and has route
            if bus.get('status') != 'active':
                continue
            
            route_name = bus.get('route_name', '')
            if not route_name:
                continue
            
            # Find route details
            route = None
            for r in self.routes.get('routes', []):
                if r.get('route_name') == route_name:
                    route = r
                    break
            
            if not route:
                continue
            
            # Check if route has both stops
            stops = [s['stop_name'] for s in route.get('stops', [])]
            if from_stop not in stops or to_stop not in stops:
                continue
            
            # Check if from_stop comes before to_stop
            from_idx = stops.index(from_stop)
            to_idx = stops.index(to_stop)
            
            if from_idx >= to_idx:
                continue
            
            # Calculate available seats
            bus_key = f"{bus['bus_number']}_{date}"
            booked_seats = self.booked_seats.get(bus_key, set())
            available_seats = bus.get('capacity', 50) - len(booked_seats)
            
            # Calculate departure and arrival times
            departure_time = self._calculate_departure_time(stops, from_stop)
            arrival_time = self._calculate_arrival_time(stops, from_stop, to_stop, departure_time)
            
            bus_info = {
                'bus_number': bus['bus_number'],
                'plate_number': bus['plate_number'],
                'driver_name': bus['driver_name'],
                'driver_contact': bus.get('driver_contact', ''),
                'capacity': bus['capacity'],
                'available_seats': available_seats,
                'type': bus.get('type', 'regular'),
                'route_name': route_name,
                'route_id': route.get('route_id', ''),
                'from_stop': from_stop,
                'to_stop': to_stop,
                'departure_time': departure_time,
                'arrival_time': arrival_time,
                'estimated_travel_time': self._calculate_travel_time(stops, from_idx, to_idx),
                'fare': self._calculate_fare(from_idx, to_idx, bus.get('type', 'regular'))
            }
            
            available_buses.append(bus_info)
        
        # Sort by departure time
        available_buses.sort(key=lambda x: x['departure_time'])
        
        return available_buses
    
    def _calculate_departure_time(self, stops: List[str], from_stop: str) -> str:
        """Calculate departure time from a stop"""
        # Base departure at 08:00 from first stop
        base_time = datetime.strptime("08:00", "%H:%M")
        
        if from_stop in stops:
            index = stops.index(from_stop)
            # Add 10 minutes for each stop before
            departure_time = base_time + timedelta(minutes=index * 10)
            return departure_time.strftime("%H:%M")
        
        return "08:00"
    
    def _calculate_arrival_time(self, stops: List[str], from_stop: str, to_stop: str, departure: str) -> str:
        """Calculate arrival time"""
        if from_stop in stops and to_stop in stops:
            from_idx = stops.index(from_stop)
            to_idx = stops.index(to_stop)
            
            # 10 minutes travel + 2 minutes wait per stop
            travel_minutes = (to_idx - from_idx) * 12
            
            departure_time = datetime.strptime(departure, "%H:%M")
            arrival_time = departure_time + timedelta(minutes=travel_minutes)
            
            return arrival_time.strftime("%H:%M")
        
        return "09:00"
    
    def _calculate_travel_time(self, stops: List[str], from_idx: int, to_idx: int) -> str:
        """Calculate travel time between stops"""
        travel_minutes = (to_idx - from_idx) * 12
        hours = travel_minutes // 60
        minutes = travel_minutes % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    
    def _calculate_fare(self, from_idx: int, to_idx: int, bus_type: str) -> float:
        """Calculate fare based on distance and bus type"""
        distance = to_idx - from_idx
        base_fare = 50
        
        # Distance-based fare
        fare = base_fare + (distance * 10)
        
        # Bus type multiplier
        if bus_type == 'air_conditioned':
            fare *= 1.5
        elif bus_type == 'luxury':
            fare *= 2.0
        
        return round(fare, 2)
    
    def book_ticket(self, booking_data: Dict) -> Dict:
        """Book a new ticket"""
        # Generate ticket ID
        ticket_id = f"TKT{self.ticket_counter:06d}"
        self.ticket_counter += 1
        
        # Get bus details
        bus_number = booking_data.get('bus_number')
        travel_date = booking_data.get('travel_date')
        from_stop = booking_data.get('from_stop')
        to_stop = booking_data.get('to_stop')
        
        # Find bus
        bus = None
        for b in self.buses.get('buses', []):
            if b['bus_number'] == bus_number:
                bus = b
                break
        
        if not bus:
            return {'success': False, 'message': 'Bus not found'}
        
        # Get route
        route = None
        for r in self.routes.get('routes', []):
            if r.get('route_name') == bus.get('route_name'):
                route = r
                break
        
        if not route:
            return {'success': False, 'message': 'Route not found'}
        
        # Calculate fare
        stops = [s['stop_name'] for s in route.get('stops', [])]
        from_idx = stops.index(from_stop) if from_stop in stops else 0
        to_idx = stops.index(to_stop) if to_stop in stops else len(stops)-1
        fare = self._calculate_fare(from_idx, to_idx, bus.get('type', 'regular'))
        
        # Assign seat
        bus_key = f"{bus_number}_{travel_date}"
        if bus_key not in self.booked_seats:
            self.booked_seats[bus_key] = set()
        
        seat_number = 1
        while seat_number <= bus['capacity']:
            if seat_number not in self.booked_seats[bus_key]:
                self.booked_seats[bus_key].add(seat_number)
                break
            seat_number += 1
        
        if seat_number > bus['capacity']:
            return {'success': False, 'message': 'No seats available'}
        
        # Calculate timings
        departure_time = self._calculate_departure_time(stops, from_stop)
        arrival_time = self._calculate_arrival_time(stops, from_stop, to_stop, departure_time)
        
        # Create ticket
        ticket = Ticket(
            ticket_id=ticket_id,
            passenger_id=booking_data.get('passenger_id', ''),
            passenger_name=booking_data.get('passenger_name', ''),
            passenger_contact=booking_data.get('passenger_contact', ''),
            bus_number=bus_number,
            route_id=route.get('route_id', ''),
            route_name=route.get('route_name', ''),
            from_stop=from_stop,
            to_stop=to_stop,
            departure_time=departure_time,
            arrival_time=arrival_time,
            travel_date=travel_date,
            seat_number=seat_number,
            fare=fare,
            booking_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            qr_code=self._generate_qr_code(ticket_id),
            payment_status='paid'
        )
        
        # Add to tickets data
        ticket_dict = ticket.to_dict()
        
        if 'tickets' not in self.tickets:
            self.tickets['tickets'] = []
        
        self.tickets['tickets'].append(ticket_dict)
        self.tickets['next_id'] = self.ticket_counter
        
        # Add to booking history (Linked List)
        self.booking_history.add_booking(ticket_dict)
        
        # Add to priority queue (emergency tickets get higher priority)
        priority = 100 if booking_data.get('emergency', False) else 10
        self.ticket_queue.push(ticket_id, ticket_dict, priority)
        
        # Update passenger statistics
        self.update_passenger_stats(booking_data.get('passenger_id', ''), fare)
        
        # Update bus passenger count
        self._update_bus_passenger_count(bus_number, 1)
        
        # Save data
        self._save_tickets()
        
        # Generate downloadable ticket
        download_path = self._generate_ticket_download(ticket)
        
        return {
            'success': True,
            'ticket_id': ticket_id,
            'ticket': ticket_dict,
            'download_url': download_path,
            'message': 'Ticket booked successfully'
        }
    
    def _update_bus_passenger_count(self, bus_number: str, change: int) -> None:
        """Update passenger count for a bus"""
        if 'buses' in self.buses:
            for bus in self.buses['buses']:
                if bus['bus_number'] == bus_number:
                    bus['current_passengers'] = bus.get('current_passengers', 0) + change
                    bus['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    break
            
            # Save updated buses
            self._save_json(self.buses, self.buses_file)
    
    def _generate_qr_code(self, ticket_id: str) -> str:
        """Generate QR code data (simulated)"""
        return f"BUS:{ticket_id}:{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def _generate_ticket_download(self, ticket: Ticket) -> str:
        """Generate downloadable ticket file"""
        filename = f"tickets/ticket_{ticket.ticket_id}.txt"
        
        # Create tickets directory if not exists
        import os
        os.makedirs('tickets', exist_ok=True)
        
        ticket_content = f"""
========================================
        BUS TICKET
========================================
Ticket ID: {ticket.ticket_id}
Booking Date: {ticket.booking_time}
Status: {ticket.status}
----------------------------------------
PASSENGER INFORMATION
Name: {ticket.passenger_name}
Contact: {ticket.passenger_contact}
----------------------------------------
JOURNEY DETAILS
From: {ticket.from_stop}
To: {ticket.to_stop}
Date: {ticket.travel_date}
----------------------------------------
BUS DETAILS
Bus Number: {ticket.bus_number}
Route: {ticket.route_name}
Seat Number: {ticket.seat_number}
----------------------------------------
TIMINGS
Departure: {ticket.departure_time}
Arrival: {ticket.arrival_time}
----------------------------------------
FARE: Rs. {ticket.fare}
Payment Status: {ticket.payment_status}
----------------------------------------
QR Code: {ticket.qr_code}
========================================
Important:
1. Please arrive at the stop 10 minutes before departure
2. Keep this ticket for verification
3. Contact 0800-12345 for assistance
========================================
"""
        
        with open(filename, 'w') as f:
            f.write(ticket_content)
        
        return filename
    
    # ===================== ROUTE PLANNING =====================
    def find_shortest_route(self, from_stop: str, to_stop: str, criteria: str = 'time') -> Dict:
        """Find shortest route using Dijkstra's algorithm"""
        return self.transport_graph.dijkstra_shortest_path(from_stop, to_stop, criteria)
    
    def find_nearest_stop(self, location: str) -> Dict:
        """Find nearest bus stop to a location"""
        # Use BFS to find nearest stop with matching location
        if not self.transport_graph.nodes:
            return {'nearest_stop': None, 'distance': float('inf')}
        
        # Start from first node
        start_node = list(self.transport_graph.nodes.keys())[0]
        return self.transport_graph.bfs_nearest_stop(start_node, location)
    
    def find_all_routes(self, start_stop: str, max_depth: int = 3) -> List[List[str]]:
        """Find all possible routes from a stop using DFS"""
        return self.transport_graph.dfs_find_routes(start_stop, max_depth)
    
    def check_route_cycle(self) -> bool:
        """Check if transport network has cycles"""
        return self.transport_graph.has_cycle()
    
    # ===================== TICKET MANAGEMENT =====================
    def cancel_ticket(self, ticket_id: str) -> Dict:
        """Cancel a booked ticket"""
        ticket_found = False
        
        for i, ticket in enumerate(self.tickets.get('tickets', [])):
            if ticket['ticket_id'] == ticket_id:
                # Update status
                ticket['status'] = 'cancelled'
                ticket['cancellation_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Free up seat
                bus_key = f"{ticket['bus_number']}_{ticket['travel_date']}"
                if bus_key in self.booked_seats and ticket['seat_number'] in self.booked_seats[bus_key]:
                    self.booked_seats[bus_key].remove(ticket['seat_number'])
                
                # Update bus passenger count
                self._update_bus_passenger_count(ticket['bus_number'], -1)
                
                # Update priority queue
                self.ticket_queue.update_priority(ticket_id, 0)  # Lowest priority for cancelled
                
                ticket_found = True
                break
        
        if ticket_found:
            self._save_tickets()
            return {'success': True, 'message': 'Ticket cancelled successfully'}
        
        return {'success': False, 'message': 'Ticket not found'}
    
    def get_ticket_details(self, ticket_id: str) -> Optional[Dict]:
        """Get details of a specific ticket"""
        for ticket in self.tickets.get('tickets', []):
            if ticket['ticket_id'] == ticket_id:
                return ticket
        
        return None
    
    def get_passenger_tickets(self, passenger_id: str) -> List[Dict]:
        """Get all tickets for a passenger"""
        passenger_tickets = []
        
        for ticket in self.tickets.get('tickets', []):
            if ticket.get('passenger_id') == passenger_id:
                passenger_tickets.append(ticket)
        
        return passenger_tickets
    
    def get_priority_ticket(self) -> Optional[Dict]:
        """Get highest priority ticket"""
        return self.ticket_queue.peek()
    
    # ===================== STATISTICS =====================
    def get_system_statistics(self) -> Dict:
        """Get system statistics"""
        total_tickets = len(self.tickets.get('tickets', []))
        active_tickets = len([t for t in self.tickets.get('tickets', []) if t.get('status') == 'confirmed'])
        cancelled_tickets = len([t for t in self.tickets.get('tickets', []) if t.get('status') == 'cancelled'])
        
        total_revenue = sum(t.get('fare', 0) for t in self.tickets.get('tickets', []) 
                          if t.get('status') == 'confirmed' and t.get('payment_status') == 'paid')
        
        total_passengers = len(self.passenger_bst.get_all_passengers())
        
        return {
            'total_tickets': total_tickets,
            'active_tickets': active_tickets,
            'cancelled_tickets': cancelled_tickets,
            'total_revenue': round(total_revenue, 2),
            'total_passengers': total_passengers,
            'priority_queue_size': self.ticket_queue.size(),
            'booking_history_size': self.booking_history.size,
            'transport_nodes': len(self.transport_graph.nodes),
            'average_fare': round(total_revenue / active_tickets, 2) if active_tickets > 0 else 0
        }
