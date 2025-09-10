#!/usr/bin/env python3
"""
Simple PDF Generation Test
Direct test of the main PDF generation script
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("🎯 SIMPLE PDF GENERATION TEST")
    print("=" * 40)
    
    # Setup test video
    test_video = Path("test.mp4")
    
    # Try to copy from parent directory
    parent_test = Path("../test.mp4")
    if parent_test.exists():
        shutil.copy2(parent_test, test_video)
        print(f"✅ Using test video: {test_video}")
    elif Path("samples/quick_test_video.mp4").exists():
        shutil.copy2("samples/quick_test_video.mp4", test_video)
        print(f"✅ Using sample video: {test_video}")
    else:
        print("❌ No test video found")
        return False
    
    # Check lecture2pdf path
    lecture2pdf_path = Path("../backend/lecture2pdf-external")
    if not lecture2pdf_path.exists():
        print(f"❌ lecture2pdf-external not found at {lecture2pdf_path}")
        return False
    
    print(f"✅ Found lecture2pdf at: {lecture2pdf_path}")
    
    # Test 1: Simple PDF without subtitles
    print("\n📄 Test 1: Generate PDF without subtitles")
    output_pdf = Path("simple_test_output.pdf")
    
    cmd = [
        sys.executable, "-m", "src.main",
        str(test_video),
        "--skip-subtitles",
        "-o", str(output_pdf)
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print(f"Working directory: {lecture2pdf_path}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=lecture2pdf_path,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        print(f"Return code: {result.returncode}")
        
        if result.stdout:
            print("Output:")
            print(result.stdout)
        
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        if result.returncode == 0 and output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: Generated {output_pdf}")
            print(f"   File size: {size:,} bytes")
            return True
        else:
            print("❌ FAILED: PDF not generated")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT: Process took too long")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 PDF generation test PASSED!")
    else:
        print("\n💥 PDF generation test FAILED!")
    
    sys.exit(0 if success else 1)
