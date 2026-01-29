#!/usr/bin/env python3
"""
Test script for SimpleX Bridge v2
Verifies endpoints and functionality
"""

import requests
import json
import sys
import time

BRIDGE_URL = "http://localhost:8080"

def test_health():
    """Test /health endpoint"""
    print("Testing /health endpoint...")
    try:
        resp = requests.get(f"{BRIDGE_URL}/health", timeout=5)
        data = resp.json()
        
        print(f"  Status: {data.get('status')}")
        print(f"  WS Connected: {data.get('ws_connected')}")
        print(f"  State Contacts: {data.get('state_contacts')}")
        
        if data.get('status') == 'healthy':
            print("  ✅ Health check passed!")
            return True
        else:
            print("  ❌ Bridge is not healthy")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_metrics():
    """Test /metrics endpoint"""
    print("\nTesting /metrics endpoint...")
    try:
        resp = requests.get(f"{BRIDGE_URL}/metrics", timeout=5)
        data = resp.json()
        
        print(f"  Uptime: {data.get('uptime_seconds', 0):.0f}s")
        print(f"  Messages Received: {data.get('messages_received', 0)}")
        print(f"  Messages Forwarded: {data.get('messages_forwarded', 0)}")
        print(f"  Messages Sent: {data.get('messages_sent', 0)}")
        print(f"  Webhook Failures: {data.get('webhook_failures', 0)}")
        print(f"  Connection Errors: {data.get('connection_errors', 0)}")
        print(f"  Messages/min: {data.get('messages_per_minute', 0):.2f}")
        
        message_types = data.get('message_types', {})
        if message_types:
            print(f"  Message Types: {json.dumps(message_types)}")
        
        print("  ✅ Metrics endpoint works!")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_state():
    """Test /state endpoint"""
    print("\nTesting /state endpoint...")
    try:
        resp = requests.get(f"{BRIDGE_URL}/state", timeout=5)
        data = resp.json()
        
        print(f"  Contacts Tracked: {data.get('contacts', 0)}")
        
        recent = data.get('recent', [])
        if recent:
            print(f"  Recent Messages:")
            for item in recent[:3]:
                print(f"    - {item.get('key')}: itemId={item.get('itemId')}")
        
        print("  ✅ State endpoint works!")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_send(contact_id=None, text="Test message from bridge test script"):
    """Test /send endpoint"""
    if contact_id is None:
        print("\nSkipping /send test (no contactId provided)")
        return None
    
    print(f"\nTesting /send endpoint with contactId={contact_id}...")
    try:
        payload = {
            "contactId": int(contact_id),
            "text": text
        }
        
        resp = requests.post(
            f"{BRIDGE_URL}/send",
            json=payload,
            timeout=10
        )
        
        if resp.status_code == 200:
            print(f"  ✅ Message sent successfully!")
            print(f"  Response: {resp.json()}")
            return True
        else:
            print(f"  ❌ Failed with status {resp.status_code}")
            print(f"  Response: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def run_all_tests(contact_id=None):
    """Run all tests"""
    print("=" * 60)
    print("SimpleX Bridge v2 - Test Suite")
    print("=" * 60)
    
    results = []
    
    # Health check
    results.append(("Health", test_health()))
    time.sleep(0.5)
    
    # Metrics
    results.append(("Metrics", test_metrics()))
    time.sleep(0.5)
    
    # State
    results.append(("State", test_state()))
    time.sleep(0.5)
    
    # Send (optional)
    if contact_id:
        results.append(("Send", test_send(contact_id)))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        if result is None:
            status = "⏭️  SKIP"
        print(f"  {name:15s} {status}")
    
    print("=" * 60)
    
    # Overall result
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    print(f"\nPassed: {passed}, Failed: {failed}, Skipped: {skipped}")
    
    if failed > 0:
        print("\n❌ Some tests failed!")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0


if __name__ == "__main__":
    # Parse args
    contact_id = None
    if len(sys.argv) > 1:
        contact_id = sys.argv[1]
        print(f"Will test /send with contactId={contact_id}")
    else:
        print("Tip: Provide contactId as argument to test /send endpoint")
        print(f"Example: {sys.argv[0]} 123\n")
    
    # Run tests
    exit_code = run_all_tests(contact_id)
    sys.exit(exit_code)
