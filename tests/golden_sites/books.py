import subprocess
import json
import os
from pathlib import Path

def test_books_toscrape():
    """
    Golden Site Test: books.toscrape.com
    Verifies the end-to-end flow in CI mode.
    """
    url = "https://books.toscrape.com"
    print(f"Starting Golden Test for {url}...")
    
    # Run scrapewizard in CI mode
    cmd = [
        "python", "-m", "scrapewizard.cli.main", "scrape",
        "--url", url,
        "--ci",
        "--verbose"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Test Failed! Exit code: {result.returncode}")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        assert False
        
    print("Scrape command finished successfully.")
    
    # Find the project directory from stdout
    # "Project directory: C:\Users\User\scrapewizard_projects\project_books_toscrape_com_2026_01_21_0710"
    project_dir = None
    for line in result.stdout.split('\n'):
        if "Project directory:" in line:
            project_dir = Path(line.split("Project directory:")[1].strip())
            break
            
    assert project_dir is not None, "Project directory not found in output"
    assert project_dir.exists(), f"Project directory {project_dir} does not exist"
    
    # Verify output data
    data_file = project_dir / "output" / "data.json"
    assert data_file.exists(), f"Data file {data_file} not found"
    
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert len(data) > 0, "No data scraped"
    print(f"Test Passed! Scraped {len(data)} items.")
    
    # Check for Excel file if also generated
    excel_file = project_dir / "output" / "data.xlsx"
    # Note: our CI mode currently defaults to json, but we could check whatever results were generated.
    
if __name__ == "__main__":
    try:
        test_books_toscrape()
    except Exception as e:
        print(f"Golden test failed: {e}")
        exit(1)
