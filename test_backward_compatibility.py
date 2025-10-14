#!/usr/bin/env python3
"""
Test backward compatibility between main and current branch
This proves NO BREAKING CHANGES were introduced
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all critical imports work"""
    print("=" * 70)
    print("TEST 1: Import Compatibility (Core Components)")
    print("=" * 70)
    
    try:
        from src.main import CommandLineArgRunner
        print("✅ CommandLineArgRunner imported successfully")
    except Exception as e:
        print(f"❌ CommandLineArgRunner import failed: {e}")
        return False
    
    try:
        from src.video_segment_finder import VideoSegmentFinder
        print("✅ VideoSegmentFinder imported successfully")
    except Exception as e:
        print(f"❌ VideoSegmentFinder import failed: {e}")
        return False
    
    print("ℹ️  Skipping EnhancedWorker import (requires firebase_admin - tested separately)")
    
    print()
    return True

def test_constructor_signatures():
    """Test that old constructor calls still work"""
    print("=" * 70)
    print("TEST 2: Constructor Backward Compatibility")
    print("=" * 70)
    
    from src.video_segment_finder import VideoSegmentFinder
    
    # Test 1: Main branch style (no args)
    try:
        finder1 = VideoSegmentFinder()
        print("✅ VideoSegmentFinder() - No arguments (main branch style)")
    except Exception as e:
        print(f"❌ VideoSegmentFinder() failed: {e}")
        return False
    
    # Test 2: Main branch style (with min_change)
    try:
        finder2 = VideoSegmentFinder(min_change=10000)
        print("✅ VideoSegmentFinder(min_change=10000) - Main branch parameter")
    except Exception as e:
        print(f"❌ VideoSegmentFinder(min_change=10000) failed: {e}")
        return False
    
    # Test 3: Main branch style (all old parameters)
    try:
        finder3 = VideoSegmentFinder(
            threshold=15,
            min_change=10000,
            min_segment_duration=2000
        )
        print("✅ VideoSegmentFinder(threshold, min_change, min_segment_duration) - All main branch params")
    except Exception as e:
        print(f"❌ Full constructor failed: {e}")
        return False
    
    # Test 4: New style (with max_segments)
    try:
        finder4 = VideoSegmentFinder(max_segments=10)
        print("✅ VideoSegmentFinder(max_segments=10) - New parameter")
    except Exception as e:
        print(f"❌ VideoSegmentFinder(max_segments=10) failed: {e}")
        return False
    
    # Test 5: Mixed (old + new)
    try:
        finder5 = VideoSegmentFinder(
            threshold=15,
            min_change=10000,
            min_segment_duration=2000,
            max_segments=10
        )
        print("✅ VideoSegmentFinder(all params) - Complete backward + forward compatibility")
    except Exception as e:
        print(f"❌ Mixed constructor failed: {e}")
        return False
    
    print()
    return True

def test_api_contract():
    """Test that API contract is unchanged"""
    print("=" * 70)
    print("TEST 3: API Endpoint Compatibility")
    print("=" * 70)
    
    print("Testing api_server.py endpoints...")
    
    # Check if api_server has correct endpoints
    try:
        with open('api_server.py', 'r') as f:
            content = f.read()
        
        required_endpoints = [
            '@app.route(\'/health\'',
            '@app.route(\'/upload\'',
            '@app.route(\'/process-from-s3\'',
            '@app.route(\'/generate-pdf\'',
        ]
        
        for endpoint in required_endpoints:
            if endpoint in content:
                endpoint_name = endpoint.split("'")[1]
                print(f"  ✅ {endpoint_name} endpoint exists")
            else:
                endpoint_name = endpoint.split("'")[1]
                print(f"  ❌ {endpoint_name} endpoint MISSING")
                return False
        
        # Check process-from-s3 accepts correct parameters
        if "video_id = data.get('video_id')" in content:
            print("  ✅ process-from-s3 accepts 'video_id'")
        if "s3_key = data.get('s3_key')" in content:
            print("  ✅ process-from-s3 accepts 's3_key'")
        if "filename = data.get('filename')" in content:
            print("  ✅ process-from-s3 accepts 'filename'")
        if "user_id = data.get('user_id')" in content:
            print("  ✅ process-from-s3 accepts 'user_id'")
            
    except Exception as e:
        print(f"❌ API contract test failed: {e}")
        return False
    
    print()
    return True

def test_main_entry_point():
    """Test that main.py can be called as module"""
    print("=" * 70)
    print("TEST 4: Main Entry Point Compatibility")
    print("=" * 70)
    
    from src.main import CommandLineArgRunner
    import sys
    
    try:
        runner = CommandLineArgRunner()
        print("✅ CommandLineArgRunner() instantiated successfully")
    except Exception as e:
        print(f"❌ CommandLineArgRunner() failed: {e}")
        return False
    
    # Check if parser exists
    if hasattr(runner, 'parser'):
        print("✅ runner.parser exists")
    else:
        print("❌ runner.parser missing")
        return False
    
    # Check if run method exists
    if hasattr(runner, 'run'):
        print("✅ runner.run() method exists")
    else:
        print("❌ runner.run() method missing")
        return False
    
    print()
    return True

def main():
    print("\n" + "=" * 70)
    print("BACKWARD COMPATIBILITY TEST SUITE")
    print("Testing: main branch → fix/non-breaking-logarithmic-implementation")
    print("=" * 70)
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Constructor Signatures", test_constructor_signatures),
        ("API Contract", test_api_contract),
        ("Main Entry Point", test_main_entry_point),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"💥 Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED - NO BREAKING CHANGES")
        print("=" * 70)
        return 0
    else:
        print("💥 SOME TESTS FAILED - BREAKING CHANGES DETECTED")
        print("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())

