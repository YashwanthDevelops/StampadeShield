import socket
import threading
import queue
import json
import time
from typing import Dict, Any, Callable, Optional, List

class UDPReceiver:
    def __init__(self, port: int = 5005, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self.running = False
        self.socket = None
        self.thread = None
        
        # Thread-safe queue for incoming data
        self.data_queue = queue.Queue()
        
        # Storage for latest data and timestamps
        self.latest_data: Dict[str, Dict[str, Any]] = {}
        self.last_seen_time: Dict[str, float] = {} # node_id -> timestamp
        
        # Threading lock for shared data access
        self.lock = threading.Lock()
        
        # Callbacks
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Timeout configuration
        self.timeout_seconds = 3.0

    def start(self):
        """Start the UDP listening thread."""
        if self.running:
            return
        
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to the port
        try:
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(1.0) # Set a timeout so we can check self.running occasionally
            print(f"UDP Receiver started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Error binding UDP socket: {e}")
            self.running = False
            return

        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the listening thread and close the socket."""
        self.running = False
        if self.thread:
            self.thread.join()
        if self.socket:
            self.socket.close()
        print("UDP Receiver stopped.")

    def _listen_loop(self):
        """Internal loop to listen for incoming UDP packets."""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                message = data.decode('utf-8')
                try:
                    parsed_data = json.loads(message)
                    self._process_data(parsed_data)
                except json.JSONDecodeError:
                    print(f"Received malformed JSON from {addr}: {message}")
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error receiving data: {e}")

    def _process_data(self, data: Dict[str, Any]):
        """Process received JSON data."""
        if "id" not in data:
            return # Ignore data without an ID

        node_id = data["id"]
        current_time = time.time()
        
        with self.lock:
            self.latest_data[node_id] = data
            self.last_seen_time[node_id] = current_time
        
        self.data_queue.put(data)
        
        # Trigger callbacks
        for callback in self.callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"Error in callback: {e}")

    def get_latest(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest reading from a specific node. Returns None if node is offline or unknown."""
        with self.lock:
            if node_id not in self.latest_data:
                return None
            
            # Check for timeout
            if time.time() - self.last_seen_time.get(node_id, 0) > self.timeout_seconds:
                return None # Node is considered offline
            
            return self.latest_data[node_id]

    def get_all_latest(self) -> Dict[str, Dict[str, Any]]:
        """Get a dictionary of all active nodes and their latest readings."""
        active_nodes = {}
        current_time = time.time()
        
        with self.lock:
            for node_id, timestamp in self.last_seen_time.items():
                if current_time - timestamp <= self.timeout_seconds:
                    active_nodes[node_id] = self.latest_data[node_id]
        
        return active_nodes

    def on_data(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback function for new data."""
        self.callbacks.append(callback)
