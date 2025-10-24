"""
Batch test script to validate parsing accuracy on multiple resumes.

Usage:
    python scripts/run_batch_test.py tests/sample_resumes/


"""

import asyncio
import sys
from pathlib import Path
import json
from typing import List, Dict
import structlog

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.extraction.resume_parser import ResumeParser
from app.utils.logger import setup_logging

setup_logging(log_level="INFO")
logger = structlog.get_logger()


async def test_single_resume(parser: ResumeParser, file_path: Path) -> Dict:
    """Test parsing a single resume."""
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        profile = await parser.parse(file_bytes, file_path.name)
        
        # Calculate metrics
        total_clients = sum(len(exp.client_projects) for exp in profile.experiences)
        total_products = sum(
            len(proj.products)
            for exp in profile.experiences
            for proj in exp.client_projects
        )
        
        return {
            "filename": file_path.name,
            "status": "success",
            "candidate_name": profile.full_name,
            "sfdc_years": profile.sfdc_years,
            "experiences_count": len(profile.experiences),
            "clients_extracted": total_clients,
            "products_at_clients": total_products,
            "has_summary": bool(profile.candidate_overall_summary),
            "summary_length": len(profile.candidate_overall_summary or "")
        }
    except Exception as e:
        logger.error("parse_failed", filename=file_path.name, error=str(e))
        return {
            "filename": file_path.name,
            "status": "failed",
            "error": str(e)
        }


async def main(resume_dir: str):
    """Run batch test on all resumes in directory."""
    resume_path = Path(resume_dir)
    
    if not resume_path.exists():
        print(f"❌ Directory not found: {resume_dir}")
        sys.exit(1)
    
    # Find all PDF/DOCX files
    resume_files = list(resume_path.glob("*.pdf")) + list(resume_path.glob("*.docx"))
    
    if not resume_files:
        print(f"❌ No resumes found in: {resume_dir}")
        sys.exit(1)
    
    print(f"\n🚀 Testing {len(resume_files)} resumes...\n")
    
    parser = ResumeParser()
    results = []
    
    for resume_file in resume_files:
        print(f"📄 Processing: {resume_file.name}")
        result = await test_single_resume(parser, resume_file)
        results.append(result)
        
        if result["status"] == "success":
            print(f"   ✅ {result['candidate_name']}")
            print(f"      SFDC Years: {result['sfdc_years']}")
            print(f"      Clients: {result['clients_extracted']}")
            print(f"      Products at Clients: {result['products_at_clients']}")
        else:
            print(f"   ❌ Failed: {result['error']}")
        print()
    
    # Summary statistics
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]
    
    print("\n" + "="*60)
    print("📊 BATCH TEST RESULTS")
    print("="*60)
    print(f"Total Resumes: {len(results)}")
    print(f"✅ Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"❌ Failed: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")
    
    if successful:
        avg_clients = sum(r["clients_extracted"] for r in successful) / len(successful)
        avg_products = sum(r["products_at_clients"] for r in successful) / len(successful)
        with_summary = sum(1 for r in successful if r["has_summary"])
        
        print(f"\n📈 Metrics (Successful Parses):")
        print(f"   Average Clients Extracted: {avg_clients:.1f}")
        print(f"   Average Products at Clients: {avg_products:.1f}")
        print(f"   With Summary: {with_summary}/{len(successful)} ({with_summary/len(successful)*100:.1f}%)")
    
    if failed:
        print(f"\n❌ Failed Parses:")
        for r in failed:
            print(f"   - {r['filename']}: {r['error']}")
    
    # Save results
    output_file = Path("batch_test_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_batch_test.py <resume_directory>")
        print("Example: python scripts/run_batch_test.py tests/sample_resumes/")
        sys.exit(1)
    
    asyncio.run(main(sys.argv[1]))
