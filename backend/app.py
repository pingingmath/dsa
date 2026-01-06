from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from flask_cors import CORS
import json
import os
from datetime import datetime
from dsa_structures.users import UserManager, User
from dsa_structures.utils import DataHandler, Stack
from dsa_structures.routes import RouteManager
from dsa_structures.linked_list import LinkedList
from dsa_structures.passenger_routes import PassengerBookingSystem
from dsa_structures.passenger_tickets import RoutePlanner, TicketStore, BusStore
import heapq
from datetime import time, timedelta
import uuid

app = Flask(__name__, 
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
app.secret_key = 'your-secret-key-here-change-in-production'
CORS(app)

# Initialize data handlers
data_dir = os.path.join(os.path.dirname(__file__), 'data')
users_file = os.path.join(data_dir, 'users.json')
config_file = os.path.join(data_dir, 'config.json')

sim_file = os.path.join(data_dir, 'sim_distances.json')
journeys_file = os.path.join(data_dir, 'journeys.json')


# Ensure data directory exists
os.makedirs(data_dir, exist_ok=True)

# Initialize data structures
user_manager = UserManager(users_file)

# Admin credentials (hardcoded as per requirements)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_EMAIL = "admin@transport.com"
ADMIN_PHONE = "0000000000"

routes_file = os.path.join(data_dir, 'routes.json')
route_manager = RouteManager(routes_file)
ticket_store = TicketStore(os.path.join(data_dir, 'tickets.json'))
route_planner = RoutePlanner(routes_file)
bus_store = BusStore(os.path.join(data_dir, 'buses.json'))


def _sim_init_file():
    """Ensure sim_distances.json exists"""
    try:
        if not os.path.exists(sim_file):
            os.makedirs(os.path.dirname(sim_file), exist_ok=True)
            with open(sim_file, "w", encoding="utf-8") as f:
                json.dump({"route_distances": {}, "last_updated": None}, f, indent=2)
    except Exception as e:
        print("SIM init error:", e)

def _sim_read():
    _sim_init_file()
    with open(sim_file, "r", encoding="utf-8") as f:
        return json.load(f)

def _sim_write(data):
    os.makedirs(os.path.dirname(sim_file), exist_ok=True)
    tmp = sim_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, sim_file)

def _journey_init_file():
    if not os.path.exists(journeys_file):
        os.makedirs(os.path.dirname(journeys_file), exist_ok=True)
        with open(journeys_file, "w", encoding="utf-8") as f:
            json.dump({"journeys": []}, f, indent=2)

def _journey_read():
    _journey_init_file()
    return _read_json_file(journeys_file, {"journeys": []})

def _journey_write(data):
    os.makedirs(os.path.dirname(journeys_file), exist_ok=True)
    tmp = journeys_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, journeys_file)

def _journey_total_distance(segments):
    return sum(float(segment.get("distance") or 0) for segment in segments)

def _journey_position(segments, distance_covered):
    remaining = max(distance_covered, 0.0)
    for index, segment in enumerate(segments):
        segment_distance = float(segment.get("distance") or 0)
        if remaining <= segment_distance:
            progress = 0.0 if segment_distance == 0 else remaining / segment_distance
            return {
                "segment_index": index,
                "from": segment.get("from"),
                "to": segment.get("to"),
                "segment_progress": progress,
            }
        remaining -= segment_distance
    last = segments[-1] if segments else None
    return {
        "segment_index": len(segments) - 1,
        "from": last.get("from") if last else None,
        "to": last.get("to") if last else None,
        "segment_progress": 1.0,
    }
def _load_routes_raw():
    """Read your existing routes.json schema safely"""
    if not os.path.exists(routes_file):
        return {"routes": [], "total_routes": 0, "last_updated": None}
    with open(routes_file, "r", encoding="utf-8") as f:
        return json.load(f)

def _read_json_file(file_path, default):
    if not os.path.exists(file_path):
        return default
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json_file(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _load_buses_raw():
    data = _read_json_file(buses_file, [])
    if isinstance(data, dict):
        return data.get("buses", [])
    return data

def _bus_route_counts(buses):
    counts = {}
    name_counts = {}
    for bus in buses:
        route_id = str(bus.get("route_id") or "").strip()
        route_name = str(bus.get("route_name") or "").strip()
        if route_id:
            counts[route_id] = counts.get(route_id, 0) + 1
        if route_name:
            name_counts[route_name] = name_counts.get(route_name, 0) + 1
    return counts, name_counts

def _traffic_level(bus_count):
    if bus_count > 1:
        return "high"
    if bus_count == 1:
        return "medium"
    return "low"

def _update_bus_passengers(bus_number, delta):
    data = _read_json_file(buses_file, [])
    buses = data.get("buses", []) if isinstance(data, dict) else data
    updated = False
    for bus in buses:
        if str(bus.get("bus_number")) == str(bus_number):
            current = int(bus.get("current_passengers") or 0)
            bus["current_passengers"] = max(0, current + delta)
            updated = True
            break
    if updated:
        if isinstance(data, dict):
            data["buses"] = buses
        else:
            data = buses
        _write_json_file(buses_file, data)
    return updated

def _record_action(file_path, before, after, description):
    action_history.push({
        "file": file_path,
        "before": before,
        "after": after,
        "description": description,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    redo_history.clear()

def _reload_managers(file_path):
    global bus_manager
    if file_path == routes_file:
        route_manager.load_routes()
        route_planner.reload()
    elif file_path == buses_file:
        bus_manager = BusManager(buses_file)

def _unique_stops_from_routes(routes_data):
    stops = []
    for r in routes_data.get("routes", []):
        for s in r.get("stops", []):
            name = (s.get("stop_name") or "").strip()
            if name and name not in stops:
                stops.append(name)
    return stops
def _build_weighted_graph(routes_data, default_weight=1.0):
    """
    Undirected weighted graph from routes.json.
    Edge between consecutive stops in a route.

    Weight priority:
      1) distance_from_previous in routes.json stop schema
      2) fallback default_weight
    """
    graph = {}  # node -> {neighbor: weight}
    edges = []
    seen = set()

    def add_edge(a, b, w):
        graph.setdefault(a, {})
        graph.setdefault(b, {})
        prev = graph[a].get(b)
        if prev is None or w < prev:
            graph[a][b] = w
            graph[b][a] = w

    for r in routes_data.get("routes", []):
        rid = r.get("route_id")
        stop_dicts = _route_stop_dicts(r)
        stops = [(s.get("stop_name") or "").strip() for s in stop_dicts]
        if len(stops) < 2:
            continue

        for i in range(len(stops) - 1):
            a, b = stops[i], stops[i + 1]

            # 1) preferred: routes.json schema
            w = None
            if i + 1 < len(stop_dicts):
                w = _safe_distance(stop_dicts[i + 1].get("distance_from_previous"), None)

            # 2) fallback
            if w is None:
                w = default_weight

            add_edge(a, b, w)

            k = tuple(sorted((a, b)))
            if k not in seen:
                seen.add(k)
                edges.append({
                    "from": a,
                    "to": b,
                    "w": w,
                    "route_id": rid,
                    "route_name": r.get("route_name"),
                })

    return graph, edges

def _dijkstra(graph, start, end):
    """Dijkstra for shortest path + settled order animation support"""
    import heapq

    if start not in graph or end not in graph:
        return {"path": [], "distance": None, "settled_order": []}

    dist = {n: float("inf") for n in graph}
    prev = {n: None for n in graph}
    dist[start] = 0.0

    pq = [(0.0, start)]
    visited = set()
    settled_order = []

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        settled_order.append(u)

        if u == end:
            break

        for v, w in graph[u].items():
            if v in visited:
                continue
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if dist[end] == float("inf"):
        return {"path": [], "distance": None, "settled_order": settled_order}

    # reconstruct
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()

    return {"path": path, "distance": dist[end], "settled_order": settled_order}

# ==================== BUS MANAGEMENT DSA STRUCTURES ====================

class BusNode:
    """Node for Doubly Linked List Bus Management"""
    def __init__(self, bus_data):
        self.bus_data = bus_data
        self.next = None
        self.prev = None

class DoublyLinkedListBus:
    """Doubly Linked List for Bus Management"""
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0
    
    def add_bus(self, bus_data):
        """Add bus to the end of the list"""
        new_node = BusNode(bus_data)
        
        if not self.head:
            self.head = new_node
            self.tail = new_node
        else:
            self.tail.next = new_node
            new_node.prev = self.tail
            self.tail = new_node
        
        self.size += 1
        return new_node
    
    def remove_bus(self, bus_id):
        """Remove bus by ID"""
        current = self.head
        
        while current:
            if current.bus_data['id'] == bus_id:
                if current.prev:
                    current.prev.next = current.next
                else:
                    self.head = current.next
                
                if current.next:
                    current.next.prev = current.prev
                else:
                    self.tail = current.prev
                
                self.size -= 1
                return True
            
            current = current.next
        
        return False
    
    def find_bus(self, bus_id):
        """Find bus by ID"""
        current = self.head
        
        while current:
            if current.bus_data['id'] == bus_id:
                return current
            current = current.next
        
        return None
    
    def update_bus(self, bus_id, updated_data):
        """Update bus information"""
        bus_node = self.find_bus(bus_id)
        
        if bus_node:
            bus_node.bus_data.update(updated_data)
            bus_node.bus_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True
        
        return False
    
    def get_all_buses(self):
        """Get all buses as list"""
        buses = []
        current = self.head
        
        while current:
            buses.append(current.bus_data)
            current = current.next
        
        return buses
    
    def filter_by_status(self, status):
        """Filter buses by status"""
        buses = []
        current = self.head
        
        while current:
            if current.bus_data.get('status') == status:
                buses.append(current.bus_data)
            current = current.next
        
        return buses
    
    def filter_by_route(self, route_id):
        """Filter buses by route"""
        buses = []
        current = self.head
        
        while current:
            if current.bus_data.get('route_id') == route_id:
                buses.append(current.bus_data)
            current = current.next
        
        return buses

class MinHeapBusArrival:
    """Min Heap for Earliest Arriving Buses"""
    def __init__(self):
        self.heap = []
    
    def push(self, bus):
        """Add bus to min heap based on arrival time"""
        arrival_time = self._parse_time(bus['next_arrival'])
        heapq.heappush(self.heap, (arrival_time, bus))
    
    def pop(self):
        """Get earliest arriving bus"""
        if self.heap:
            return heapq.heappop(self.heap)[1]
        return None
    
    def peek(self):
        """Peek earliest arriving bus without removing"""
        if self.heap:
            return self.heap[0][1]
        return None
    
    def update_arrival(self, bus_id, new_arrival):
        """Update bus arrival time"""
        new_heap = []
        for arrival, bus in self.heap:
            if bus['id'] == bus_id:
                bus['next_arrival'] = new_arrival
                arrival = self._parse_time(new_arrival)
            heapq.heappush(new_heap, (arrival, bus))
        
        self.heap = new_heap
    
    def rebuild_heap(self, buses):
        """Rebuild heap with new bus list"""
        self.heap = []
        for bus in buses:
            self.push(bus)
    
    def _parse_time(self, time_str):
        """Parse time string to time object"""
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except:
            return datetime.strptime("08:00", "%H:%M").time()
    
    def get_all_buses_sorted(self):
        """Get all buses sorted by arrival time"""
        sorted_buses = []
        temp_heap = self.heap.copy()
        
        while temp_heap:
            sorted_buses.append(heapq.heappop(temp_heap)[1])
        
        return sorted_buses

class MaxHeapBusPriority:
    """Max Heap for Peak Hour Priority"""
    def __init__(self):
        self.heap = []
    
    def push(self, bus):
        """Add bus to max heap based on priority score"""
        priority_score = self._calculate_priority_score(bus)
        heapq.heappush(self.heap, (-priority_score, bus))
    
    def pop(self):
        """Get highest priority bus"""
        if self.heap:
            return heapq.heappop(self.heap)[1]
        return None
    
    def peek(self):
        """Peek highest priority bus without removing"""
        if self.heap:
            return self.heap[0][1]
        return None
    
    def _calculate_priority_score(self, bus):
        """Calculate priority score for bus"""
        score = 0
        
        try:
            # Arrival time factor
            arrival_time = datetime.strptime(bus.get('next_arrival', '08:00'), "%H:%M").time()
            
            # Peak hours weight (7-9 AM, 5-7 PM)
            if (time(7, 0) <= arrival_time <= time(9, 0)) or \
               (time(17, 0) <= arrival_time <= time(19, 0)):
                score += 50
            
            # Route demand factor
            score += bus.get('route_demand', 0)
            
            # Bus capacity factor
            score += bus.get('capacity', 50) / 10
            
            # Current load factor
            capacity = bus.get('capacity', 50)
            current_passengers = bus.get('current_passengers', 0)
            if capacity > 0:
                load_percentage = (current_passengers / capacity) * 100
                if load_percentage > 80:
                    score += 30
                elif load_percentage > 60:
                    score += 20
        except:
            pass
        
        return score
    
    def rebuild_heap(self, buses):
        """Rebuild heap with new bus list"""
        self.heap = []
        for bus in buses:
            self.push(bus)

class BusManager:
    """Main Bus Management System"""
    def __init__(self, data_file='data/buses.json'):
        self.data_file = data_file
        self.bus_list = DoublyLinkedListBus()
        self.min_heap_arrival = MinHeapBusArrival()
        self.max_heap_priority = MaxHeapBusPriority()
        self.load_data()
    
    def load_data(self):
        """Load bus data from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    buses = json.load(f)
                    for bus in buses:
                        self.bus_list.add_bus(bus)
                        self.min_heap_arrival.push(bus)
                        self.max_heap_priority.push(bus)
        except Exception as e:
            print(f"Error loading bus data: {e}")
            self.save_data()
    
    def save_data(self):
        """Save bus data to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            buses = self.bus_list.get_all_buses()
            with open(self.data_file, 'w') as f:
                json.dump(buses, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving bus data: {e}")
            return False
    
    def add_bus(self, bus_data):
        """Add new bus to system"""
        # Generate new ID
        existing_buses = self.bus_list.get_all_buses()
        new_id = max([bus['id'] for bus in existing_buses], default=0) + 1
        
        bus_data['id'] = new_id
        bus_data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bus_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add to data structures
        self.bus_list.add_bus(bus_data)
        self.min_heap_arrival.push(bus_data)
        self.max_heap_priority.push(bus_data)
        
        # Save to file
        self.save_data()
        
        return bus_data
    
    def update_bus(self, bus_id, updated_data):
        """Update existing bus"""
        success = self.bus_list.update_bus(bus_id, updated_data)
        
        if success:
            # Rebuild heaps with updated data
            all_buses = self.bus_list.get_all_buses()
            self.min_heap_arrival.rebuild_heap(all_buses)
            self.max_heap_priority.rebuild_heap(all_buses)
            self.save_data()
        
        return success
    
    def delete_bus(self, bus_id):
        """Delete bus from system"""
        success = self.bus_list.remove_bus(bus_id)
        
        if success:
            # Rebuild heaps
            all_buses = self.bus_list.get_all_buses()
            self.min_heap_arrival.rebuild_heap(all_buses)
            self.max_heap_priority.rebuild_heap(all_buses)
            self.save_data()
        
        return success
    
    def allocate_bus_to_route(self, bus_id, route_id, route_name):
        """Allocate bus to specific route"""
        bus_node = self.bus_list.find_bus(bus_id)
        
        if bus_node:
            bus_node.bus_data['route_id'] = route_id
            bus_node.bus_data['route_name'] = route_name
            
            # Update demand based on route (simulated)
            bus_node.bus_data['route_demand'] = 50
            
            # Rebuild heaps
            all_buses = self.bus_list.get_all_buses()
            self.min_heap_arrival.rebuild_heap(all_buses)
            self.max_heap_priority.rebuild_heap(all_buses)
            self.save_data()
            
            return True
        
        return False
    
    def get_next_arrival(self):
        """Get next arriving bus"""
        return self.min_heap_arrival.peek()
    
    def get_priority_bus(self):
        """Get highest priority bus"""
        return self.max_heap_priority.peek()
    
    def update_bus_arrival(self, bus_id, new_arrival):
        """Update bus arrival time after movement"""
        self.min_heap_arrival.update_arrival(bus_id, new_arrival)
        
        # Also update in main list
        self.bus_list.update_bus(bus_id, {'next_arrival': new_arrival})
        
        # Rebuild priority heap (scores may change)
        all_buses = self.bus_list.get_all_buses()
        self.max_heap_priority.rebuild_heap(all_buses)
        self.save_data()
    
    def get_bus_statistics(self):
        """Get bus system statistics"""
        all_buses = self.bus_list.get_all_buses()
        
        stats = {
            'total_buses': len(all_buses),
            'active_buses': len(self.bus_list.filter_by_status('active')),
            'inactive_buses': len(self.bus_list.filter_by_status('inactive')),
            'maintenance_buses': len(self.bus_list.filter_by_status('maintenance')),
            'total_capacity': sum(bus.get('capacity', 0) for bus in all_buses),
            'average_load': 0,
            'next_arrival': 'N/A',
            'priority_bus': 'N/A'
        }
        
        if all_buses:
            total_load = sum((bus.get('current_passengers', 0) / bus.get('capacity', 1)) * 100 
                           for bus in all_buses)
            stats['average_load'] = round(total_load / len(all_buses), 1)
        
        next_bus = self.get_next_arrival()
        if next_bus:
            stats['next_arrival'] = next_bus.get('next_arrival', 'N/A')
        
        priority_bus = self.get_priority_bus()
        if priority_bus:
            stats['priority_bus'] = priority_bus.get('bus_number', 'N/A')
        
        return stats

# Initialize Bus Manager
buses_file = os.path.join(data_dir, 'buses.json')
bus_manager = BusManager(buses_file)
action_history = Stack()
redo_history = Stack()

# ==================== HELPER FUNCTIONS ====================

def load_routes_for_buses():
    """Load routes from JSON file for bus allocation - FIXED for your structure"""
    try:
        with open(routes_file, 'r') as f:
            routes_data = json.load(f)
        
        print(f"\n=== DEBUG: Loading routes ===")
        print(f"Type of routes_data: {type(routes_data)}")
        print(f"Keys in routes_data: {list(routes_data.keys())}")
        
        # Extract the routes array from the nested structure
        if isinstance(routes_data, dict) and 'routes' in routes_data:
            routes_list = routes_data['routes']
            print(f"Found 'routes' key with {len(routes_list)} routes")
        else:
            routes_list = routes_data
            print(f"No 'routes' key found, using data directly")
        
        routes = []
        for route in routes_list:
            if isinstance(route, dict):
                # Debug print each route
                print(f"\nProcessing route:")
                print(f"  route_id: {route.get('route_id')}")
                print(f"  route_name: {route.get('route_name')}")
                print(f"  total_stops: {route.get('total_stops')}")
                print(f"  id field exists: {'id' in route}")
                print(f"  name field exists: {'name' in route}")
                
                # Create route object for dropdown
                route_obj = {
                    'id': route.get('route_id'),  # Use route_id as id
                    'name': route.get('route_name'),  # Use route_name as name
                    'stops': route.get('stops', []),
                    'total_stops': route.get('total_stops', 0)
                }
                
                routes.append(route_obj)
                print(f"  Added to dropdown: ID={route_obj['id']}, Name={route_obj['name']}")
        
        print(f"\nTotal routes processed for dropdown: {len(routes)}")
        print("=== DEBUG END ===\n")
        
        return routes
        
    except FileNotFoundError:
        print(f"DEBUG: routes.json file not found at {routes_file}")
        return []
    except Exception as e:
        print(f"DEBUG: Error loading routes: {e}")
        import traceback
        traceback.print_exc()
        return []

def calculate_next_arrival(bus, current_time):
    """Calculate next arrival time based on current time and frequency"""
    try:
        if bus.get('timings'):
            last_timing = bus['timings'][-1]
            frequency = last_timing.get('frequency', '30min')
            
            if 'min' in frequency:
                minutes = int(frequency.replace('min', ''))
            elif 'hour' in frequency:
                minutes = int(frequency.replace('hour', '')) * 60
            else:
                minutes = 30
            
            current_dt = datetime.combine(datetime.today(), current_time)
            next_arrival_dt = current_dt + timedelta(minutes=minutes)
            
            return next_arrival_dt.time()
        else:
            current_dt = datetime.combine(datetime.today(), current_time)
            next_arrival_dt = current_dt + timedelta(minutes=30)
            return next_arrival_dt.time()
    except Exception as e:
        print(f"Error calculating next arrival: {e}")
        current_dt = datetime.combine(datetime.today(), current_time)
        next_arrival_dt = current_dt + timedelta(minutes=30)
        return next_arrival_dt.time()

# Initialize booking system
booking_system = PassengerBookingSystem()

# ==================== FLASK ROUTES ====================

@app.route('/')
def index():
    """Landing page route"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route for both admin and passengers"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = request.form.get('remember')
        
        # Check admin login first
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['user_type'] = 'admin'
            session['username'] = ADMIN_USERNAME
            session['email'] = ADMIN_EMAIL
            session['phone'] = ADMIN_PHONE
            session['full_name'] = 'System Administrator'
            session['user_id'] = 'admin-001'
            session['logged_in'] = True
            session['login_time'] = datetime.now().isoformat()
            
            if remember:
                session.permanent = True
            
            flash('Welcome back, Administrator!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        # Check passenger login
        user = user_manager.authenticate(username, password)
        if user:
            session['user_type'] = 'passenger'
            session['username'] = user.username
            session['email'] = user.email
            session['phone'] = user.phone
            session['full_name'] = user.full_name
            session['user_id'] = user.user_id
            session['logged_in'] = True
            session['login_time'] = datetime.now().isoformat()
            
            if remember:
                session.permanent = True
            
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('passenger_dashboard'))
        
        flash('Invalid username or password. Please try again.', 'error')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Signup route for passengers only"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', 'passenger')
        terms = request.form.get('terms')
        
        # Validation
        if not all([username, email, phone, password, confirm_password]):
            flash('All fields are required!', 'error')
            return redirect(url_for('signup'))
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('signup'))
        
        if not terms:
            flash('You must agree to the terms and conditions!', 'error')
            return redirect(url_for('signup'))
        
        # Check if username or email already exists
        if user_manager.username_exists(username):
            flash('Username already exists!', 'error')
            return redirect(url_for('signup'))
        
        if user_manager.email_exists(email):
            flash('Email already registered!', 'error')
            return redirect(url_for('signup'))
        
        # Create new user
        try:
            new_user = user_manager.create_user(
                username=username,
                email=email,
                phone=phone,
                full_name=full_name,
                password=password,
                role=role
            )
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'error')
            return redirect(url_for('signup'))
    
    return render_template('signup.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard route"""
    # Check if user is logged in and is admin
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    if session.get('user_type') != 'admin':
        flash('Access denied! Admin privileges required.', 'error')
        return redirect(url_for('passenger_dashboard'))
    
    # Get statistics from both managers
    bus_stats = bus_manager.get_bus_statistics()
    
    stats = {
        'total_passengers': user_manager.get_user_count(),
        'active_sessions': 1,  # Just the admin for now
        'system_status': 'Online',
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'admin_name': session.get('full_name', 'Administrator'),
        'total_buses': bus_stats['total_buses'],
        'active_buses': bus_stats['active_buses']
    }
    
    return render_template('admin_dashboard.html', stats=stats)

@app.route('/admin/analytics')
def admin_analytics():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'admin':
        flash('Access denied! Admin privileges required.', 'error')
        return redirect(url_for('passenger_dashboard'))

    return render_template('admin_analytics.html')


@app.route('/admin/passengers')
def admin_passengers():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'admin':
        flash('Access denied! Admin privileges required.', 'error')
        return redirect(url_for('passenger_dashboard'))

    ticket_store._load()
    tickets = ticket_store.tickets
    passengers = [u for u in user_manager.get_all_users() if u.get('role') == 'passenger']
    bus_lookup = {str(b.get('bus_number')): b for b in bus_store.list_buses()}

    ticket_rows = []
    for ticket in tickets:
        passenger = next((p for p in passengers if p.get('user_id') == ticket.get('passenger_id')), {})
        bus_number = str(ticket.get('bus_number') or '')
        bus = bus_lookup.get(bus_number, {})
        ticket_rows.append({
            "ticket_id": ticket.get("ticket_id"),
            "passenger_name": passenger.get("full_name") or ticket.get("passenger_name"),
            "passenger_email": passenger.get("email"),
            "passenger_phone": passenger.get("phone"),
            "from_stop": ticket.get("from_stop"),
            "to_stop": ticket.get("to_stop"),
            "route_path": ticket.get("path", []),
            "bus_number": bus_number,
            "bus_timing": bus.get("next_arrival") or bus.get("start_time") or ticket.get("eta"),
            "fare": ticket.get("fare"),
            "created_at": ticket.get("created_at"),
        })

    stats = {
        "total_passengers": len(passengers),
        "total_tickets": len(tickets),
    }

    return render_template(
        'admin_passengers.html',
        tickets=ticket_rows,
        stats=stats,
    )


@app.route('/admin/passengers')
def admin_passengers():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'admin':
        flash('Access denied! Admin privileges required.', 'error')
        return redirect(url_for('passenger_dashboard'))

    ticket_store._load()
    tickets = ticket_store.tickets
    passengers = [u for u in user_manager.get_all_users() if u.get('role') == 'passenger']
    bus_lookup = {str(b.get('bus_number')): b for b in bus_store.list_buses()}

    ticket_rows = []
    for ticket in tickets:
        passenger = next((p for p in passengers if p.get('user_id') == ticket.get('passenger_id')), {})
        bus_number = str(ticket.get('bus_number') or '')
        bus = bus_lookup.get(bus_number, {})
        ticket_rows.append({
            "ticket_id": ticket.get("ticket_id"),
            "passenger_name": passenger.get("full_name") or ticket.get("passenger_name"),
            "passenger_email": passenger.get("email"),
            "passenger_phone": passenger.get("phone"),
            "from_stop": ticket.get("from_stop"),
            "to_stop": ticket.get("to_stop"),
            "route_path": ticket.get("path", []),
            "bus_number": bus_number,
            "bus_timing": bus.get("next_arrival") or bus.get("start_time") or ticket.get("eta"),
            "fare": ticket.get("fare"),
            "created_at": ticket.get("created_at"),
        })

    stats = {
        "total_passengers": len(passengers),
        "total_tickets": len(tickets),
    }

    return render_template(
        'admin_passengers.html',
        tickets=ticket_rows,
        stats=stats,
    )

@app.route('/admin/simulation')
def sim_dashboard():
    """Simulation dashboard (Admin only)"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        flash('Please login as administrator first!', 'error')
        return redirect(url_for('login'))

    routes_data = _load_routes_raw()

    routes_list = []
    for r in routes_data.get("routes", []):
        rid = r.get("route_id")
        stop_dicts = _route_stop_dicts(r)
        stops = [(s.get("stop_name") or "").strip() for s in stop_dicts]

        routes_list.append({
            "route_id": rid,
            "route_name": r.get("route_name"),
            "total_stops": r.get("total_stops", len(stops)),
            "stops": stops,
            "distances": _distances_from_stop_dicts(stop_dicts),
        })

    stops = _unique_stops_from_routes(routes_data)
    return render_template('sim_dashboard.html', routes=routes_list, stops=stops)


@app.route('/api/sim/routes', methods=['GET'])
def api_sim_routes():
    """Get routes + stops + saved distances (from routes.json stop schema)."""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    routes_data = _load_routes_raw()

    out = []
    for r in routes_data.get("routes", []):
        rid = r.get("route_id")
        stop_dicts = _route_stop_dicts(r)
        stops = [(s.get("stop_name") or "").strip() for s in stop_dicts]

        out.append({
            "route_id": rid,
            "route_name": r.get("route_name"),
            "stops": stops,
            "distances": _distances_from_stop_dicts(stop_dicts),
        })

    return jsonify({"success": True, "routes": out})

def _safe_distance(x, default=1.0):
    try:
        v = float(x)
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


def _route_stop_dicts(route_obj):
    """Return only valid stop dicts with a stop_name."""
    stop_dicts = []
    for s in (route_obj.get("stops", []) or []):
        if isinstance(s, dict) and (s.get("stop_name") or "").strip():
            stop_dicts.append(s)
    return stop_dicts


def _distances_from_stop_dicts(stop_dicts):
    """
    distances[i-1] = distance_from_previous for stop i (i starts at 1).
    stop 0 is the first stop and has no distance_from_previous.
    """
    distances = []
    for i in range(1, len(stop_dicts)):
        distances.append(_safe_distance(stop_dicts[i].get("distance_from_previous", 1.0), 1.0))
    return distances

@app.route('/api/sim/routes/<route_id>/distances', methods=['POST'])
def api_sim_set_distances(route_id):
    """Save distances into routes.json stop schema (distance_from_previous)."""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    payload = request.get_json(force=True, silent=True) or {}
    distances = payload.get("distances", [])

    if not isinstance(distances, list) or len(distances) == 0:
        return jsonify({"error": "distances must be a non-empty list"}), 400

    clean = []
    for d in distances:
        try:
            dd = float(d)
            if dd <= 0:
                return jsonify({"error": "All distances must be > 0"}), 400
            clean.append(dd)
        except:
            return jsonify({"error": "All distances must be numeric"}), 400

    # Ensure RouteManager has the route loaded
    if route_id not in route_manager.routes:
        route_manager.load_routes()

    route = route_manager.routes.get(route_id)
    if not route:
        return jsonify({"error": f"Route '{route_id}' not found"}), 404

    if len(route) < 2:
        return jsonify({"error": "Route must have at least 2 stops"}), 400

    if len(clean) != (len(route) - 1):
        return jsonify({"error": f"This route needs exactly {len(route) - 1} distances"}), 400

    now = datetime.now().isoformat()

    # Force first stop distance = 0
    s1 = route.get_at(1)
    if isinstance(s1, dict):
        s1["distance_from_previous"] = 0.0
        s1["updated_at"] = now
        route.update_at(1, s1)

    # Apply distances to stops 2..n (distance from previous)
    for pos in range(2, len(route) + 1):
        s = route.get_at(pos)
        if not isinstance(s, dict):
            s = {}
        s["distance_from_previous"] = clean[pos - 2]
        s["updated_at"] = now
        route.update_at(pos, s)

    route_manager.save_routes()

    return jsonify({"success": True, "route_id": route_id, "distances": clean})

@app.route('/api/sim/graph', methods=['GET'])
def api_sim_graph():
    """Return graph nodes + edges for visualization"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    routes_data = _load_routes_raw()
    graph, edges = _build_weighted_graph(routes_data)

    nodes = []
    for name in sorted(graph.keys()):
        nodes.append({
            "name": name
        })

    return jsonify({"success": True, "nodes": nodes, "edges": edges})

@app.route('/api/sim/path', methods=['POST'])
def api_sim_path():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    payload = request.get_json(force=True, silent=True) or {}
    start = (payload.get("start") or "").strip()
    end = (payload.get("end") or "").strip()

    routes_data = _load_routes_raw()
    graph, _ = _build_weighted_graph(routes_data)

    result = _dijkstra(graph, start, end)
    return jsonify({"success": True, **result})


@app.route('/admin/dashboard_stats')
def admin_dashboard_stats():
    """API endpoint for admin dashboard statistics"""
    # Check if user is logged in and is admin
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    bus_stats = bus_manager.get_bus_statistics()
    routes_data = _load_routes_raw()
    routes = routes_data.get('routes', [])
    total_routes = len(routes)
    total_stops = len(_unique_stops_from_routes(routes_data))
    total_distance = 0.0
    route_names = {}
    for route in routes:
        route_id = route.get('route_id')
        if route_id:
            route_names[route_id] = route.get('route_name')
        for stop in route.get('stops', []):
            total_distance += _safe_distance(stop.get('distance_from_previous'), 0.0)

    tickets_path = os.path.join(data_dir, 'tickets.json')
    tickets_data = {'tickets': []}
    if os.path.exists(tickets_path):
        with open(tickets_path, 'r', encoding='utf-8') as handle:
            tickets_data = json.load(handle) or {'tickets': []}
    tickets = tickets_data.get('tickets', [])
    total_tickets = len(tickets)
    active_tickets = len([ticket for ticket in tickets if ticket.get('status') != 'cancelled'])
    total_revenue = sum(ticket.get('fare', 0) for ticket in tickets if ticket.get('status') != 'cancelled')

    buses = bus_store.list_buses()
    bus_type_counts = {'air_conditioned': 0, 'standard': 0}
    route_bus_counts = {}
    for bus in buses:
        bus_type = bus.get('type') or 'standard'
        if bus_type not in bus_type_counts:
            bus_type_counts[bus_type] = 0
        bus_type_counts[bus_type] += 1
        route_id = bus.get('route_id')
        route_name = bus.get('route_name')
        if route_id:
            route_bus_counts[route_id] = route_bus_counts.get(route_id, 0) + 1
        if route_name:
            route_bus_counts[route_name] = route_bus_counts.get(route_name, 0) + 1

    stats = {
        'total_passengers': user_manager.get_user_count(),
        'active_sessions': 1,
        'system_status': 'Online',
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_buses': bus_stats['total_buses'],
        'active_buses': bus_stats['active_buses'],
        'analytics': {
            'total_routes': total_routes,
            'total_stops': total_stops,
            'total_tickets': total_tickets,
            'active_tickets': active_tickets,
            'total_revenue': round(total_revenue, 2),
            'total_distance': round(total_distance, 2),
            'bus_types': bus_type_counts,
            'route_bus_counts': route_bus_counts,
            'route_names': route_names,
        },
        'features': [
            {'name': 'Route Management', 'status': 'Active'},
            {'name': 'Passenger Queue', 'status': 'Active'},
            {'name': 'Ticket System', 'status': 'Active'},
            {'name': 'Network Graph', 'status': 'Active'},
            {'name': 'Action History', 'status': 'Active'},
            {'name': 'Data Management', 'status': 'Active'},
            {'name': 'Bus Management', 'status': 'Active'},
            {'name': 'Min Heap Bus Arrival', 'status': 'Active'},
            {'name': 'Max Heap Priority', 'status': 'Active'}
        ]
    }
    
    return jsonify(stats)

@app.route('/admin/api/actions/history')
def admin_action_history():
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    history = list(action_history.stack)[-10:]
    return jsonify({
        'history': history,
        'undo_available': not action_history.is_empty(),
        'redo_available': not redo_history.is_empty()
    })

@app.route('/admin/api/actions/undo', methods=['POST'])
def admin_action_undo():
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    if action_history.is_empty():
        return jsonify({'error': 'No actions to undo'}), 400

    action = action_history.pop()
    _write_json_file(action['file'], action['before'])
    _reload_managers(action['file'])
    redo_history.push(action)
    return jsonify({'success': True, 'message': f"Undid: {action['description']}"})

@app.route('/admin/api/actions/redo', methods=['POST'])
def admin_action_redo():
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    if redo_history.is_empty():
        return jsonify({'error': 'No actions to redo'}), 400

    action = redo_history.pop()
    _write_json_file(action['file'], action['after'])
    _reload_managers(action['file'])
    action_history.push(action)
    return jsonify({'success': True, 'message': f"Redid: {action['description']}"})

@app.route('/passenger/dashboard')
def passenger_dashboard():
    """Passenger dashboard route - ONLY ONE DEFINITION"""
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    if session.get('user_type') != 'passenger':
        flash('Access denied! Passenger account required.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    user_data = {
        'username': session.get('username'),
        'email': session.get('email'),
        'phone': session.get('phone'),
        'full_name': session.get('full_name', 'Passenger'),
        'login_time': session.get('login_time')
    }
    
    return render_template('passenger_dashboard.html', user=user_data)


@app.route('/passenger/profile', endpoint='passenger_profile_page')
def passenger_profile():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))

    user_data = {
        'username': session.get('username'),
        'email': session.get('email'),
        'phone': session.get('phone'),
        'full_name': session.get('full_name', 'Passenger'),
        'login_time': session.get('login_time'),
    }
    return render_template('passenger_profile.html', user=user_data)


@app.route('/passenger/travel_history')
def passenger_travel_history():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))

    passenger_id = session.get('user_id', '')
    history = _travel_history_read().get("history", [])
    passenger_history = [h for h in history if h.get("passenger_id") == passenger_id]
    return render_template('passenger_travel_history.html', user=session, history=passenger_history)


@app.route('/passenger/profile')
def passenger_profile():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))

    user_data = {
        'username': session.get('username'),
        'email': session.get('email'),
        'phone': session.get('phone'),
        'full_name': session.get('full_name', 'Passenger'),
        'login_time': session.get('login_time'),
    }
    return render_template('passenger_profile.html', user=user_data)


@app.route('/passenger/travel_history')
def passenger_travel_history():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))

    passenger_id = session.get('user_id', '')
    history = _travel_history_read().get("history", [])
    passenger_history = [h for h in history if h.get("passenger_id") == passenger_id]
    return render_template('passenger_travel_history.html', user=session, history=passenger_history)


@app.route('/passenger/profile')
def passenger_profile():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))

    user_data = {
        'username': session.get('username'),
        'email': session.get('email'),
        'phone': session.get('phone'),
        'full_name': session.get('full_name', 'Passenger'),
        'login_time': session.get('login_time'),
    }
    return render_template('passenger_profile.html', user=user_data)


@app.route('/passenger/travel_history')
def passenger_travel_history():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))

    passenger_id = session.get('user_id', '')
    history = _travel_history_read().get("history", [])
    passenger_history = [h for h in history if h.get("passenger_id") == passenger_id]
    return render_template('passenger_travel_history.html', user=session, history=passenger_history)


@app.route('/passenger/profile')
def passenger_profile():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))

    user_data = {
        'username': session.get('username'),
        'email': session.get('email'),
        'phone': session.get('phone'),
        'full_name': session.get('full_name', 'Passenger'),
        'login_time': session.get('login_time'),
    }
    return render_template('passenger_profile.html', user=user_data)


@app.route('/passenger/travel_history')
def passenger_travel_history():
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))

    passenger_id = session.get('user_id', '')
    history = _travel_history_read().get("history", [])
    passenger_history = [h for h in history if h.get("passenger_id") == passenger_id]
    return render_template('passenger_travel_history.html', user=session, history=passenger_history)

@app.route('/logout')
def logout():
    """Logout route"""
    username = session.get('username', 'User')
    session.clear()
    flash(f'{username} has been logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/api/users/count')
def get_user_count():
    """API endpoint to get user count"""
    count = user_manager.get_user_count()
    return jsonify({'count': count})

@app.route('/api/users')
def get_users():
    """API endpoint to get all users (admin only)"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = user_manager.get_all_users()
    return jsonify({'users': users})

@app.route('/api/user/<user_id>')
def get_user(user_id):
    """API endpoint to get specific user"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = user_manager.get_user_by_id(user_id)
    if user:
        return jsonify(user.to_dict())
    return jsonify({'error': 'User not found'}), 404

# ==================== BUS MANAGEMENT ROUTES ====================

@app.route('/admin/bus_management')
def admin_bus_management():
    """Bus Management Page"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        flash('Please login as administrator first!', 'error')
        return redirect(url_for('login'))
    
    buses = bus_manager.bus_list.get_all_buses()
    routes = load_routes_for_buses()
    
    # Get heap data
    next_arrival_bus = bus_manager.get_next_arrival()
    priority_bus = bus_manager.get_priority_bus()
    
    # Get statistics
    stats = bus_manager.get_bus_statistics()
    
    return render_template('admin_bus_management.html',
                         buses=buses,
                         routes=routes,
                         next_arrival_bus=next_arrival_bus,
                         priority_bus=priority_bus,
                         stats=stats)

@app.route('/admin/api/buses', methods=['GET'])
def get_all_buses():
    """API: Get all buses"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    buses = bus_manager.bus_list.get_all_buses()
    return jsonify({'buses': buses})

@app.route('/admin/api/buses/<int:bus_id>', methods=['GET'])
def get_bus(bus_id):
    """API: Get specific bus"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    bus_node = bus_manager.bus_list.find_bus(bus_id)
    
    if bus_node:
        return jsonify({'bus': bus_node.bus_data})
    
    return jsonify({'error': 'Bus not found'}), 404

@app.route('/admin/api/buses', methods=['POST'])
def add_bus():
    """API: Add new bus"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json

        # Validate required fields
        required_fields = ['bus_number', 'plate_number', 'driver_name', 'capacity']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create bus object
        bus_data = {
            'bus_number': data['bus_number'],
            'plate_number': data['plate_number'],
            'driver_name': data['driver_name'],
            'driver_contact': data.get('driver_contact', ''),
            'capacity': int(data['capacity']),
            'current_passengers': 0,
            'status': data.get('status', 'active'),
            'type': data.get('type', 'regular'),
            'next_arrival': data.get('next_arrival', '08:00'),
            'route_id': data.get('route_id'),
            'route_name': data.get('route_name', ''),
            'route_demand': data.get('route_demand', 0),
            'timings': data.get('timings', [])
        }

        before = _read_json_file(buses_file, [])
        # Add bus
        new_bus = bus_manager.add_bus(bus_data)
        after = _read_json_file(buses_file, [])
        _record_action(buses_file, before, after, f"Added bus {bus_data['bus_number']}")
        
        return jsonify({
            'success': True,
            'message': 'Bus added successfully',
            'bus': new_bus
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/buses/<int:bus_id>', methods=['PUT'])
def update_bus(bus_id):
    """API: Update bus"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        
        # Remove immutable fields
        data.pop('id', None)
        data.pop('created_at', None)
        
        before = _read_json_file(buses_file, [])
        # Update bus
        success = bus_manager.update_bus(bus_id, data)

        if success:
            bus_node = bus_manager.bus_list.find_bus(bus_id)
            after = _read_json_file(buses_file, [])
            _record_action(buses_file, before, after, f"Updated bus {bus_id}")
            return jsonify({
                'success': True,
                'message': 'Bus updated successfully',
                'bus': bus_node.bus_data
            })
        
        return jsonify({'error': 'Bus not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/buses/<int:bus_id>', methods=['DELETE'])
def delete_bus(bus_id):
    """API: Delete bus"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        before = _read_json_file(buses_file, [])
        success = bus_manager.delete_bus(bus_id)

        if success:
            after = _read_json_file(buses_file, [])
            _record_action(buses_file, before, after, f"Deleted bus {bus_id}")
            return jsonify({
                'success': True,
                'message': 'Bus deleted successfully'
            })
        
        return jsonify({'error': 'Bus not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/buses/allocate', methods=['POST'])
def allocate_bus():
    """API: Allocate bus to route - UPDATED for UUID routes"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        
        if 'bus_id' not in data or 'route_id' not in data:
            return jsonify({'error': 'Missing bus_id or route_id'}), 400
        
        print(f"\n=== DEBUG: Allocate Bus ===")
        print(f"Bus ID: {data['bus_id']}")
        print(f"Route ID: {data['route_id']}")
        print(f"Route ID type: {type(data['route_id'])}")
        
        # Get route name - load the routes properly
        routes = load_routes_for_buses()
        print(f"Available routes: {len(routes)}")
        
        route_name = 'Unknown'
        route_found = False
        
        for route in routes:
            print(f"Checking route: ID={route.get('id')}, Name={route.get('name')}")
            
            # Compare as strings since route_id is UUID string
            if route.get('id') and str(route.get('id')) == str(data['route_id']):
                route_name = route.get('name', 'Unknown')
                route_found = True
                print(f"✓ Found matching route: {route_name}")
                break
        
        if not route_found:
            print(f"✗ Route not found!")
            print(f"Looking for: {data['route_id']}")
            print(f"Available routes IDs:")
            for r in routes:
                print(f"  - {r.get('id')}")
            
            return jsonify({'error': f'Route not found. Available routes: {len(routes)}'}), 404
        
        before = _read_json_file(buses_file, [])
        # Allocate bus
        success = bus_manager.allocate_bus_to_route(
            int(data['bus_id']),  # Convert to int for bus_id
            str(data['route_id']),  # Keep as string for route_id (UUID)
            route_name
        )

        if success:
            bus_node = bus_manager.bus_list.find_bus(int(data['bus_id']))
            after = _read_json_file(buses_file, [])
            _record_action(buses_file, before, after, f"Allocated bus {data['bus_id']} to {route_name}")
            return jsonify({
                'success': True,
                'message': f'Bus allocated to route {route_name}',
                'bus': bus_node.bus_data
            })
        
        return jsonify({'error': 'Bus not found'}), 404
        
    except Exception as e:
        print(f"DEBUG: Exception in allocate_bus: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/buses/next_arrival', methods=['GET'])
def get_next_arrival_bus():
    """API: Get next arriving bus"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    next_bus = bus_manager.get_next_arrival()
    
    if next_bus:
        return jsonify({
            'success': True,
            'next_bus': next_bus
        })
    
    return jsonify({
        'success': True,
        'message': 'No buses available',
        'next_bus': None
    })

@app.route('/admin/api/buses/priority', methods=['GET'])
def get_priority_bus():
    """API: Get highest priority bus"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    priority_bus = bus_manager.get_priority_bus()
    
    if priority_bus:
        return jsonify({
            'success': True,
            'priority_bus': priority_bus
        })
    
    return jsonify({
        'success': True,
        'message': 'No buses available',
        'priority_bus': None
    })

@app.route('/admin/api/buses/update_arrival/<int:bus_id>', methods=['POST'])
def update_bus_arrival(bus_id):
    """API: Update bus arrival time"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        
        if 'next_arrival' not in data:
            return jsonify({'error': 'Missing next_arrival time'}), 400
        
        before = _read_json_file(buses_file, [])
        # Update arrival time
        bus_manager.update_bus_arrival(bus_id, data['next_arrival'])
        
        bus_node = bus_manager.bus_list.find_bus(bus_id)
        after = _read_json_file(buses_file, [])
        _record_action(buses_file, before, after, f"Updated arrival for bus {bus_id}")
        
        return jsonify({
            'success': True,
            'message': 'Bus arrival time updated',
            'bus': bus_node.bus_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/buses/statistics', methods=['GET'])
def get_bus_statistics_api():
    """API: Get bus statistics"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    stats = bus_manager.get_bus_statistics()
    
    return jsonify({
        'success': True,
        'statistics': stats
    })

@app.route('/admin/api/buses/filter', methods=['GET'])
def filter_buses():
    """API: Filter buses by status or route"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    status = request.args.get('status')
    route_id = request.args.get('route_id')
    
    if status:
        buses = bus_manager.bus_list.filter_by_status(status)
    elif route_id:
        buses = bus_manager.bus_list.filter_by_route(str(route_id))

    else:
        buses = bus_manager.bus_list.get_all_buses()
    
    return jsonify({
        'success': True,
        'buses': buses
    })

# ==================== ROUTE MANAGEMENT ROUTES ====================

@app.route('/admin/routes')
def admin_routes():
    """Route management page"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        flash('Please login as administrator first!', 'error')
        return redirect(url_for('login'))
    
    # Get all routes
    all_routes = route_manager.get_all_routes()
    route_stats = route_manager.get_route_stats()
    
    return render_template('admin_routes.html', 
                         routes=all_routes,
                         stats=route_stats)

@app.route('/api/routes/create', methods=['POST'])
def create_route():
    """API to create new route"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        route_name = data.get('route_name', '').strip()
        
        print(f"\n=== CREATE ROUTE API ===")
        print(f"Requested route name: '{route_name}'")
        
        if not route_name:
            print(f"✗ Route name is empty")
            return jsonify({'error': 'Route name is required'}), 400
        
        # Debug: Check existing routes
        print(f"Existing routes in system:")
        for name, rid in route_manager.route_names.items():
            print(f"  - '{name}' -> '{rid}'")
        
        before = _read_json_file(routes_file, {"routes": []})

        # Create new route
        route = route_manager.create_route(route_name)

        after = _read_json_file(routes_file, {"routes": []})
        _record_action(routes_file, before, after, f"Created route {route_name}")
        
        return jsonify({
            'success': True,
            'message': f'Route "{route_name}" created successfully',
            'route': {
                'route_id': route.route_id,
                'route_name': route.route_name,
                'total_stops': 0
            }
        })
        
    except ValueError as e:
        print(f"ValueError: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/routes/<route_id>/add_stop', methods=['POST'])
def add_stop_to_route(route_id):
    try:
        print(f"\n=== DEBUG START ===")
        print(f"Route ID from request: '{route_id}'")
        print(f"Type of route_id: {type(route_id)}")
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        stop_name = data.get('stop_name')
        if not stop_name:
            return jsonify({'error': 'Stop name is required'}), 400
        

        distance_from_previous = data.get('distance_from_previous', 0)
        try:
            distance_from_previous = float(distance_from_previous)
            if distance_from_previous < 0:
                return jsonify({'error': 'distance_from_previous must be 0 or a positive number'}), 400
        except (TypeError, ValueError):
            return jsonify({'error': 'distance_from_previous must be a number'}), 400

        stop_data = {
            'stop_name': stop_name,
            'wait_time': data.get('wait_time', 5),
            'location': data.get('location', ''),
            'distance_from_previous': distance_from_previous,
        }

        
        position = data.get('position')
        
        print(f"\nAttempting to add stop to route: {route_id}")
        print(f"Stop data: {stop_data}")
        print(f"Position: {position}")
        
        before = _read_json_file(routes_file, {"routes": []})

        # Call add_stop
        result = route_manager.add_stop(route_id, stop_data, position)

        after = _read_json_file(routes_file, {"routes": []})
        _record_action(routes_file, before, after, f"Added stop {stop_name}")
        
        print(f"\nSuccess! Stop added: {stop_name}")
        print("=== DEBUG END ===\n")
        
        return jsonify({
            'success': True,
            'message': f'Stop "{stop_name}" added successfully',
            'stop': result
        }), 200
        
    except ValueError as e:
        print(f"ValueError: {e}")
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/routes/<route_id>/remove_stop/<int:position>', methods=['DELETE'])
def remove_stop_from_route(route_id, position):
    """API to remove stop from route"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        before = _read_json_file(routes_file, {"routes": []})
        # Remove stop from route
        removed_stop = route_manager.remove_stop(route_id, position)

        after = _read_json_file(routes_file, {"routes": []})
        stop_name = removed_stop.get('stop_name', 'stop') if isinstance(removed_stop, dict) else 'stop'
        _record_action(routes_file, before, after, f"Removed stop {stop_name}")
        
        return jsonify({
            'success': True,
            'message': f'Stop removed successfully',
            'removed_stop': removed_stop
        })
        
    except (ValueError, IndexError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/routes/<route_id>/update_stop/<int:position>', methods=['PUT'])
def update_stop_in_route(route_id, position):
    """API to update stop in route"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        updated_data = {
            'stop_name': data.get('stop_name', '').strip(),
            'wait_time': data.get('wait_time'),
            'location': data.get('location', ''),
        }
        
        before = _read_json_file(routes_file, {"routes": []})
        # Update stop in route
        updated_stop = route_manager.update_stop(route_id, position, updated_data)

        after = _read_json_file(routes_file, {"routes": []})
        stop_name = updated_stop.get('stop_name', 'stop') if isinstance(updated_stop, dict) else 'stop'
        _record_action(routes_file, before, after, f"Updated stop {stop_name}")
        
        return jsonify({
            'success': True,
            'message': f'Stop updated successfully',
            'stop': updated_stop
        })
        
    except (ValueError, IndexError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/routes/<route_id>/reorder', methods=['PUT'])
def reorder_route_stops(route_id):
    """API to reorder stops in route"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        new_order = data.get('new_order', [])
        
        if not new_order:
            return jsonify({'error': 'New order array is required'}), 400
        
        before = _read_json_file(routes_file, {"routes": []})
        # Reorder stops
        updated_route = route_manager.reorder_stops(route_id, new_order)

        after = _read_json_file(routes_file, {"routes": []})
        _record_action(routes_file, before, after, "Reordered route stops")
        
        return jsonify({
            'success': True,
            'message': f'Route stops reordered successfully',
            'route': updated_route
        })
        
    except (ValueError, IndexError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/routes/<route_id>', methods=['DELETE'])
def delete_route(route_id):
    """API to delete a route"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        before = _read_json_file(routes_file, {"routes": []})
        # Delete route
        success = route_manager.delete_route(route_id)

        after = _read_json_file(routes_file, {"routes": []})
        _record_action(routes_file, before, after, "Deleted route")
        
        return jsonify({
            'success': True,
            'message': 'Route deleted successfully'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/routes')
def get_all_routes_api():
    """API to get all routes"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        all_routes = route_manager.get_all_routes()
        
        return jsonify({
            'success': True,
            'routes': all_routes,
            'total': len(all_routes)
        })
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/routes/stats')
def get_route_stats_api():
    """API to get route statistics"""
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        stats = route_manager.get_route_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/routes/<route_id>', methods=['GET'])
def get_route_details(route_id):
    """API to get specific route details"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    print(f"DEBUG: Getting route details for ID: {route_id}")
    
    try:
        # Method 1: Try from get_all_routes first
        all_routes = route_manager.get_all_routes()
        print(f"DEBUG: All routes count: {len(all_routes)}")
        
        for route in all_routes:
            if route.get('route_id') == route_id:
                print(f"DEBUG: Found route in get_all_routes: {route.get('route_name')}")
                return jsonify({
                    'success': True,
                    'route': {
                        'route_id': route['route_id'],
                        'route_name': route['route_name'],
                        'total_stops': route.get('total_stops', 0),
                        'stops': route.get('stops', []),
                        'route_string': route.get('route_string', '')
                    }
                })
        
        # Method 2: Try get_route directly
        print(f"DEBUG: Route not found in get_all_routes, trying get_route()")
        route_obj = route_manager.get_route(route_id)
        
        if route_obj:
            print(f"DEBUG: Found route object: {route_obj}")
            print(f"DEBUG: Route type: {type(route_obj)}")
            
            # Build basic route info
            route_data = {
                'route_id': getattr(route_obj, 'route_id', route_id),
                'route_name': getattr(route_obj, 'route_name', 'Unknown Route'),
                'total_stops': len(route_obj) if hasattr(route_obj, '__len__') else 0,
                'stops': [],
                'route_string': str(route_obj) if hasattr(route_obj, '__str__') else ''
            }
            
            return jsonify({
                'success': True,
                'route': route_data
            })
        
        print(f"DEBUG: Route not found anywhere")
        return jsonify({'error': 'Route not found'}), 404
        
    except Exception as e:
        print(f"ERROR in get_route_details: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# ==================== PASSENGER BOOKING ROUTES ====================

@app.route('/passenger/my_tickets')
def passenger_my_tickets():
    """My tickets page"""
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    passenger_id = session.get('user_id', '')
    tickets = ticket_store.list_for_passenger(passenger_id)

    return render_template(
        'passenger_my_tickets.html',
        user=session,
        tickets=tickets
    )


@app.route('/api/passenger/stops')
def passenger_stops():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('user_type') != 'passenger':
        return jsonify({'error': 'Passenger access only'}), 403

    route_planner.reload()
    return jsonify({'stops': route_planner.list_stops()})


@app.route('/api/passenger/graph')
def passenger_graph():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('user_type') != 'passenger':
        return jsonify({'error': 'Passenger access only'}), 403

    route_planner.reload()
    buses = _load_buses_raw()
    route_counts, route_name_counts = _bus_route_counts(buses)
    edges = []
    for edge in route_planner.list_edges():
        route_id = edge.get("route_id")
        bus_count = route_counts.get(str(route_id), 0) if route_id else 0
        edges.append({
            **edge,
            "bus_count": bus_count,
            "traffic": _traffic_level(bus_count),
        })
    return jsonify({
        'stops': route_planner.list_stops(),
        'edges': edges,
        'route_bus_counts': route_counts,
        'route_name_counts': route_name_counts,
    })


@app.route('/api/passenger/buses')
def passenger_buses():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('user_type') != 'passenger':
        return jsonify({'error': 'Passenger access only'}), 403

    return jsonify({'buses': bus_store.list_buses()})


@app.route('/api/passenger/route', methods=['POST'])
def passenger_route():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('user_type') != 'passenger':
        return jsonify({'error': 'Passenger access only'}), 403

    payload = request.get_json(force=True, silent=True) or {}
    start = (payload.get('start_stop') or '').strip()
    end = (payload.get('end_stop') or '').strip()

    route_planner.reload()
    if not route_planner.validate_stop(start) or not route_planner.validate_stop(end):
        return jsonify({'error': 'Invalid stops supplied'}), 400

    result = route_planner.shortest_path(start, end)
    if not result:
        return jsonify({'error': 'No route found between selected stops'}), 400

    edges = route_planner.list_edges()
    route_votes = {}
    route_name_votes = {}
    segments = []
    for segment in result.get("segments", []):
        match = next(
            (
                edge
                for edge in edges
                if (edge.get("from") == segment["from"] and edge.get("to") == segment["to"])
                or (edge.get("from") == segment["to"] and edge.get("to") == segment["from"])
            ),
            None,
        )
        route_id = match.get("route_id") if match else None
        route_name = match.get("route_name") if match else None
        if route_id:
            route_votes[route_id] = route_votes.get(route_id, 0) + 1
        if route_name:
            route_name_votes[route_name] = route_name_votes.get(route_name, 0) + 1
        segments.append({
            "from": segment["from"],
            "to": segment["to"],
            "distance": segment["weight"],
            "route_id": route_id,
            "route_name": route_name,
        })

    buses = _load_buses_raw()
    route_counts, _ = _bus_route_counts(buses)
    route_id = max(route_votes, key=route_votes.get) if route_votes else None
    route_name = max(route_name_votes, key=route_name_votes.get) if route_name_votes else "Route"
    bus_count = route_counts.get(str(route_id), 0) if route_id else 0

    return jsonify({
        'path': result['path'],
        'distance': result['distance'],
        'stops': len(result['path']) - 1,
        'route_id': route_id,
        'route_name': route_name,
        'bus_count': bus_count,
        'traffic': _traffic_level(bus_count),
        'segments': segments,
    })


@app.route('/api/passenger/journey/start', methods=['POST'])
def passenger_start_journey():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('user_type') != 'passenger':
        return jsonify({'error': 'Passenger access only'}), 403

    payload = request.get_json(force=True, silent=True) or {}
    start = (payload.get('start_stop') or '').strip()
    end = (payload.get('end_stop') or '').strip()
    bus_number = (payload.get('bus_number') or '').strip()

    route_planner.reload()
    if not route_planner.validate_stop(start) or not route_planner.validate_stop(end):
        return jsonify({'error': 'Invalid stops supplied'}), 400

    result = route_planner.shortest_path(start, end)
    if not result:
        return jsonify({'error': 'No route found between selected stops'}), 400

    bus = None
    speed_kph = 30.0
    if bus_number:
        bus = next((b for b in bus_store.list_buses() if str(b.get('bus_number')) == bus_number), None)
        if not bus:
            return jsonify({'error': 'Selected bus is not available'}), 400
        speed_kph = float(bus.get('speed_kph') or speed_kph)

    journey_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    segments = [
        {
            "from": segment["from"],
            "to": segment["to"],
            "distance": segment["weight"],
        }
        for segment in result.get("segments", [])
    ]
    journey = {
        "journey_id": journey_id,
        "passenger_id": session.get('user_id', ''),
        "start_stop": start,
        "end_stop": end,
        "bus_number": bus_number,
        "bus_type": bus.get("type") if bus else None,
        "speed_kph": speed_kph,
        "path": result["path"],
        "segments": segments,
        "distance": result["distance"],
        "status": "in_transit",
        "start_time": created_at,
        "last_updated": created_at,
    }

    data = _journey_read()
    journeys = data.get("journeys", [])
    journeys.append(journey)
    data["journeys"] = journeys
    _journey_write(data)

    return jsonify({
        "journey": journey,
    }), 201


@app.route('/api/passenger/journey/status')
def passenger_journey_status():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('user_type') != 'passenger':
        return jsonify({'error': 'Passenger access only'}), 403

    journey_id = (request.args.get("journey_id") or "").strip()
    if not journey_id:
        return jsonify({'error': 'Journey id is required'}), 400

    data = _journey_read()
    journeys = data.get("journeys", [])
    journey = next((j for j in journeys if j.get("journey_id") == journey_id), None)
    if not journey:
        return jsonify({'error': 'Journey not found'}), 404
    if journey.get("passenger_id") != session.get('user_id', ''):
        return jsonify({'error': 'Unauthorized'}), 403

    start_time = journey.get("start_time")
    if start_time:
        start_dt = datetime.fromisoformat(start_time)
    else:
        start_dt = datetime.utcnow()
    elapsed_minutes = max((datetime.utcnow() - start_dt).total_seconds() / 60, 0)
    speed_kph = float(journey.get("speed_kph") or 30.0)
    distance_covered = speed_kph * (elapsed_minutes / 60)
    total_distance = _journey_total_distance(journey.get("segments", []))
    distance_covered = min(distance_covered, total_distance)

    position = _journey_position(journey.get("segments", []), distance_covered)
    remaining_distance = max(total_distance - distance_covered, 0)
    remaining_minutes = (remaining_distance / speed_kph) * 60 if speed_kph > 0 else 0
    status = "approaching_destination" if remaining_distance <= 0.2 else "in_transit"

    journey["status"] = status
    journey["last_updated"] = datetime.utcnow().isoformat()
    journey["distance_covered"] = round(distance_covered, 2)
    journey["remaining_distance"] = round(remaining_distance, 2)
    data["journeys"] = journeys
    _journey_write(data)

    return jsonify({
        "journey_id": journey_id,
        "status": status,
        "position": position,
        "remaining_distance": remaining_distance,
        "remaining_minutes": remaining_minutes,
        "distance_covered": distance_covered,
        "total_distance": total_distance,
    })


@app.route('/api/passenger/tickets', methods=['GET', 'POST'])
def passenger_tickets_api():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('user_type') != 'passenger':
        return jsonify({'error': 'Passenger access only'}), 403

    passenger_id = session.get('user_id', '')
    if request.method == 'GET':
        tickets = ticket_store.list_for_passenger(passenger_id)
        return jsonify({'tickets': tickets})

    payload = request.get_json(force=True, silent=True) or {}
    start = (payload.get('start_stop') or '').strip()
    end = (payload.get('end_stop') or '').strip()
    bus_number = (payload.get('bus_number') or '').strip()

    route_planner.reload()
    if not route_planner.validate_stop(start) or not route_planner.validate_stop(end):
        return jsonify({'error': 'Invalid stops supplied'}), 400

    result = route_planner.shortest_path(start, end)
    if not result:
        return jsonify({'error': 'No route found between selected stops'}), 400
    if not bus_number:
        return jsonify({'error': 'Bus selection is required'}), 400

    bus = next((b for b in bus_store.list_buses() if str(b.get('bus_number')) == bus_number), None)
    if not bus:
        return jsonify({'error': 'Selected bus is not available'}), 400
    capacity = int(bus.get('capacity') or 0)
    current_passengers = int(bus.get('current_passengers') or 0)
    if capacity and current_passengers >= capacity:
        return jsonify({'error': 'Selected bus is full'}), 400

    distance = result['distance']
    fare_rate = 3.5 if bus.get('type') == 'air_conditioned' else 2.5
    fare = max(round(distance * fare_rate, 2), 10.0)
    eta = bus.get('next_arrival')

    ticket = ticket_store.add_ticket(
        passenger_id=passenger_id,
        passenger_name=session.get('full_name', 'Passenger'),
        start_stop=start,
        end_stop=end,
        path=result['path'],
        bus_number=bus_number,
        fare=fare,
        distance=distance,
        eta=eta,
    )
    _update_bus_passengers(bus_number, 1)
    return jsonify({'ticket': ticket}), 201


@app.route('/api/passenger/tickets/<ticket_id>')
def passenger_ticket_detail(ticket_id: str):
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('user_type') != 'passenger':
        return jsonify({'error': 'Passenger access only'}), 403

    ticket = ticket_store.get_ticket(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket not found'}), 404
    return jsonify({'ticket': ticket})

@app.route('/passenger/book_ticket')
def passenger_book_ticket_page():
    """Ticket booking page - DIFFERENT FUNCTION NAME"""
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Get available routes for dropdown
    routes = []
    if 'routes' in booking_system.routes:
        routes = booking_system.routes['routes']
    
    return render_template('passenger_book_ticket.html', 
                         user=session,
                         routes=routes,
                         now=datetime.now().strftime('%Y-%m-%d'))

@app.route('/passenger/plan_journey')
def passenger_plan_journey():
    """Plan journey page with route finding"""
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Get all stops for dropdown
    stops = []
    if 'routes' in booking_system.routes:
        for route in booking_system.routes['routes']:
            for stop in route.get('stops', []):
                if stop['stop_name'] not in stops:
                    stops.append(stop['stop_name'])
    
    return render_template('passenger_plan_journey.html',
                         user=session,
                         stops=stops)

@app.route('/passenger/live_tracking')
def passenger_live_tracking():
    """Live bus tracking page"""
    if not session.get('logged_in'):
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    if session.get('user_type') != 'passenger':
        flash('Passenger access only!', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Get active buses
    active_buses = []
    if 'buses' in booking_system.buses:
        active_buses = [bus for bus in booking_system.buses['buses'] 
                       if bus.get('status') == 'active']
    
    return render_template('passenger_live_tracking.html',
                         user=session,
                         active_buses=active_buses)

# ==================== BOOKING API ENDPOINTS ====================

@app.route('/api/book/available_buses', methods=['POST'])
def get_available_buses_api():
    """API: Get available buses for route"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        from_stop = data.get('from_stop')
        to_stop = data.get('to_stop')
        date = data.get('date')
        
        if not all([from_stop, to_stop, date]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        available_buses = booking_system.get_available_buses(from_stop, to_stop, date)
        
        return jsonify({
            'success': True,
            'buses': available_buses,
            'count': len(available_buses)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/book/ticket', methods=['POST'])
def book_ticket_api():
    """API: Book a ticket"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        
        # Add passenger info from session
        data['passenger_id'] = session.get('user_id', '')
        data['passenger_name'] = session.get('full_name', '')
        data['passenger_contact'] = session.get('phone', '')
        
        # Book ticket
        result = booking_system.book_ticket(data)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/book/cancel_ticket/<ticket_id>', methods=['POST'])
def cancel_ticket_api(ticket_id):
    """API: Cancel a ticket"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        result = booking_system.cancel_ticket(ticket_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plan/shortest_route', methods=['POST'])
def find_shortest_route_api():
    """API: Find shortest route"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        from_stop = data.get('from_stop')
        to_stop = data.get('to_stop')
        criteria = data.get('criteria', 'time')
        
        if not from_stop or not to_stop:
            return jsonify({'error': 'Missing stops'}), 400
        
        result = booking_system.find_shortest_route(from_stop, to_stop, criteria)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tracking/live_buses')
def get_live_buses_api():
    """API: Get live bus positions"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Simulated live bus positions
        live_buses = []
        
        if 'buses' in booking_system.buses:
            for bus in booking_system.buses['buses']:
                if bus.get('status') == 'active':
                    stops = []
                    route_name = bus.get('route_name', '')
                    route_id = bus.get('route_id', '')

                    # Get stops for this route
                    for route in booking_system.routes.get('routes', []):
                        if route_id and route.get('route_id') == route_id:
                            stops = route.get('stops', [])
                            route_name = route.get('route_name', route_name)
                            break
                        if route.get('route_name', '').lower() == route_name.lower():
                            stops = route.get('stops', [])
                            break

                    if stops and len(stops) > 1:
                        stop_names = [s.get('stop_name', '') for s in stops]
                        segment_distances = [
                            float(stops[index].get('distance_from_previous') or 0)
                            for index in range(1, len(stops))
                        ]
                        speed_kph = float(bus.get('speed_kph') or 0)
                        segment_duration_minutes = float(bus.get('segment_duration_minutes') or 0)
                        if speed_kph <= 0 and segment_duration_minutes <= 0:
                            speed_kph = 30.0

                        segment_durations = []
                        for distance in segment_distances:
                            if segment_duration_minutes > 0:
                                duration = segment_duration_minutes
                            else:
                                duration = (distance / speed_kph) * 60 if distance > 0 else 1.0
                            segment_durations.append(max(duration, 1.0))

                        start_stop = bus.get('start_stop') or stop_names[0]
                        start_stop_index = (
                            stop_names.index(start_stop)
                            if start_stop in stop_names
                            else 0
                        )
                        if start_stop_index >= len(stop_names) - 1:
                            start_stop_index = 0
                        active_segment_durations = segment_durations[start_stop_index:]
                        total_duration = sum(active_segment_durations) or 1.0

                        start_time_str = bus.get('start_time')
                        now = datetime.now()
                        if start_time_str:
                            try:
                                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                                start_dt = datetime.combine(now.date(), start_time)
                                if start_dt > now:
                                    start_dt = start_dt - timedelta(days=1)
                            except ValueError:
                                start_dt = now
                        else:
                            start_dt = now

                        elapsed_minutes = max((now - start_dt).total_seconds() / 60, 0.0)
                        elapsed_cycle = elapsed_minutes % total_duration

                        segment_index = start_stop_index
                        segment_elapsed = 0.0
                        for duration in active_segment_durations:
                            if elapsed_cycle <= duration:
                                segment_elapsed = elapsed_cycle
                                break
                            elapsed_cycle -= duration
                            segment_index += 1

                        if segment_index >= len(segment_durations):
                            segment_index = len(segment_durations) - 1
                            segment_elapsed = segment_durations[segment_index]

                        segment_duration = segment_durations[segment_index] or 1.0
                        segment_progress = min(segment_elapsed / segment_duration, 1.0)
                        segment_index_relative = max(segment_index - start_stop_index, 0)
                        current_stop = stop_names[segment_index]
                        next_stop = stop_names[segment_index + 1]
                        eta_minutes = max(int(round((1 - segment_progress) * segment_duration)), 1)

                        live_buses.append({
                            'bus_number': bus['bus_number'],
                            'route_name': route_name,
                            'current_stop': current_stop,
                            'next_stop': next_stop,
                            'segment_index': segment_index_relative,
                            'segment_progress': round(segment_progress, 3),
                            'total_segments': len(active_segment_durations),
                            'passenger_count': bus.get('current_passengers', 0),
                            'capacity': bus.get('capacity', 50),
                            'status': 'moving',
                            'speed': int(round(speed_kph)),
                            'speed_kph': int(round(speed_kph)),
                            'eta': f"{eta_minutes} minutes"
                        })
        
        return jsonify({
            'success': True,
            'live_buses': live_buses,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/passenger/stats')
def get_passenger_stats_api():
    """API: Get passenger statistics"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        passenger_id = session.get('user_id', '')
        tickets = booking_system.get_passenger_tickets(passenger_id)
        
        stats = {
            'total_tickets': len(tickets),
            'active_tickets': len([t for t in tickets if t.get('status') == 'confirmed']),
            'total_spent': sum(t.get('fare', 0) for t in tickets if t.get('status') == 'confirmed'),
            'favorite_route': '',
            'last_ticket': tickets[0] if tickets else None
        }
        
        # Find favorite route
        route_counts = {}
        for ticket in tickets:
            route = ticket.get('route_name', '')
            if route:
                route_counts[route] = route_counts.get(route, 0) + 1
        
        if route_counts:
            stats['favorite_route'] = max(route_counts, key=route_counts.get)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/ticket/<ticket_id>')
def download_ticket(ticket_id):
    """Download ticket as file"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        ticket = booking_system.get_ticket_details(ticket_id)
        
        if not ticket:
            flash('Ticket not found!', 'error')
            return redirect(url_for('passenger_my_tickets'))
        
        # Check if ticket belongs to logged in passenger
        if ticket.get('passenger_id') != session.get('user_id'):
            flash('Access denied!', 'error')
            return redirect(url_for('passenger_my_tickets'))
        
        # Generate download content
        filename = f"ticket_{ticket_id}.txt"
        content = f"""
========================================
        BUS TICKET
========================================
Ticket ID: {ticket.get('ticket_id')}
Booking Date: {ticket.get('booking_time')}
Status: {ticket.get('status')}
----------------------------------------
PASSENGER INFORMATION
Name: {ticket.get('passenger_name')}
Contact: {ticket.get('passenger_contact')}
----------------------------------------
JOURNEY DETAILS
From: {ticket.get('from_stop')}
To: {ticket.get('to_stop')}
Date: {ticket.get('travel_date')}
----------------------------------------
BUS DETAILS
Bus Number: {ticket.get('bus_number')}
Route: {ticket.get('route_name')}
Seat Number: {ticket.get('seat_number')}
----------------------------------------
TIMINGS
Departure: {ticket.get('departure_time')}
Arrival: {ticket.get('arrival_time')}
----------------------------------------
FARE: Rs. {ticket.get('fare')}
Payment Status: {ticket.get('payment_status')}
----------------------------------------
QR Code: {ticket.get('qr_code')}
========================================
"""
        
        response = make_response(content)
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Content-type"] = "text/plain"
        
        return response
        
    except Exception as e:
        flash(f'Error downloading ticket: {str(e)}', 'error')
        return redirect(url_for('passenger_my_tickets'))

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# Simple error pages
@app.errorhandler(404)
def page_not_found(e):
    # Render dedicated template; keep it simple so it never fails.
    return render_template('404.html'), 404

@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html'), 401

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Use FLASK_ENV / FLASK_DEBUG in production instead of hardcoding debug=True.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
