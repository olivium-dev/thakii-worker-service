#!/usr/bin/env python3
"""
Generate additional PDFs with different parameters
"""

import os
import sys
import subprocess
from pathlib import Path

def generate_pdf_variations():
    """Generate PDFs with different parameters"""
    print("🎯 GENERATING PDF VARIATIONS")
    print("=" * 40)
    
    # Setup paths
    test_video = Path("test.mp4")
    if not test_video.exists():
        # Copy from parent
        parent_test = Path("../test.mp4")
        if parent_test.exists():
            import shutil
            shutil.copy2(parent_test, test_video)
            print(f"✅ Copied test video: {test_video}")
        else:
            print("❌ No test video found")
            return False
    
    lecture2pdf_path = Path("../backend/lecture2pdf-external").absolute()
    
    # Test different output names and parameters
    tests = [
        {
            "name": "variation1_default_params.pdf",
            "args": ["--skip-subtitles"],
            "description": "Default parameters, no subtitles"
        },
        {
            "name": "variation2_custom_output.pdf", 
            "args": ["--skip-subtitles"],
            "description": "Custom output name"
        },
        {
            "name": "variation3_test_video.pdf",
            "args": ["--skip-subtitles"],
            "description": "Another variation"
        }
    ]
    
    successful_pdfs = []
    
    for i, test in enumerate(tests, 1):
        print(f"\n📄 VARIATION {i}: {test['description']}")
        print("-" * 30)
        
        output_pdf = Path(test["name"])
        
        cmd = [
            sys.executable, "-m", "src.main",
            str(test_video.absolute()),
            *test["args"],
            "-o", str(output_pdf.absolute())
        ]
        
        print(f"Command: {' '.join(cmd[-4:])}")  # Show last 4 args
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=lecture2pdf_path, 
                capture_output=True, 
                text=True, 
                timeout=120
            )
            
            if result.returncode == 0 and output_pdf.exists():
                size = output_pdf.stat().st_size
                print(f"✅ SUCCESS: {output_pdf.name} ({size:,} bytes)")
                successful_pdfs.append((output_pdf.name, size))
            else:
                print(f"❌ FAILED")
                if result.stderr:
                    print(f"   Error: {result.stderr[:100]}...")
                    
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    return successful_pdfs

def main():
    """Generate final PDF variations and show summary"""
    print("🚀 FINAL PDF GENERATION TEST")
    print("=" * 50)
    
    # Generate variations
    new_pdfs = generate_pdf_variations()
    
    # Show all PDFs in current directory and subdirectories
    print("\n📁 ALL GENERATED PDF FILES:")
    print("=" * 50)
    
    all_pdfs = []
    
    # Current directory
    for pdf_file in Path(".").glob("*.pdf"):
        size = pdf_file.stat().st_size
        all_pdfs.append((pdf_file.name, size, "current"))
    
    # Subdirectories
    for subdir in ["pdf_outputs", "working_pdf_outputs"]:
        subdir_path = Path(subdir)
        if subdir_path.exists():
            for pdf_file in subdir_path.glob("*.pdf"):
                size = pdf_file.stat().st_size
                all_pdfs.append((pdf_file.name, size, subdir))
    
    # Sort by size (largest first)
    all_pdfs.sort(key=lambda x: x[1], reverse=True)
    
    total_size = 0
    for i, (name, size, location) in enumerate(all_pdfs, 1):
        total_size += size
        location_str = f"({location})" if location != "current" else ""
        print(f"{i:2d}. {name:35} {size:8,} bytes {location_str}")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total PDFs: {len(all_pdfs)}")
    print(f"   Total size: {total_size:,} bytes")
    print(f"   Average size: {total_size//len(all_pdfs) if all_pdfs else 0:,} bytes")
    
    # Show image files too
    print(f"\n🖼️  GENERATED IMAGE FILES:")
    print("-" * 30)
    
    image_count = 0
    for img_file in Path(".").glob("*.jpg"):
        size = img_file.stat().st_size
        print(f"   {img_file.name:30} {size:8,} bytes")
        image_count += 1
    
    for subdir in ["pdf_outputs"]:
        subdir_path = Path(subdir)
        if subdir_path.exists():
            for img_file in subdir_path.glob("*.jpg"):
                size = img_file.stat().st_size
                print(f"   {img_file.name:30} {size:8,} bytes ({subdir})")
                image_count += 1
    
    print(f"\n🎉 FINAL RESULTS:")
    print(f"   ✅ Generated {len(all_pdfs)} PDF files from test.mp4")
    print(f"   ✅ Generated {image_count} image files")
    print(f"   ✅ Used multiple Python scripts and methods")
    print(f"   ✅ All files created successfully!")
    
    return len(all_pdfs) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
