#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║                    STAMPEDE SHIELD                        ║
║              UDP Receiver for Crowd Monitoring            ║
╚═══════════════════════════════════════════════════════════╝

Receives JSON data from ESP32 nodes via UDP broadcast.
Stores data in thread-safe dictionary.

Usage:
    python udp_receiver.py
"""

import socket
import json
import threading
import time
from datetime import datetime


class UDPReceiver:
    """
    UDP Receiver for StampedeShield ESP32 nodes.
    
    Listens for JSON broadcasts from nodes A, B, C and stores
    the latest data in a thread-safe dictionary.
    """
    
    def __init__(self, port=4444):
        """
        Initialize the UDP receiver.
        
        Args:
            port: UDP port to listen on (default: 4444)
        """
        self.port = port
        self.host = "0.0.0.0"  # Listen on all interfaces
        
        # Thread-safe storage for node data
        self.nodes_data = {}
        self.data_lock = threading.Lock()
        
        # Control flags
        self.running = False
        self.receiver_thread = None
        
        # Socket
        self.socket = None
        
        # Statistics
        self.packets_received = 0
        self.packets_failed = 0
    
    def start(self):
        """Start listening for UDP packets in a background thread."""
        if self.running:
            print("[UDP] Already running!")
            return
        
        self.running = True
        
        # Create and configure socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Enable broadcast receiving
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Set timeout so we can check the running flag periodically
        self.socket.settimeout(1.0)
        
        try:
            self.socket.bind((self.host, self.port))
            print(f"[UDP] ✓ Listening on {self.host}:{self.port}")
        except OSError as e:
            print(f"[UDP] ✗ Failed to bind: {e}")
            self.running = False
            return
        
        # Start receiver thread
        self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receiver_thread.start()
        
        print("[UDP] ✓ Receiver thread started")
    
    def stop(self):
        """Stop listening for UDP packets."""
        if not self.running:
            print("[UDP] Not running!")
            return
        
        print("[UDP] Stopping receiver...")
        self.running = False
        
        # Wait for thread to finish
        if self.receiver_thread:
            self.receiver_thread.join(timeout=2.0)
        
        # Close socket
        if self.socket:
            self.socket.close()
            self.socket = None
        
        print("[UDP] ✓ Receiver stopped")
    
    def _receive_loop(self):
        """Main receive loop (runs in background thread)."""
        print("[UDP] Receive loop started, waiting for data...\n")
        
        while self.running:
            try:
                # Receive data (max 1024 bytes)
                data, addr = self.socket.recvfrom(1024)
                
                # Decode and parse JSON
                self._process_packet(data, addr)
                
            except socket.timeout:
                # Timeout is normal, allows checking running flag
                continue
                
            except OSError as e:
                if self.running:  # Only print if not shutting down
                    print(f"[UDP] Socket error: {e}")
                break
    
    def _process_packet(self, data, addr):
        """
        Process a received UDP packet.
        
        Args:
            data: Raw bytes received
            addr: Tuple of (ip, port) of sender
        """
        try:
            # Decode bytes to string
            json_str = data.decode('utf-8').strip()
            
            # Parse JSON
            packet = json.loads(json_str)
            
            # Validate required field
            if 'node' not in packet and 'id' not in packet:
                print(f"[UDP] ⚠ Missing node ID in packet: {json_str[:50]}")
                self.packets_failed += 1
                return
            
            # Get node ID (support both 'node' and 'id' fields)
            node_id = packet.get('node') or packet.get('id')
            
            # Build node data structure
            node_data = {
                'dist': packet.get('dist') or packet.get('distance', 0),
                'pir': packet.get('pir', 0),
                'wifi_count': packet.get('wifi_count', 0),
                'status': packet.get('status', 'unknown'),
                'timestamp': packet.get('timestamp', 0),
                'last_seen': time.time(),
                'ip': addr[0],
                'rssi': packet.get('rssi', 0),
                'uptime': packet.get('uptime', 0)
            }
            
            # Add db field for Node C
            if 'db' in packet:
                node_data['db'] = packet['db']
            
            # Thread-safe update
            with self.data_lock:
                self.nodes_data[node_id] = node_data
            
            self.packets_received += 1
            
            # Print received data
            self._print_node_update(node_id, node_data)
            
        except json.JSONDecodeError as e:
            print(f"[UDP] ⚠ Invalid JSON from {addr[0]}: {e}")
            self.packets_failed += 1
            
        except Exception as e:
            print(f"[UDP] ⚠ Error processing packet: {e}")
            self.packets_failed += 1
    
    def _print_node_update(self, node_id, data):
        """Print formatted node update to console."""
        # Status emoji
        status = data.get('status', 'unknown')
        if status == 'danger':
            emoji = '🔴'
        elif status == 'warning':
            emoji = '🟡'
        elif status == 'safe':
            emoji = '🟢'
        else:
            emoji = '⚪'
        
        # Build output string
        output = f"[NODE {node_id}] {emoji} "
        output += f"Dist: {data['dist']:6.1f}cm | "
        output += f"PIR: {data['pir']} | "
        output += f"WiFi: {data['wifi_count']:2d} | "
        output += f"Status: {status}"
        
        # Add dB for Node C
        if 'db' in data:
            output += f" | dB: {data['db']}"
        
        print(output)
    
    def get_node_data(self, node_id):
        """
        Get latest data for a specific node.
        
        Args:
            node_id: Node identifier ('A', 'B', or 'C')
            
        Returns:
            dict: Node data or None if not found
        """
        with self.data_lock:
            return self.nodes_data.get(node_id, None)
    
    def get_all_data(self):
        """
        Get data for all nodes.
        
        Returns:
            dict: Dictionary of all node data
        """
        with self.data_lock:
            # Return a copy to prevent modification
            return dict(self.nodes_data)
    
    def is_node_alive(self, node_id, timeout=5):
        """
        Check if a node has sent data recently.
        
        Args:
            node_id: Node identifier ('A', 'B', or 'C')
            timeout: Maximum seconds since last data (default: 5)
            
        Returns:
            bool: True if node is alive, False otherwise
        """
        with self.data_lock:
            if node_id not in self.nodes_data:
                return False
            
            last_seen = self.nodes_data[node_id].get('last_seen', 0)
            return (time.time() - last_seen) < timeout
    
    def get_alive_nodes(self, timeout=5):
        """
        Get list of nodes that are currently alive.
        
        Args:
            timeout: Maximum seconds since last data (default: 5)
            
        Returns:
            list: List of alive node IDs
        """
        alive = []
        for node_id in ['A', 'B', 'C']:
            if self.is_node_alive(node_id, timeout):
                alive.append(node_id)
        return alive
    
    def get_overall_status(self):
        """
        Get the overall system status (worst case from all nodes).
        
        Returns:
            str: 'danger', 'warning', 'safe', or 'offline'
        """
        all_data = self.get_all_data()
        
        if not all_data:
            return 'offline'
        
        # Check for any danger
        for node_id, data in all_data.items():
            if self.is_node_alive(node_id):
                if data.get('status') == 'danger':
                    return 'danger'
        
        # Check for any warning
        for node_id, data in all_data.items():
            if self.is_node_alive(node_id):
                if data.get('status') == 'warning':
                    return 'warning'
        
        # Check if any node is alive
        if self.get_alive_nodes():
            return 'safe'
        
        return 'offline'
    
    def get_statistics(self):
        """
        Get receiver statistics.
        
        Returns:
            dict: Statistics dictionary
        """
        return {
            'packets_received': self.packets_received,
            'packets_failed': self.packets_failed,
            'nodes_online': len(self.get_alive_nodes()),
            'running': self.running
        }


# ==================== MAIN TEST BLOCK ====================
if __name__ == "__main__":
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║                    STAMPEDE SHIELD                        ║")
    print("║                 UDP Receiver - Test Mode                  ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    
    # Create and start receiver
    receiver = UDPReceiver(port=4444)
    receiver.start()
    
    print("\nPress Ctrl+C to stop\n")
    print("=" * 60)
    
    try:
        while True:
            time.sleep(3)
            
            # Print status summary every 3 seconds
            print("\n" + "-" * 60)
            print(f"[SUMMARY] Time: {datetime.now().strftime('%H:%M:%S')}")
            
            # Get alive nodes
            alive_nodes = receiver.get_alive_nodes()
            dead_nodes = [n for n in ['A', 'B', 'C'] if n not in alive_nodes]
            
            # Print node status
            if alive_nodes:
                print(f"[SUMMARY] 🟢 Nodes ONLINE: {', '.join(alive_nodes)}")
            if dead_nodes:
                print(f"[SUMMARY] 🔴 Nodes OFFLINE: {', '.join(dead_nodes)}")
            
            # Print overall status
            overall = receiver.get_overall_status()
            if overall == 'danger':
                print(f"[SUMMARY] ⚠️  OVERALL STATUS: 🔴 DANGER")
            elif overall == 'warning':
                print(f"[SUMMARY] ⚠️  OVERALL STATUS: 🟡 WARNING")
            elif overall == 'safe':
                print(f"[SUMMARY] ✓  OVERALL STATUS: 🟢 SAFE")
            else:
                print(f"[SUMMARY] ?  OVERALL STATUS: ⚪ OFFLINE")
            
            # Print statistics
            stats = receiver.get_statistics()
            print(f"[SUMMARY] Packets: ✓{stats['packets_received']} ✗{stats['packets_failed']}")
            
            print("-" * 60)
            
    except KeyboardInterrupt:
        print("\n\n[MAIN] Caught Ctrl+C, shutting down...")
    
    finally:
        receiver.stop()
        print("\n[MAIN] Goodbye!\n")