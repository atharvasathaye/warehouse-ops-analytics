"""
Script to check for the Olist dataset files and provide download instructions.
"""
import logging
import argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

EXPECTED_FILES = [
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_products_dataset.csv",
    "product_category_name_translation.csv"
]

def check_files(raw_dir: Path) -> None:
    """
    Check if the expected Kaggle dataset files exist in the specified directory.
    
    Args:
        raw_dir: Path to the raw data directory.
    """
    missing_files = []
    found_files = []
    
    for filename in EXPECTED_FILES:
        filepath = raw_dir / filename
        if filepath.exists():
            found_files.append(filename)
        else:
            missing_files.append(filename)
            
    logger.info(f"Checking for dataset files in {raw_dir}")
    logger.info(f"Found {len(found_files)} files: {', '.join(found_files) if found_files else 'None'}")
    
    if missing_files:
        logger.warning(f"Missing {len(missing_files)} files: {', '.join(missing_files)}")
        print("\n" + "="*80)
        print("DATASET DOWNLOAD INSTRUCTIONS")
        print("="*80)
        print("The required data files are missing. Please follow these steps:")
        print("1. Go to URL: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
        print("2. Download the archive.zip file")
        print(f"3. Extract all CSV files into: {raw_dir.absolute()}")
        print("="*80 + "\n")
    else:
        logger.info("All expected files are present! You are ready to proceed with data splitting.")

def main() -> None:
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Check for required dataset files and print download instructions.")
    parser.add_argument(
        "--raw-dir", 
        type=str, 
        default="data/raw", 
        help="Path to the raw data directory relative to project root."
    )
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent.resolve()
    raw_dir = project_root / args.raw_dir
    
    # Ensure directory exists
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    check_files(raw_dir)

if __name__ == "__main__":
    main()
