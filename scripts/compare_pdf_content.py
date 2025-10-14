#!/usr/bin/env python3
"""
PDF Content Validator
Analyzes PDF to verify it contains real transcription, not fake content
"""

import sys
import json
from pathlib import Path

try:
    from PyPDF2 import PdfReader
except ImportError:
    print("Error: PyPDF2 not installed")
    sys.exit(1)


class PDFValidator:
    """Validates PDF content for authenticity"""
    
    # Fake content markers from SubtitleGenerator
    FAKE_MARKERS = [
        "Welcome to today's comprehensive lecture session",
        "As you can observe on this detailed slide presentation",
        "This comprehensive diagram clearly illustrates",
        "Let me walk you through this complex process",
        "Notice how these different elements interact",
        "The next section demonstrates practical applications",
        "Here we can observe the detailed results",
        "These important findings have significant implications",
        "Moving forward, let's examine how this connects",
        "In conclusion, these comprehensive concepts"
    ]
    
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.reader = None
        self.num_pages = 0
        self.file_size = 0
        self.all_text = ""
        
    def load_pdf(self) -> bool:
        """Load PDF and extract basic info"""
        if not self.pdf_path.exists():
            print(f"Error: PDF not found at {self.pdf_path}")
            return False
        
        try:
            self.reader = PdfReader(str(self.pdf_path))
            self.num_pages = len(self.reader.pages)
            self.file_size = self.pdf_path.stat().st_size
            
            # Extract all text
            text_parts = []
            for page in self.reader.pages:
                text_parts.append(page.extract_text())
            self.all_text = " ".join(text_parts)
            
            return True
        except Exception as e:
            print(f"Error loading PDF: {e}")
            return False
    
    def check_page_count(self) -> dict:
        """Check if page count indicates real content"""
        # Fake content typically generates 2-8 pages
        # Real content should have more varied page counts
        is_suspicious = self.num_pages <= 2
        
        return {
            "check": "page_count",
            "value": self.num_pages,
            "passed": not is_suspicious,
            "message": f"{'✅' if not is_suspicious else '❌'} {self.num_pages} pages"
        }
    
    def check_file_size(self) -> dict:
        """Check if file size indicates real content"""
        # Fake content PDFs are typically < 300KB
        # Real transcription PDFs are typically > 500KB
        size_kb = self.file_size / 1024
        is_suspicious = size_kb < 300
        
        return {
            "check": "file_size",
            "value": self.file_size,
            "passed": not is_suspicious,
            "message": f"{'✅' if not is_suspicious else '❌'} {size_kb:.1f} KB"
        }
    
    def check_fake_markers(self) -> dict:
        """Check for fake content markers"""
        found_markers = []
        
        for marker in self.FAKE_MARKERS:
            if marker.lower() in self.all_text.lower():
                found_markers.append(marker)
        
        has_fake_content = len(found_markers) > 0
        
        return {
            "check": "fake_markers",
            "value": len(found_markers),
            "found_markers": found_markers,
            "passed": not has_fake_content,
            "message": f"{'✅ No fake markers' if not has_fake_content else f'❌ Found {len(found_markers)} fake markers'}"
        }
    
    def check_real_transcription(self, expected_text: str = None) -> dict:
        """Check for expected real transcription content"""
        # Default: Look for varied, natural language patterns
        # that indicate real speech rather than template text
        
        word_count = len(self.all_text.split())
        has_sufficient_words = word_count > 100
        
        # Check for natural speech patterns
        natural_patterns = [
            "thank you",
            "i think",
            "you know",
            "we can see",
            "let me show",
            "as we discussed",
            "the question is"
        ]
        
        natural_pattern_matches = sum(
            1 for pattern in natural_patterns 
            if pattern in self.all_text.lower()
        )
        
        has_natural_speech = natural_pattern_matches > 0
        
        # If expected text provided, check for it
        has_expected = True
        if expected_text:
            has_expected = expected_text.lower() in self.all_text.lower()
        
        passed = has_sufficient_words and (has_natural_speech or has_expected)
        
        return {
            "check": "real_transcription",
            "word_count": word_count,
            "natural_patterns_found": natural_pattern_matches,
            "has_expected_text": has_expected if expected_text else None,
            "passed": passed,
            "message": f"{'✅' if passed else '❌'} {word_count} words, {natural_pattern_matches} natural patterns"
        }
    
    def validate(self, expected_text: str = None) -> dict:
        """Run all validation checks"""
        if not self.load_pdf():
            return {
                "success": False,
                "error": "Failed to load PDF"
            }
        
        results = {
            "pdf_path": str(self.pdf_path),
            "checks": [
                self.check_page_count(),
                self.check_file_size(),
                self.check_fake_markers(),
                self.check_real_transcription(expected_text)
            ]
        }
        
        # Overall validation
        all_passed = all(check["passed"] for check in results["checks"])
        results["validation_passed"] = all_passed
        results["success"] = True
        
        return results


def main():
    if len(sys.argv) < 2:
        print("Usage: compare_pdf_content.py <pdf_path> [expected_text]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    expected_text = sys.argv[2] if len(sys.argv) > 2 else None
    
    validator = PDFValidator(pdf_path)
    results = validator.validate(expected_text)
    
    # Print results
    print("\n" + "="*50)
    print("PDF VALIDATION REPORT")
    print("="*50)
    print(f"\nPDF: {results['pdf_path']}")
    print(f"\nValidation: {'✅ PASSED' if results.get('validation_passed') else '❌ FAILED'}")
    print("\nChecks:")
    
    for check in results.get("checks", []):
        print(f"  {check['message']}")
        if check.get("found_markers"):
            print(f"    Found markers: {check['found_markers'][:2]}")
    
    print("\n" + "="*50)
    
    # Output JSON for programmatic use
    print("\nJSON Output:")
    print(json.dumps(results, indent=2))
    
    # Exit code
    sys.exit(0 if results.get("validation_passed") else 1)


if __name__ == "__main__":
    main()

