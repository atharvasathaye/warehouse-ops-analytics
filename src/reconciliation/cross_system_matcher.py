
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def match_orders_across_systems(
    wms_orders: pd.DataFrame,
    tms_shipments: pd.DataFrame,
    erp_items: pd.DataFrame,
    wms_order_items: pd.DataFrame
) -> pd.DataFrame:
    """
    Detect mismatches between WMS, TMS, and ERP systems.
    
    Detects:
    - MISSING_TMS_SHIPMENT: Orders in WMS (status='delivered') with no matching shipment in TMS.
    - ORPHAN_TMS_SHIPMENT: Shipments in TMS with no matching order in WMS.
    - MISSING_ERP_PRODUCT: product_ids referenced in wms_order_items that don't exist in erp_items.
    - ORPHAN_ERP_PRODUCT: Products in ERP not referenced by any WMS order item.
    
    Args:
        wms_orders (pd.DataFrame): WMS orders data.
        tms_shipments (pd.DataFrame): TMS shipments data.
        erp_items (pd.DataFrame): ERP product items data.
        wms_order_items (pd.DataFrame): WMS order items data.
        
    Returns:
        pd.DataFrame: DataFrame containing exception records.
    """
    logger.info("Matching orders across systems...")
    exceptions = []
    
    # MISSING_TMS_SHIPMENT
    delivered_wms = wms_orders[wms_orders['order_status'] == 'delivered']
    missing_tms = delivered_wms[~delivered_wms['order_id'].isin(tms_shipments['order_id'])]
    for _, row in missing_tms.iterrows():
        exceptions.append({
            'exception_type': 'MISSING_TMS_SHIPMENT',
            'severity': 'CRITICAL',
            'source_system': 'WMS-TMS',
            'order_id': row['order_id'],
            'product_id': None,
            'description': 'Delivered order in WMS missing from TMS'
        })
        
    # ORPHAN_TMS_SHIPMENT
    orphan_tms = tms_shipments[~tms_shipments['order_id'].isin(wms_orders['order_id'])]
    for _, row in orphan_tms.iterrows():
        exceptions.append({
            'exception_type': 'ORPHAN_TMS_SHIPMENT',
            'severity': 'WARNING',
            'source_system': 'TMS',
            'order_id': row['order_id'],
            'product_id': None,
            'description': 'Shipment in TMS missing from WMS orders'
        })
        
    # MISSING_ERP_PRODUCT
    wms_product_ids = wms_order_items['product_id'].dropna().unique()
    erp_product_ids = erp_items['product_id'].dropna().unique()
    missing_erp = set(wms_product_ids) - set(erp_product_ids)
    for pid in missing_erp:
        exceptions.append({
            'exception_type': 'MISSING_ERP_PRODUCT',
            'severity': 'CRITICAL',
            'source_system': 'WMS-ERP',
            'order_id': None,
            'product_id': pid,
            'description': 'Product ID in WMS not found in ERP'
        })
        
    # ORPHAN_ERP_PRODUCT
    orphan_erp = set(erp_product_ids) - set(wms_product_ids)
    for pid in orphan_erp:
        exceptions.append({
            'exception_type': 'ORPHAN_ERP_PRODUCT',
            'severity': 'INFO',
            'source_system': 'ERP',
            'order_id': None,
            'product_id': pid,
            'description': 'Product ID in ERP not referenced in any WMS order'
        })
        
    logger.info(f"Found {len(exceptions)} cross-system exceptions.")
    
    if not exceptions:
        return pd.DataFrame(columns=[
            'exception_type', 'severity', 'source_system', 'order_id', 'product_id', 'description'
        ])
        
    return pd.DataFrame(exceptions)
