#!/usr/bin/env python3
"""
Backend Test Suite for Geography Resolver API
Tests the sansadx-backend geography endpoints
"""

import requests
import json
import sys
from typing import Dict, Any

# Test configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 10

def test_geography_stats():
    """Test GET /geography/stats endpoint"""
    print("🧪 Testing GET /geography/stats")
    
    try:
        response = requests.get(f"{BASE_URL}/geography/stats", timeout=TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            
            # Validate expected fields
            expected_fields = ['loaded', 'localities_count', 'stations_count', 'buildings_count', 'aliases_count']
            missing_fields = [field for field in expected_fields if field not in data]
            
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
                return False
            
            if data.get('loaded') is True:
                print("✅ Geography index is loaded")
                return True
            else:
                print("❌ Geography index is not loaded")
                return False
                
        else:
            print(f"❌ Status: {response.status_code}")
            print(f"❌ Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_geography_reload():
    """Test POST /geography/reload endpoint"""
    print("\n🧪 Testing POST /geography/reload")
    
    try:
        response = requests.post(f"{BASE_URL}/geography/reload", timeout=TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            
            # Validate expected fields
            if 'status' in data and 'stats' in data:
                print("✅ Reload response has expected structure")
                return True
            else:
                print("❌ Reload response missing expected fields")
                return False
                
        else:
            print(f"❌ Status: {response.status_code}")
            print(f"❌ Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_geography_resolve_muglihal():
    """Test POST /geography/resolve with Muglihal location"""
    print("\n🧪 Testing POST /geography/resolve?text=Water problem in Muglihal")
    
    try:
        params = {"text": "Water problem in Muglihal"}
        response = requests.post(f"{BASE_URL}/geography/resolve", params=params, timeout=TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            
            # Validate expected resolution
            if data.get('location_resolved') is True:
                expected_assembly = "Belgaum_North"
                expected_parliamentary = "Belagavi"
                
                if (data.get('assembly_constituency') == expected_assembly and 
                    data.get('parliamentary_constituency') == expected_parliamentary):
                    print("✅ Location resolved correctly")
                    return True
                else:
                    print(f"❌ Incorrect resolution. Expected: {expected_assembly}/{expected_parliamentary}")
                    return False
            else:
                print("❌ Location not resolved")
                return False
                
        else:
            print(f"❌ Status: {response.status_code}")
            print(f"❌ Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_geography_resolve_booth():
    """Test POST /geography/resolve with booth number"""
    print("\n🧪 Testing POST /geography/resolve?text=Issue at booth 1")
    
    try:
        params = {"text": "Issue at booth 1"}
        response = requests.post(f"{BASE_URL}/geography/resolve", params=params, timeout=TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            
            # Check if location was resolved by station number
            if data.get('location_resolved') is True:
                if data.get('match_type') == 'station_number':
                    print("✅ Location resolved by station number")
                    return True
                else:
                    print(f"✅ Location resolved by {data.get('match_type')}")
                    return True
            else:
                print("❌ Location not resolved")
                return False
                
        else:
            print(f"❌ Status: {response.status_code}")
            print(f"❌ Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_geography_resolve_unknown():
    """Test POST /geography/resolve with unknown location"""
    print("\n🧪 Testing POST /geography/resolve?text=Unknown place xyz")
    
    try:
        params = {"text": "Unknown place xyz"}
        response = requests.post(f"{BASE_URL}/geography/resolve", params=params, timeout=TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            
            # Should return location_resolved: false
            if data.get('location_resolved') is False:
                print("✅ Unknown location correctly not resolved")
                return True
            else:
                print("❌ Unknown location was incorrectly resolved")
                return False
                
        else:
            print(f"❌ Status: {response.status_code}")
            print(f"❌ Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_server_connectivity():
    """Test basic server connectivity"""
    print("🧪 Testing server connectivity")
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
        
        if response.status_code == 200:
            print(f"✅ Server is accessible at {BASE_URL}")
            print(f"📊 Response: {response.json()}")
            return True
        else:
            print(f"❌ Server returned status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 GEOGRAPHY RESOLVER API TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Server Connectivity", test_server_connectivity),
        ("Geography Stats", test_geography_stats),
        ("Geography Reload", test_geography_reload),
        ("Resolve Muglihal", test_geography_resolve_muglihal),
        ("Resolve Booth Number", test_geography_resolve_booth),
        ("Resolve Unknown Location", test_geography_resolve_unknown),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())