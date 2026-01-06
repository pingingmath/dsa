"""
Linked List implementation for Bus Routes
Each route is a linked list of bus stops
"""

class Node:
    """Node class for Linked List - represents a bus stop"""
    def __init__(self, data):
        self.data = data  # Bus stop data
        self.next = None  # Pointer to next stop
        self.prev = None  # For doubly linked list
    
    def __str__(self):
        return f"Node({self.data})"

class LinkedList:
    """Doubly Linked List for bus route management"""
    
    def __init__(self):
        self.head = None  # First stop
        self.tail = None  # Last stop
        self.size = 0     # Number of stops
        self.route_id = None  # Route identifier
        self.route_name = ""  # Route name
    
    def is_empty(self):
        """Check if route is empty"""
        return self.head is None
    
    def add_first(self, data):
        """Add stop at beginning of route"""
        new_node = Node(data)
        
        if self.is_empty():
            self.head = self.tail = new_node
        else:
            new_node.next = self.head
            self.head.prev = new_node
            self.head = new_node
        
        self.size += 1
        return new_node
    
    def add_last(self, data):
        """Add stop at end of route"""
        new_node = Node(data)
        
        if self.is_empty():
            self.head = self.tail = new_node
        else:
            self.tail.next = new_node
            new_node.prev = self.tail
            self.tail = new_node
        
        self.size += 1
        return new_node
    
    def insert_at(self, position, data):
        """Insert stop at specific position (1-based index)"""
        if position < 1 or position > self.size + 1:
            raise IndexError(f"Position {position} out of bounds")
        
        if position == 1:
            return self.add_first(data)
        elif position == self.size + 1:
            return self.add_last(data)
        
        # Find node at position-1
        current = self.head
        for _ in range(position - 2):
            current = current.next
        
        # Insert new node
        new_node = Node(data)
        new_node.next = current.next
        new_node.prev = current
        
        if current.next:
            current.next.prev = new_node
        current.next = new_node
        
        self.size += 1
        return new_node
    
    def remove_first(self):
        """Remove first stop from route"""
        if self.is_empty():
            return None
        
        removed = self.head
        if self.head == self.tail:
            self.head = self.tail = None
        else:
            self.head = self.head.next
            self.head.prev = None
        
        self.size -= 1
        return removed.data
    
    def remove_last(self):
        """Remove last stop from route"""
        if self.is_empty():
            return None
        
        removed = self.tail
        if self.head == self.tail:
            self.head = self.tail = None
        else:
            self.tail = self.tail.prev
            self.tail.next = None
        
        self.size -= 1
        return removed.data
    
    def remove_at(self, position):
        """Remove stop at specific position"""
        if position < 1 or position > self.size:
            raise IndexError(f"Position {position} out of bounds")
        
        if position == 1:
            return self.remove_first()
        elif position == self.size:
            return self.remove_last()
        
        # Find node at position
        current = self.head
        for _ in range(position - 1):
            current = current.next
        
        # Remove node
        current.prev.next = current.next
        current.next.prev = current.prev
        
        self.size -= 1
        return current.data
    
    def get_at(self, position):
        """Get stop at specific position"""
        if position < 1 or position > self.size:
            raise IndexError(f"Position {position} out of bounds")
        
        current = self.head
        for _ in range(position - 1):
            current = current.next
        
        return current.data
    
    def update_at(self, position, data):
        """Update stop at specific position"""
        if position < 1 or position > self.size:
            raise IndexError(f"Position {position} out of bounds")
        
        current = self.head
        for _ in range(position - 1):
            current = current.next
        
        current.data = data
        return current.data
    
    def find_stop(self, stop_id):
        """Find stop by ID (Linear search O(n))"""
        current = self.head
        position = 1
        
        while current:
            if current.data.get('stop_id') == stop_id:
                return current.data, position
            current = current.next
            position += 1
        
        return None, -1
    
    def display(self):
        """Display all stops in route"""
        stops = []
        current = self.head
        position = 1
        
        while current:
            stops.append({
                'position': position,
                'data': current.data
            })
            current = current.next
            position += 1
        
        return stops
    
    def to_list(self):
        """Convert linked list to Python list"""
        result = []
        current = self.head
        
        while current:
            result.append(current.data)
            current = current.next
        
        return result
    
    def clear(self):
        """Clear the entire route"""
        self.head = self.tail = None
        self.size = 0
    
    def __len__(self):
        return self.size
    
    def __str__(self):
        stops = []
        current = self.head
        
        while current:
            stops.append(str(current.data.get('stop_name', 'Unnamed')))
            current = current.next
        
        return f"Route {self.route_name}: {' → '.join(stops)}"