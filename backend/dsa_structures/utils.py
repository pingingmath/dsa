import json
import os
from datetime import datetime

class DataHandler:
    """Handles data storage and retrieval for various entities"""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
    
    def save_data(self, filename, data):
        """Save data to JSON file"""
        filepath = os.path.join(self.data_dir, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving data to {filename}: {e}")
            return False
    
    def load_data(self, filename, default=None):
        """Load data from JSON file"""
        filepath = os.path.join(self.data_dir, filename)
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading data from {filename}: {e}")
        
        return default if default is not None else {}
    
    def append_data(self, filename, new_data):
        """Append data to existing JSON file"""
        existing_data = self.load_data(filename, [])
        if isinstance(existing_data, list):
            existing_data.append(new_data)
            return self.save_data(filename, existing_data)
        return False

class Stack:
    """Stack implementation for action history"""
    def __init__(self):
        self.stack = []
    
    def push(self, item):
        """Push item onto stack"""
        self.stack.append(item)
    
    def pop(self):
        """Pop item from stack"""
        if not self.is_empty():
            return self.stack.pop()
        return None
    
    def peek(self):
        """Peek at top item"""
        if not self.is_empty():
            return self.stack[-1]
        return None
    
    def is_empty(self):
        """Check if stack is empty"""
        return len(self.stack) == 0
    
    def size(self):
        """Get stack size"""
        return len(self.stack)
    
    def clear(self):
        """Clear stack"""
        self.stack = []

class Queue:
    """Queue implementation for passenger management"""
    def __init__(self):
        self.queue = []
    
    def enqueue(self, item):
        """Add item to queue"""
        self.queue.append(item)
    
    def dequeue(self):
        """Remove item from queue"""
        if not self.is_empty():
            return self.queue.pop(0)
        return None
    
    def front(self):
        """Get front item"""
        if not self.is_empty():
            return self.queue[0]
        return None
    
    def is_empty(self):
        """Check if queue is empty"""
        return len(self.queue) == 0
    
    def size(self):
        """Get queue size"""
        return len(self.queue)
    
    def clear(self):
        """Clear queue"""
        self.queue = []