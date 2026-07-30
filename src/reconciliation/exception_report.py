"""
Module to aggregate all reconciliation exceptions into a unified report.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def generate_exception_report(
    cross_system_exceptions: pd.DataFrame,
    quantity_exceptions: pd.DataFrame,
    price_exceptions: pd.DataFrame,
    timestamp_exceptions: pd.DataFrame
) -> pd.DataFrame:
    """
    Generate a unified exception report from all reconciliation outputs.
    
    Args:
        cross_system_exceptions (pd.DataFrame): Cross-system mismatch exceptions.
        quantity_exceptions (pd.DataFrame): Quantity mismatch exceptions.
        price_exceptions (pd.DataFrame): Price anomaly exceptions.
        timestamp_exceptions (pd.DataFrame): Timestamp validation exceptions.
        
    Returns:
        pd.DataFrame: Unified exception report.
    """
    logger.info("Generating unified exception report...")
    
    dfs = [cross_system_exceptions, quantity_exceptions, price_exceptions, timestamp_exceptions]
    valid_dfs = [df for df in dfs if df is not None and not df.empty]
    
    if not valid_dfs:
        logger.info("No exceptions found. Returning empty report.")
        return pd.DataFrame(columns=[
            'exception_id', 'exception_type', 'severity', 'source_system',
            'order_id', 'product_id', 'description', 'wms_value', 'tms_value',
            'erp_value', 'detected_at'
        ])
        
    report = pd.concat(valid_dfs, ignore_index=True)
    
    required_cols = [
        'exception_type', 'severity', 'source_system', 'order_id', 'product_id', 
        'description', 'wms_value', 'tms_value', 'erp_value'
    ]
    
    for col in required_cols:
        if col not in report.columns:
            report[col] = None
            
    report['exception_id'] = [f"EXC-{str(i+1).zfill(4)}" for i in range(len(report))]
    report['detected_at'] = datetime.now()
    
    severity_order = {'CRITICAL': 1, 'WARNING': 2, 'INFO': 3}
    report['severity_rank'] = report['severity'].map(severity_order).fillna(4)
    report = report.sort_values('severity_rank').drop(columns=['severity_rank'])
    
    final_cols = [
        'exception_id', 'exception_type', 'severity', 'source_system',
        'order_id', 'product_id', 'description', 'wms_value', 'tms_value',
        'erp_value', 'detected_at'
    ]
    report = report[final_cols]
    
    summary = report.groupby(['exception_type', 'severity']).size().reset_index(name='count')
    logger.info("Exception Report Summary:")
    for _, row in summary.iterrows():
        logger.info(f" - {row['severity']} | {row['exception_type']}: {row['count']}")
        
    return report

def save_exception_report(report: pd.DataFrame, output_path: Path) -> Path:
    """
    Save the exception report to a CSV file.
    
    Args:
        report (pd.DataFrame): The exception report DataFrame.
        output_path (Path): Path to save the CSV.
        
    Returns:
        Path: The output path.
    """
    logger.info(f"Saving exception report to {output_path}...")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(output_path, index=False)
    
    logger.info("Exception report saved successfully.")
    return output_path
