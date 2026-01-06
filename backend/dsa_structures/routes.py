"""
Route Management System using Linked Lists
Manages bus routes with CRUD operations
"""

import json
import uuid
from datetime import datetime
import os
from .linked_list import LinkedList

class RouteManager:
    """Manages bus routes using Linked List data structure"""
    
    def __init__(self, routes_file):
        self.routes_file = routes_file
        self.routes = {}  # Dictionary to store routes by ID (Hash Table for O(1) lookup)
        self.route_names = {}  # Index for route names
        self.load_routes()
    
    def load_routes(self):
        """Load routes from JSON file - FIXED VERSION"""
        try:
            print(f"\n=== LOAD ROUTES ===")
            
            if os.path.exists(self.routes_file):
                with open(self.routes_file, 'r') as f:
                    data = json.load(f)
                    
                # Clear existing data
                self.routes.clear()
                self.route_names.clear()
                
                routes_loaded = 0
                print(f"Loading from {self.routes_file}...")
                
                for route_data in data.get('routes', []):
                    try:
                        # Create LinkedList from JSON data
                        route = self._create_route_from_data(route_data)
                        
                        # Ensure route has ID and name
                        if not hasattr(route, 'route_id'):
                            route.route_id = route_data.get('route_id', str(uuid.uuid4()))
                        if not hasattr(route, 'route_name'):
                            route.route_name = route_data.get('route_name', f"Route_{route.route_id[:8]}")
                        
                        # Store in hash tables
                        self.routes[route.route_id] = route
                        self.route_names[route.route_name] = route.route_id
                        routes_loaded += 1
                        
                        print(f"  ✓ Loaded: {route.route_name} (ID: {route.route_id})")
                        
                    except Exception as e:
                        print(f"  ✗ Error loading route: {e}")
                
                print(f"✓ Loaded {routes_loaded} routes")
                
                # Verify consistency
                print(f"\nVerifying consistency:")
                print(f"  Routes in dictionary: {len(self.routes)}")
                print(f"  Routes in route_names index: {len(self.route_names)}")
                
                # Check for missing entries
                for route_id, route in self.routes.items():
                    if hasattr(route, 'route_name'):
                        if route.route_name not in self.route_names:
                            print(f"  ⚠️ Missing: {route.route_name} not in route_names")
                            self.route_names[route.route_name] = route_id
                        elif self.route_names[route.route_name] != route_id:
                            print(f"  ⚠️ Mismatch: {route.route_name} has wrong ID")
                            self.route_names[route.route_name] = route_id
                
                print("=== END LOAD ===\n")
                
            else:
                print(f"File {self.routes_file} does not exist, creating empty...")
                self.save_routes()
                    
        except json.JSONDecodeError:
            print(f"✗ Invalid JSON in {self.routes_file}")
            self.routes = {}
            self.route_names = {}
        except Exception as e:
            print(f"✗ Error loading routes: {e}")
            import traceback
            traceback.print_exc()
            self.routes = {}
            self.route_names = {}

    def _create_route_from_data(self, route_data):
        """Create Linked List route from JSON data"""
        route = LinkedList()
        
        # Ensure route_data is a dictionary
        if isinstance(route_data, dict):
            route.route_id = route_data.get('route_id', str(uuid.uuid4()))
            route.route_name = route_data.get('route_name', 'Unnamed Route')
            route.size = 0  # Initialize size
            
            # Add all stops to linked list
            for stop_data in route_data.get('stops', []):
                if stop_data and isinstance(stop_data, dict):  # Validate stop_data
                    stop_data.setdefault('distance_from_previous', 0)
                    route.add_last(stop_data)
        else:
            # If route_data is already a LinkedList or unexpected type
            print(f"Warning: Unexpected type in _create_route_from_data: {type(route_data)}")
            return route_data if hasattr(route_data, 'add_last') else LinkedList()
        
        return route
    
    def save_routes(self):
        """Save routes to JSON file - FIXED VERSION"""
        try:
            print(f"\n=== SAVE ROUTES ===")
            print(f"Saving {len(self.routes)} routes...")
            
            routes_data = []
            
            for route_id, route in self.routes.items():
                # Ensure route has required attributes
                if not hasattr(route, 'route_id'):
                    route.route_id = route_id
                if not hasattr(route, 'route_name'):
                    route.route_name = f"Route_{route_id[:8]}"
                
                route_data = {
                    'route_id': route.route_id,
                    'route_name': route.route_name,
                    'created_at': datetime.now().isoformat(),
                    'total_stops': len(route),
                    'stops': route.to_list() if hasattr(route, 'to_list') else []
                }
                routes_data.append(route_data)
                
                print(f"  - Saving: {route.route_name} (ID: {route.route_id})")
            
            data = {
                'routes': routes_data,
                'total_routes': len(self.routes),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.routes_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✓ Saved to {self.routes_file}")
            print("=== END SAVE ===\n")
            return True
            
        except Exception as e:
            print(f"✗ Error saving routes: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_route(self, route_name, description=""):
        """Create a new bus route"""
        print(f"\n{'='*60}")
        print("CREATE_ROUTE METHOD")
        print('='*60)
        
        # Clean and validate route name
        route_name_clean = route_name.strip()
        print(f"Requested route name: '{route_name_clean}'")
        
        if not route_name_clean:
            print("✗ Route name is empty")
            raise ValueError("Route name cannot be empty")
        
        # Debug: Print current state
        print(f"Current route_names dictionary:")
        for name, rid in self.route_names.items():
            print(f"  '{name}' -> '{rid}'")
        
        print(f"\nChecking if '{route_name_clean}' exists...")
        
        # Case-insensitive check
        for existing_name in self.route_names.keys():
            if existing_name.lower() == route_name_clean.lower():
                print(f"✗ Route name '{route_name_clean}' already exists (case-insensitive match)")
                print(f"  Existing name: '{existing_name}'")
                raise ValueError(f"Route '{route_name_clean}' already exists")
        
        print(f"✓ Route name '{route_name_clean}' is available")
        
        # Create new route
        route = LinkedList()
        route.route_id = str(uuid.uuid4())
        route.route_name = route_name_clean
        
        print(f"Created route with ID: {route.route_id}")
        
        # Store in data structures
        self.routes[route.route_id] = route
        self.route_names[route_name_clean] = route.route_id
        
        print(f"Added to routes dictionary (total: {len(self.routes)})")
        print(f"Added to route_names index (total: {len(self.route_names)})")
        
        # Save to file
        if self.save_routes():
            print(f"✓ Route saved successfully")
            print("="*60 + "\n")
            return route
        else:
            print("✗ Failed to save route")
            raise Exception("Failed to save route to file")
        
    def add_stop(self, route_id, stop_data, position=None):
        """Add a bus stop to route"""
        try:
            print(f"\n=== ADD_STOP SIMPLIFIED ===")
            print(f"Looking for route_id: '{route_id}'")
            print(f"self.routes has {len(self.routes)} routes")
            print(f"Available IDs: {list(self.routes.keys())}")
            
            # SIMPLE DIRECT LOOKUP
            if route_id not in self.routes:
                raise ValueError(f"Route with ID '{route_id}' not found")
            
            route = self.routes[route_id]
            print(f"✓ Route found: {route.route_name}")
            
            # Prepare stop data
            if not isinstance(stop_data, dict):
                stop_data = {}
            
            # Ensure required fields
            if 'stop_id' not in stop_data:
                stop_data['stop_id'] = str(uuid.uuid4())
            
            if 'stop_name' not in stop_data:
                stop_data['stop_name'] = f"Stop_{len(route) + 1}"

                        # ---- Distance from previous stop (km) ----
            dist = stop_data.get('distance_from_previous', 0)

            try:
                dist = float(dist)
            except (TypeError, ValueError):
                raise ValueError("distance_from_previous must be a number")

            if dist < 0:
                raise ValueError("distance_from_previous must be 0 or a positive number")

            # If adding as the first stop (route empty OR inserting at position 1), force distance = 0
            pos_int = None
            if position is not None:
                try:
                    pos_int = int(position)
                except (TypeError, ValueError):
                    pos_int = None

            if len(route) == 0 or pos_int == 1:
                dist = 0.0

            stop_data['distance_from_previous'] = dist

            
            stop_data['added_at'] = datetime.now().isoformat()
            
            print(f"Adding stop: {stop_data['stop_name']}")
            
            # Add to linked list
            try:
                if position is None or position > len(route):
                    node = route.add_last(stop_data)
                else:
                    node = route.insert_at(position, stop_data)
            except Exception as e:
                print(f"Error adding to linked list: {e}")
                raise ValueError(f"Failed to add stop to linked list: {e}")
            
            # Save to file
            if not self.save_routes():
                raise Exception("Failed to save routes to file")
            
            print(f"✓ Successfully added stop '{stop_data['stop_name']}' to route '{route.route_name}'")
            print("=== END ADD_STOP ===\n")
            
            return node.data
            
        except Exception as e:
            print(f"Error in add_stop: {e}")
            import traceback
            traceback.print_exc()
            raise

    def update_stop(self, route_id, position, updated_data):
        """Update bus stop information"""
        route = self.routes.get(route_id)
        if not route:
            raise ValueError(f"Route with ID {route_id} not found")
        
        if position < 1 or position > len(route):
            raise IndexError(f"Position {position} out of bounds")
        
        # Get existing stop data
        existing_stop = route.get_at(position)

        # Preserve distance_from_previous if edit request doesn't include it
        if 'distance_from_previous' not in updated_data or updated_data['distance_from_previous'] is None:
            updated_data['distance_from_previous'] = existing_stop.get('distance_from_previous', 0)
        else:
            try:
                d = float(updated_data['distance_from_previous'])
            except (TypeError, ValueError):
                raise ValueError("distance_from_previous must be a number")
            if d < 0:
                raise ValueError("distance_from_previous must be 0 or a positive number")
            updated_data['distance_from_previous'] = d

        
        # Update with new data (preserve ID and timestamp)
        updated_data['stop_id'] = existing_stop.get('stop_id')
        updated_data['added_at'] = existing_stop.get('added_at')
        updated_data['updated_at'] = datetime.now().isoformat()
        
        # Update in linked list
        route.update_at(position, updated_data)
        
        # Save changes
        self.save_routes()
        
        print(f"Updated stop at position {position} in route '{route.route_name}'")
        return updated_data

    def remove_stop(self, route_id, position):
        """Remove a bus stop from route - FIXED"""
        print(f"\n=== REMOVE STOP ===")
        print(f"Route ID: {route_id}, Position: {position}")
        
        if route_id not in self.routes:
            print(f"✗ Route not found")
            raise ValueError(f"Route with ID {route_id} not found")
        
        route = self.routes[route_id]
        
        if position < 1 or position > len(route):
            print(f"✗ Position {position} out of bounds (1-{len(route)})")
            raise IndexError(f"Position {position} out of bounds")
        
        print(f"Removing stop from route: {getattr(route, 'route_name', 'Unknown')}")
        
        try:
            # Remove from linked list
            removed_stop = route.remove_at(position)
            
            # Save changes
            self.save_routes()
            
            print(f"✓ Removed stop: {removed_stop.get('stop_name', 'Unknown')}")
            print("=== END REMOVE ===\n")
            
            return removed_stop
            
        except Exception as e:
            print(f"✗ Error removing stop: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def reorder_stops(self, route_id, new_order):
        """Reorder stops in a route"""
        route = self.routes.get(route_id)
        if not route:
            raise ValueError(f"Route with ID {route_id} not found")
        
        # Validate new order
        if len(new_order) != len(route):
            raise ValueError(f"New order must contain exactly {len(route)} stops")
        
        # Get all stops
        all_stops = route.to_list()
        
        # Clear and rebuild route in new order
        route.clear()
        
        for pos in new_order:
            if 0 <= pos < len(all_stops):
                route.add_last(all_stops[pos])
        
        # Save changes
        self.save_routes()
        
        print(f"Reordered {len(route)} stops in route '{route.route_name}'")
        return route.display()
    
    def get_route(self, route_id):
        """Get route by ID"""
        if route_id in self.routes:
            route = self.routes[route_id]
            
            # Convert linked list to proper format
            stops_data = []
            if hasattr(route, 'display'):
                display_result = route.display()
                print(f"DEBUG: Route display() returns: {display_result}")  # Debug
                
                if isinstance(display_result, list):
                    for i, item in enumerate(display_result, 1):
                        if isinstance(item, dict) and 'data' in item:
                            # Format: {'data': {...}, 'position': X}
                            stops_data.append({
                                'position': item.get('position', i),
                                'data': item['data']
                            })
                        elif isinstance(item, dict):
                            # Direct dictionary
                            stops_data.append({
                                'position': i,
                                'data': item
                            })
            
            return {
                'route_id': route.route_id,
                'route_name': route.route_name,
                'total_stops': len(route),
                'stops': stops_data,
                'route_string': str(route)
            }
        return None
    
    def get_route_by_name(self, route_name):
        """Get route by name (O(1) using Hash Table)"""
        route_id = self.route_names.get(route_name)
        return self.routes.get(route_id) if route_id else None
    
    def get_all_routes(self):
        """Get all routes"""
        routes_list = []
        
        for route_id, route in self.routes.items():
            routes_list.append({
                'route_id': route.route_id,
                'route_name': route.route_name,
                'total_stops': len(route),
                'stops': route.display(),
                'route_string': str(route)
            })
        
        return routes_list
    
    def delete_route(self, route_id):
        """Delete a route"""
        print(f"\n=== DELETE ROUTE ===")
        print(f"Deleting route: {route_id}")
        print(f"Available routes: {list(self.routes.keys())}")
        
        if route_id not in self.routes:
            print(f"Route not found!")
            raise ValueError(f"Route with ID '{route_id}' not found")
        
        route = self.routes[route_id]
        route_name = route.route_name
        
        # Remove from data structures
        del self.routes[route_id]
        
        # Remove from route_names if exists
        if route_name in self.route_names:
            del self.route_names[route_name]
        
        # Save changes
        if not self.save_routes():
            raise Exception("Failed to save routes after deletion")
        
        print(f"✓ Deleted route '{route_name}'")
        print("=== END DELETE ===\n")
        return True
        
    def search_routes(self, query):
        """Search routes by name or stop name"""
        results = []
        query_lower = query.lower()
        
        for route_id, route in self.routes.items():
            # Search in route name
            if query_lower in route.route_name.lower():
                results.append({
                    'route_id': route.route_id,
                    'route_name': route.route_name,
                    'total_stops': len(route),
                    'match_type': 'route_name'
                })
                continue
            
            # Search in stop names
            current = route.head
            while current:
                stop_name = current.data.get('stop_name', '').lower()
                if query_lower in stop_name:
                    results.append({
                        'route_id': route.route_id,
                        'route_name': route.route_name,
                        'stop_name': current.data.get('stop_name'),
                        'match_type': 'stop_name'
                    })
                    break
                current = current.next
        
        return results
    
    def get_route_stats(self):
        """Get statistics about all routes"""
        total_routes = len(self.routes)
        total_stops = sum(len(route) for route in self.routes.values())
        avg_stops = total_stops / total_routes if total_routes > 0 else 0
        
        return {
            'total_routes': total_routes,
            'total_stops': total_stops,
            'average_stops_per_route': round(avg_stops, 2),
            'routes': [
                {
                    'name': route.route_name,
                    'stops': len(route),
                    'route_id': route.route_id
                }
                for route in self.routes.values()
            ]
        }


# Test the implementation
if __name__ == "__main__":
    print("=" * 60)
    print("Testing Route Management System with Linked Lists")
    print("=" * 60)
    
    # Create route manager
    manager = RouteManager("test_routes.json")
    
    # Create a new route
    print("\n1. Creating new route...")
    route = manager.create_route("Downtown Express", "Express route through downtown")
    print(f"   Created: {route.route_name} (ID: {route.route_id})")
    
    # Add stops to route
    print("\n2. Adding stops to route...")
    stops = [
        {"stop_name": "Central Station", "wait_time": 5},
        {"stop_name": "City Mall", "wait_time": 3},
        {"stop_name": "University", "wait_time": 7},
        {"stop_name": "Hospital", "wait_time": 4},
        {"stop_name": "Airport", "wait_time": 10}
    ]
    
    for stop in stops:
        manager.add_stop(route.route_id, stop)
        print(f"   Added: {stop['stop_name']}")
    
    print(f"\n3. Route display: {route}")
    print(f"   Total stops: {len(route)}")
    
    # Display all stops
    print("\n4. All stops in route:")
    for i, stop_info in enumerate(route.display(), 1):
        print(f"   {i}. {stop_info['data']['stop_name']} (Wait: {stop_info['data'].get('wait_time', 0)} mins)")
    
    # Update a stop
    print("\n5. Updating stop at position 3...")
    updated = manager.update_stop(route.route_id, 3, {"stop_name": "Main University", "wait_time": 8})
    print(f"   Updated: {updated['stop_name']}")
    
    # Remove a stop
    print("\n6. Removing stop at position 2...")
    removed = manager.remove_stop(route.route_id, 2)
    print(f"   Removed: {removed['stop_name']}")
    
    # Display updated route
    print(f"\n7. Updated route: {route}")
    
    # Get route stats
    print("\n8. Route statistics:")
    stats = manager.get_route_stats()
    for key, value in stats.items():
        if key != 'routes':
            print(f"   {key}: {value}")
    
    # Save and reload test
    print("\n9. Testing save and reload...")
    manager.save_routes()
    
    # Create new manager to test loading
    manager2 = RouteManager("test_routes.json")
    loaded_route = manager2.get_route(route.route_id)
    print(f"   Loaded route: {loaded_route.route_name} with {len(loaded_route)} stops")
    
    print("\n" + "=" * 60)
    print("Route Management Test Complete!")
    print("=" * 60)