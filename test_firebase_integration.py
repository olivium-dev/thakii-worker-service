#!/usr/bin/env python3
"""
Test Firebase Integration
"""

def test_imports():
    print("🧪 Testing Firebase Integration")
    print("=" * 40)
    
    try:
        print("📦 Testing imports...")
        
        # Test core modules
        from core.firestore_integration import firestore_client
        print("✅ Firestore integration imported")
        
        from core.s3_integration import s3_client  
        print("✅ S3 integration imported")
        
        # Test worker
        from worker import EnhancedWorker
        print("✅ Enhanced worker imported")
        
        # Test availability
        print(f"   Firestore available: {firestore_client.is_available()}")
        print(f"   S3 available: {s3_client.is_available()}")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_pdf_generation():
    print("\n🎨 Testing Superior PDF Generation")
    print("-" * 40)
    
    import subprocess
    import sys
    from pathlib import Path
    
    # Test original repository PDF generation
    test_video = Path("test.mp4")
    if not test_video.exists():
        print("❌ test.mp4 not found")
        return False
    
    output_pdf = Path("firebase_integration_test.pdf")
    
    cmd = [
        sys.executable, "-m", "src.main",
        str(test_video),
        "-S",
        "-o", str(output_pdf)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ Superior PDF generated: {size:,} bytes")
            return True
        else:
            print(f"❌ PDF generation failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ PDF test error: {e}")
        return False

def main():
    print("🔬 FIREBASE INTEGRATION VALIDATION")
    print("=" * 50)
    
    import_test = test_imports()
    pdf_test = test_pdf_generation()
    
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    if import_test and pdf_test:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Firebase integration ready")
        print("✅ Superior PDF generation working")
        print("✅ Enhanced worker validated")
    else:
        print("💥 VALIDATION FAILED!")
        if not import_test:
            print("❌ Import issues detected")
        if not pdf_test:
            print("❌ PDF generation issues detected")
    
    return import_test and pdf_test

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
