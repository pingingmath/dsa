import json
import uuid
from datetime import datetime
import hashlib
import os

class User:
    """User class representing a passenger"""
    def __init__(self, user_id, username, email, phone, full_name, password_hash, role="passenger", created_at=None):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.phone = phone
        self.full_name = full_name
        self.password_hash = password_hash
        self.role = role
        self.created_at = created_at or datetime.now().isoformat()
        self.last_login = None
        self.is_active = True
    
    def to_dict(self):
        """Convert user object to dictionary"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'password_hash': self.password_hash,
            'role': self.role,
            'created_at': self.created_at,
            'last_login': self.last_login,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create user object from dictionary"""
        user = cls(
            user_id=data['user_id'],
            username=data['username'],
            email=data['email'],
            phone=data['phone'],
            full_name=data['full_name'],
            password_hash=data['password_hash'],
            role=data.get('role', 'passenger'),
            created_at=data.get('created_at')
        )
        user.last_login = data.get('last_login')
        user.is_active = data.get('is_active', True)
        return user


class HashTable:
    """Pure from-scratch Hash Table implementation with chaining"""
    
    def __init__(self, capacity=53):  # Prime number for better distribution
        self.capacity = capacity
        self.size = 0
        self.load_factor_threshold = 0.7
        self.buckets = [[] for _ in range(capacity)]  # Array of buckets for chaining
    
    def _custom_hash(self, key):
        """Custom hash function using polynomial rolling hash"""
        if isinstance(key, int):
            key = str(key)
        
        # Polynomial rolling hash: h = Σ (char_code * prime^i) mod capacity
        prime = 31  # Common prime for polynomial hash
        hash_value = 0
        power = 1
        
        for char in str(key):
            hash_value = (hash_value + ord(char) * power) % self.capacity
            power = (power * prime) % self.capacity
        
        return hash_value
    
    def _double_hash(self, key, attempt):
        """Secondary hash function for double hashing"""
        # Using a simple hash: sum of character codes
        hash2 = 0
        for char in str(key):
            hash2 = (hash2 * 31 + ord(char)) % self.capacity
        
        # Ensure hash2 is not 0 and not divisible by capacity
        if hash2 == 0:
            hash2 = 1
        
        return (self._custom_hash(key) + attempt * hash2) % self.capacity
    
    def _find_index(self, key, for_insert=False):
        """
        Find index for key using double hashing with probing
        Returns (bucket_index, position_in_bucket, bucket)
        """
        attempt = 0
        while attempt < self.capacity:
            # Use double hashing for index
            if for_insert:
                index = self._double_hash(key, attempt)
            else:
                index = self._custom_hash(key)
            
            bucket = self.buckets[index]
            
            # Search in the bucket
            for i, (k, v) in enumerate(bucket):
                if k == key:
                    return index, i, bucket
            
            # If not found and we're not inserting, continue probing
            if not for_insert:
                attempt += 1
                if attempt >= self.capacity:
                    break
            else:
                # For insert, return empty slot
                return index, len(bucket), bucket
        
        # Key not found
        return None, None, None
    
    def _rehash(self):
        """Rehash the table when load factor exceeds threshold"""
        print(f"Rehashing: Load factor {self.load_factor():.2f} > {self.load_factor_threshold}")
        
        old_buckets = self.buckets
        self.capacity = self._next_prime(self.capacity * 2)
        self.buckets = [[] for _ in range(self.capacity)]
        self.size = 0
        
        # Reinsert all key-value pairs
        for bucket in old_buckets:
            for key, value in bucket:
                self.insert(key, value)
        
        print(f"Rehashed to new capacity: {self.capacity}")
    
    def _next_prime(self, n):
        """Find next prime number >= n"""
        if n <= 2:
            return 2
        
        # Make it odd
        if n % 2 == 0:
            n += 1
        
        while True:
            # Simple primality test
            is_prime = True
            for i in range(3, int(n**0.5) + 1, 2):
                if n % i == 0:
                    is_prime = False
                    break
            
            if is_prime:
                return n
            n += 2
    
    def load_factor(self):
        """Calculate current load factor"""
        return self.size / self.capacity
    
    def insert(self, key, value):
        """Insert key-value pair into hash table"""
        # Check if rehashing is needed
        if self.load_factor() > self.load_factor_threshold:
            self._rehash()
        
        index, position, bucket = self._find_index(key, for_insert=True)
        
        if index is not None:
            # Check if key already exists in bucket
            for i, (k, v) in enumerate(bucket):
                if k == key:
                    # Update existing key
                    bucket[i] = (key, value)
                    return True
            
            # Insert new key-value pair
            bucket.append((key, value))
            self.size += 1
            return True
        
        return False
    
    def get(self, key):
        """Get value by key"""
        index, position, bucket = self._find_index(key, for_insert=False)
        
        if index is not None and position is not None:
            return bucket[position][1]  # Return value
        
        return None
    
    def delete(self, key):
        """Delete key-value pair"""
        index, position, bucket = self._find_index(key, for_insert=False)
        
        if index is not None and position is not None:
            del bucket[position]
            self.size -= 1
            return True
        
        return False
    
    def exists(self, key):
        """Check if key exists"""
        index, position, bucket = self._find_index(key, for_insert=False)
        return index is not None and position is not None
    
    def keys(self):
        """Get all keys in the hash table"""
        all_keys = []
        for bucket in self.buckets:
            for key, value in bucket:
                all_keys.append(key)
        return all_keys
    
    def values(self):
        """Get all values in the hash table"""
        all_values = []
        for bucket in self.buckets:
            for key, value in bucket:
                all_values.append(value)
        return all_values
    
    def items(self):
        """Get all key-value pairs in the hash table"""
        all_items = []
        for bucket in self.buckets:
            all_items.extend(bucket)
        return all_items
    
    def clear(self):
        """Clear the hash table"""
        self.buckets = [[] for _ in range(self.capacity)]
        self.size = 0
    
    def __len__(self):
        return self.size
    
    def __str__(self):
        result = []
        for i, bucket in enumerate(self.buckets):
            if bucket:
                result.append(f"Bucket {i}: {bucket}")
        return "\n".join(result)
    
    def statistics(self):
        """Get hash table statistics"""
        total_buckets = len(self.buckets)
        empty_buckets = sum(1 for bucket in self.buckets if not bucket)
        used_buckets = total_buckets - empty_buckets
        max_chain_length = max(len(bucket) for bucket in self.buckets)
        avg_chain_length = self.size / used_buckets if used_buckets > 0 else 0
        
        return {
            'capacity': self.capacity,
            'size': self.size,
            'load_factor': self.load_factor(),
            'total_buckets': total_buckets,
            'empty_buckets': empty_buckets,
            'used_buckets': used_buckets,
            'max_chain_length': max_chain_length,
            'avg_chain_length': avg_chain_length
        }


class UserManager:
    """Manages users using pure from-scratch DSA concepts"""
    def __init__(self, users_file):
        self.users_file = users_file
        
        # Using our custom HashTable instead of Python dict
        self.username_index = HashTable()  # Custom hash table for username lookup
        self.email_index = HashTable()     # Custom hash table for email lookup
        self.user_id_index = HashTable()   # Custom hash table for user_id lookup
        
        # Array for storing users (maintaining order)
        self.users = []  # Array for sequential access
        
        self.load_users()
    
    def _hash_password(self, password):
        """Hash password using SHA-256 (for security, not for indexing)"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def load_users(self):
        """Load users from JSON file"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    data = json.load(f)
                    for user_data in data.get('users', []):
                        user = User.from_dict(user_data)
                        self.users.append(user)
                        
                        # Insert into custom hash tables
                        self.username_index.insert(user.username, user)
                        self.email_index.insert(user.email, user)
                        self.user_id_index.insert(user.user_id, user)
                        
                print(f"Loaded {len(self.users)} users")
                print(f"Username index stats: {self.username_index.statistics()}")
            else:
                # Initialize empty users file
                self.save_users()
                print("Created new users file")
                
        except Exception as e:
            print(f"Error loading users: {e}")
            self.users = []
            self.username_index.clear()
            self.email_index.clear()
            self.user_id_index.clear()
    
    def save_users(self):
        """Save users to JSON file"""
        try:
            data = {
                'users': [user.to_dict() for user in self.users],
                'last_updated': datetime.now().isoformat(),
                'total_users': len(self.users),
                'hash_table_stats': {
                    'username_index': self.username_index.statistics(),
                    'email_index': self.email_index.statistics(),
                    'user_id_index': self.user_id_index.statistics()
                }
            }
            with open(self.users_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving users: {e}")
            return False
    
    def create_user(self, username, email, phone, full_name, password, role="passenger"):
        """Create a new user using custom hash tables"""
        # Check if username or email already exists using custom hash tables
        if self.username_index.exists(username):
            raise ValueError("Username already exists")
        if self.email_index.exists(email):
            raise ValueError("Email already registered")
        
        # Generate unique user ID
        user_id = str(uuid.uuid4())
        
        # Create user object
        password_hash = self._hash_password(password)
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            phone=phone,
            full_name=full_name,
            password_hash=password_hash,
            role=role
        )
        
        # Add to data structures
        self.users.append(user)  # Array for sequential access
        
        # Insert into custom hash tables
        success1 = self.username_index.insert(username, user)
        success2 = self.email_index.insert(email, user)
        success3 = self.user_id_index.insert(user_id, user)
        
        if not all([success1, success2, success3]):
            # Rollback if any insertion failed
            self.users.remove(user)
            self.username_index.delete(username)
            self.email_index.delete(email)
            self.user_id_index.delete(user_id)
            raise ValueError("Failed to create user in hash tables")
        
        # Save to file
        if self.save_users():
            print(f"Created user: {username} (ID: {user_id})")
            print(f"Hash table stats after insertion:")
            print(f"  Username index: {self.username_index.statistics()}")
            return user
        else:
            raise ValueError("Failed to save user to file")
    
    def authenticate(self, username, password):
        """Authenticate user using custom hash table lookup"""
        # O(1) lookup in custom hash table
        user = self.username_index.get(username)
        
        if user and user.password_hash == self._hash_password(password) and user.is_active:
            user.last_login = datetime.now().isoformat()
            self.save_users()
            return user
        return None
    
    def get_user(self, username):
        """Get user by username (O(1) lookup in custom hash table)"""
        return self.username_index.get(username)
    
    def get_user_by_email(self, email):
        """Get user by email (O(1) lookup in custom hash table)"""
        return self.email_index.get(email)
    
    def get_user_by_id(self, user_id):
        """Get user by ID (O(1) lookup in custom hash table)"""
        return self.user_id_index.get(user_id)
    
    def username_exists(self, username):
        """Check if username exists (O(1) in custom hash table)"""
        return self.username_index.exists(username)
    
    def email_exists(self, email):
        """Check if email exists (O(1) in custom hash table)"""
        return self.email_index.exists(email)
    
    def get_user_count(self):
        """Get total number of users"""
        return len(self.users)
    
    def get_all_users(self):
        """Get all users"""
        return [user.to_dict() for user in self.users]
    
    def update_user(self, user_id, **kwargs):
        """Update user information"""
        user = self.user_id_index.get(user_id)
        if not user:
            return False
        
        # Update fields
        updated = False
        
        if 'email' in kwargs and kwargs['email'] != user.email:
            if self.email_index.exists(kwargs['email']):
                return False
            
            # Remove old email, add new email in custom hash table
            self.email_index.delete(user.email)
            user.email = kwargs['email']
            self.email_index.insert(user.email, user)
            updated = True
        
        if 'phone' in kwargs:
            user.phone = kwargs['phone']
            updated = True
        
        if 'full_name' in kwargs:
            user.full_name = kwargs['full_name']
            updated = True
        
        if 'password' in kwargs:
            user.password_hash = self._hash_password(kwargs['password'])
            updated = True
        
        if updated:
            self.save_users()
            return True
        
        return False
    
    def delete_user(self, user_id):
        """Delete a user"""
        user = self.user_id_index.get(user_id)
        if not user:
            return False
        
        # Remove from all data structures
        self.users.remove(user)  # Array removal
        
        # Remove from custom hash tables
        self.username_index.delete(user.username)
        self.email_index.delete(user.email)
        self.user_id_index.delete(user.user_id)
        
        self.save_users()
        return True
    
    def get_hash_table_stats(self):
        """Get statistics of all hash tables"""
        return {
            'username_index': self.username_index.statistics(),
            'email_index': self.email_index.statistics(),
            'user_id_index': self.user_id_index.statistics()
        }


# Test the custom hash table implementation
if __name__ == "__main__":
    print("=" * 60)
    print("Testing Custom Hash Table Implementation")
    print("=" * 60)
    
    # Create a test hash table
    ht = HashTable(capacity=10)
    
    # Test insertions
    test_data = [
        ("john_doe", {"name": "John Doe", "age": 25}),
        ("jane_smith", {"name": "Jane Smith", "age": 30}),
        ("alice_wonder", {"name": "Alice Wonder", "age": 22}),
        ("bob_builder", {"name": "Bob Builder", "age": 35}),
        ("charlie_chaplin", {"name": "Charlie Chaplin", "age": 40}),
        ("diana_prince", {"name": "Diana Prince", "age": 28}),
        ("edward_scissor", {"name": "Edward Scissor", "age": 32}),
        ("fiona_fairy", {"name": "Fiona Fairy", "age": 26}),
    ]
    
    print("\n1. Inserting test data...")
    for key, value in test_data:
        ht.insert(key, value)
        print(f"   Inserted: {key} -> Load factor: {ht.load_factor():.3f}")
    
    print(f"\n2. Hash Table Statistics:")
    stats = ht.statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print(f"\n3. Testing lookups (O(1)):")
    print(f"   Get 'john_doe': {ht.get('john_doe')}")
    print(f"   Get 'jane_smith': {ht.get('jane_smith')}")
    print(f"   Get 'non_existent': {ht.get('non_existent')}")
    
    print(f"\n4. Testing existence checks:")
    print(f"   'alice_wonder' exists: {ht.exists('alice_wonder')}")
    print(f"   'ghost_user' exists: {ht.exists('ghost_user')}")
    
    print(f"\n5. Testing deletion:")
    print(f"   Delete 'bob_builder': {ht.delete('bob_builder')}")
    print(f"   'bob_builder' exists after deletion: {ht.exists('bob_builder')}")
    
    print(f"\n6. Testing rehashing (force by adding more items):")
    # Force rehashing by exceeding load factor
    for i in range(20):
        ht.insert(f"test_user_{i}", {"data": f"Test {i}"})
    
    print(f"   Final capacity after rehashing: {ht.capacity}")
    print(f"   Final size: {ht.size}")
    print(f"   Final load factor: {ht.load_factor():.3f}")
    
    print("\n" + "=" * 60)
    print("Custom Hash Table Test Complete!")
    print("=" * 60)