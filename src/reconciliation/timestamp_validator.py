
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def validate_timestamps(
    wms_orders: pd.DataFrame,
    tms_shipments: pd.DataFrame,
    conflict_threshold_hours: float = 2.0
) -> pd.DataFrame:
    """
    Validate timestamps across WMS and TMS for sequence violations, conflicts, etc.
    
    Args:
        wms_orders (pd.DataFrame): WMS orders data.
        tms_shipments (pd.DataFrame): TMS shipments data.
        conflict_threshold_hours (float): Maximum allowed difference between WMS and TMS timestamps.
        
    Returns:
        pd.DataFrame: DataFrame containing timestamp exceptions.
    """
    logger.info("Validating timestamps...")
    exceptions = []
    
    ts_columns = [
        'order_purchase_timestamp', 'order_approved_at', 
        'order_delivered_carrier_date', 'order_delivered_customer_date'
    ]
    
    wms_df = wms_orders.copy()
    for col in ts_columns:
        if col in wms_df.columns:
            wms_df[col] = pd.to_datetime(wms_df[col], errors='coerce')
            
    tms_df = tms_shipments.copy()
    if 'carrier_handoff_date' in tms_df.columns:
        tms_df['carrier_handoff_date'] = pd.to_datetime(tms_df['carrier_handoff_date'], errors='coerce')
        
    current_time = pd.Timestamp(datetime.now())
    
    for _, row in wms_df.iterrows():
        order_id = row['order_id']
        
        if row.get('order_status') == 'delivered':
            if pd.isna(row.get('order_delivered_carrier_date')) or pd.isna(row.get('order_delivered_customer_date')):
                exceptions.append({
                    'exception_type': 'MISSING_TIMESTAMP',
                    'severity': 'INFO',
                    'source_system': 'WMS',
                    'order_id': order_id,
                    'description': 'Delivered order missing carrier or delivery dates',
                    'wms_value': 'missing',
                    'tms_value': None
                })
        
        for col in ts_columns:
            if col in row and pd.notna(row[col]) and row[col] > current_time:
                exceptions.append({
                    'exception_type': 'FUTURE_TIMESTAMP',
                    'severity': 'WARNING',
                    'source_system': 'WMS',
                    'order_id': order_id,
                    'description': f'Future timestamp detected in {col}',
                    'wms_value': str(row[col]),
                    'tms_value': None
                })
                
        purchased = row.get('order_purchase_timestamp')
        approved = row.get('order_approved_at')
        carrier = row.get('order_delivered_carrier_date')
        delivered = row.get('order_delivered_customer_date')
        
        if pd.notna(purchased) and pd.notna(approved) and purchased > approved:
             exceptions.append({
                'exception_type': 'TIMESTAMP_SEQUENCE_VIOLATION',
                'severity': 'WARNING',
                'source_system': 'WMS',
                'order_id': order_id,
                'description': 'purchase > approved',
                'wms_value': f'purchased: {purchased}, approved: {approved}',
                'tms_value': None
            })
            
        if pd.notna(approved) and pd.notna(carrier) and approved > carrier:
             exceptions.append({
                'exception_type': 'TIMESTAMP_SEQUENCE_VIOLATION',
                'severity': 'WARNING',
                'source_system': 'WMS',
                'order_id': order_id,
                'description': 'approved > carrier',
                'wms_value': f'approved: {approved}, carrier: {carrier}',
                'tms_value': None
            })
            
        if pd.notna(carrier) and pd.notna(delivered) and carrier > delivered:
             exceptions.append({
                'exception_type': 'TIMESTAMP_SEQUENCE_VIOLATION',
                'severity': 'WARNING',
                'source_system': 'WMS',
                'order_id': order_id,
                'description': 'carrier > delivered',
                'wms_value': f'carrier: {carrier}, delivered: {delivered}',
                'tms_value': None
            })

    if 'carrier_handoff_date' in tms_df.columns and 'order_delivered_carrier_date' in wms_df.columns:
        merged = pd.merge(
            wms_df[['order_id', 'order_delivered_carrier_date']].dropna(),
            tms_df[['order_id', 'carrier_handoff_date']].dropna(),
            on='order_id', how='inner'
        )
        
        for _, row in merged.iterrows():
            diff = abs((row['order_delivered_carrier_date'] - row['carrier_handoff_date']).total_seconds() / 3600)
            if diff > conflict_threshold_hours:
                exceptions.append({
                    'exception_type': 'TIMESTAMP_CONFLICT',
                    'severity': 'CRITICAL',
                    'source_system': 'WMS-TMS',
                    'order_id': row['order_id'],
                    'description': f'carrier_handoff_date differs by > {conflict_threshold_hours} hours',
                    'wms_value': str(row['order_delivered_carrier_date']),
                    'tms_value': str(row['carrier_handoff_date'])
                })
                
    logger.info(f"Found {len(exceptions)} timestamp exceptions.")
    
    if not exceptions:
        return pd.DataFrame(columns=[
            'exception_type', 'severity', 'source_system', 'order_id', 'description', 'wms_value', 'tms_value'
        ])
    return pd.DataFrame(exceptions)
