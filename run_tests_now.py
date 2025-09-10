#!/usr/bin/env python3
"""
Execute PDF Generation Tests Now
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    print("🚀 EXECUTING PDF GENERATION TESTS")
    print("=" * 50)
    
    # Change to worker service directory
    worker_dir = Path(__file__).parent
    os.chdir(worker_dir)
    
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check if test video exists
    test_video_paths = [
        Path("../test.mp4"),
        Path("samples/quick_test_video.mp4"),
        Path("test.mp4")
    ]
    
    test_video = None
    for path in test_video_paths:
        if path.exists():
            test_video = path
            break
    
    if test_video:
        print(f"✅ Found test video: {test_video}")
    else:
        print("❌ No test video found")
        print("Available files:")
        for f in Path(".").iterdir():
            if f.suffix.lower() in ['.mp4', '.avi', '.mov']:
                print(f"   {f}")
        return False
    
    # Run the individual tests
    print("\n🧪 Running individual script tests...")
    try:
        result = subprocess.run([
            sys.executable, "test_individual_scripts.py"
        ], capture_output=True, text=True, timeout=600)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Tests completed successfully!")
        else:
            print(f"❌ Tests failed with return code: {result.returncode}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Tests timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
