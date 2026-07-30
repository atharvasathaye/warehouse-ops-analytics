
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def check_quantity_mismatches(
    wms_order_items: pd.DataFrame,
    tms_shipments: pd.DataFrame
) -> pd.DataFrame:
    """
    Check for quantity mismatches between WMS order items and TMS shipments.
    
    Args:
        wms_order_items (pd.DataFrame): WMS order items data.
        tms_shipments (pd.DataFrame): TMS shipments data.
        
    Returns:
        pd.DataFrame: DataFrame containing quantity mismatch exceptions.
    """
    logger.info("Checking quantity mismatches...")
    
    # Count items per order in WMS
    wms_counts = wms_order_items.groupby('order_id').size().reset_index(name='wms_item_count')
    
    if 'item_count' in tms_shipments.columns:
        tms_counts = tms_shipments[['order_id', 'item_count']].rename(columns={'item_count': 'tms_item_count'})
    else:
        tms_counts = pd.DataFrame(columns=['order_id', 'tms_item_count'])
        
    merged = pd.merge(wms_counts, tms_counts, on='order_id', how='inner')
    
    mismatches = merged[merged['wms_item_count'] != merged['tms_item_count']]
    
    exceptions = []
    for _, row in mismatches.iterrows():
        exceptions.append({
            'exception_type': 'QUANTITY_MISMATCH',
            'severity': 'WARNING',
            'source_system': 'WMS-TMS',
            'order_id': row['order_id'],
            'product_id': None,
            'description': f"WMS count ({row['wms_item_count']}) != TMS count ({row['tms_item_count']})"
        })
        
    logger.info(f"Found {len(exceptions)} quantity mismatches.")
    
    if not exceptions:
        return pd.DataFrame(columns=[
            'exception_type', 'severity', 'source_system', 'order_id', 'product_id', 'description'
        ])
    return pd.DataFrame(exceptions)


def check_price_mismatches(
    wms_order_items: pd.DataFrame,
    erp_items: pd.DataFrame,
    tolerance: float = 0.05
) -> pd.DataFrame:
    """
    Check for price anomalies in WMS items (internal consistency).
    
    Args:
        wms_order_items (pd.DataFrame): WMS order items data.
        erp_items (pd.DataFrame): ERP items data.
        tolerance (float): Tolerance for price anomalies.
        
    Returns:
        pd.DataFrame: DataFrame containing price anomaly exceptions.
    """
    logger.info("Checking price anomalies...")
    
    exceptions = []
    
    # 1. Negative prices
    negative_prices = wms_order_items[wms_order_items['price'] < 0]
    for _, row in negative_prices.iterrows():
        exceptions.append({
            'exception_type': 'PRICE_ANOMALY',
            'severity': 'WARNING',
            'source_system': 'WMS',
            'order_id': row['order_id'],
            'product_id': row.get('product_id'),
            'description': f"Negative price detected: {row['price']}"
        })
        
    # 2. Zero prices
    zero_prices = wms_order_items[wms_order_items['price'] == 0]
    for _, row in zero_prices.iterrows():
        exceptions.append({
            'exception_type': 'PRICE_ANOMALY',
            'severity': 'WARNING',
            'source_system': 'WMS',
            'order_id': row['order_id'],
            'product_id': row.get('product_id'),
            'description': 'Zero price detected on item'
        })
        
    # 3. Extreme outliers (> 3 std dev from mean)
    if 'product_category_name' in erp_items.columns and 'product_id' in wms_order_items.columns:
        merged = pd.merge(wms_order_items, erp_items[['product_id', 'product_category_name']], on='product_id', how='left')
        
        stats = merged.groupby('product_category_name')['price'].agg(['mean', 'std']).reset_index()
        merged_stats = pd.merge(merged, stats, on='product_category_name', how='left')
        
        valid_stats = merged_stats.dropna(subset=['std'])
        outliers = valid_stats[valid_stats['price'] > (valid_stats['mean'] + 3 * valid_stats['std'])]
        
        for _, row in outliers.iterrows():
            exceptions.append({
                'exception_type': 'PRICE_ANOMALY',
                'severity': 'WARNING',
                'source_system': 'WMS',
                'order_id': row['order_id'],
                'product_id': row.get('product_id'),
                'description': f"Extreme outlier price: {row['price']} (>3 std dev from category mean)"
            })
    else:
        mean_price = wms_order_items['price'].mean()
        std_price = wms_order_items['price'].std()
        
        if pd.notna(std_price):
            outliers = wms_order_items[wms_order_items['price'] > (mean_price + 3 * std_price)]
            for _, row in outliers.iterrows():
                exceptions.append({
                    'exception_type': 'PRICE_ANOMALY',
                    'severity': 'WARNING',
                    'source_system': 'WMS',
                    'order_id': row['order_id'],
                    'product_id': row.get('product_id'),
                    'description': f"Extreme outlier price: {row['price']} (>3 std dev from global mean)"
                })
                
    logger.info(f"Found {len(exceptions)} price anomalies.")
    
    if not exceptions:
        return pd.DataFrame(columns=[
            'exception_type', 'severity', 'source_system', 'order_id', 'product_id', 'description'
        ])
    return pd.DataFrame(exceptions)
