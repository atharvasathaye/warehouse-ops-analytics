
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def calculate_dock_to_ship(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate dock-to-ship time in hours.
    
    Args:
        orders (pd.DataFrame): Orders data.
        
    Returns:
        pd.DataFrame: Orders with added dock_to_ship_hours column.
    """
    logger.info("Calculating dock-to-ship time...")
    
    df = orders.copy()
    
    mask = (df['order_status'] == 'delivered') & \
           df['order_approved_at'].notna() & \
           df['order_delivered_carrier_date'].notna()
           
    df_valid = df[mask].copy()
    
    df_valid['order_approved_at'] = pd.to_datetime(df_valid['order_approved_at'], errors='coerce')
    df_valid['order_delivered_carrier_date'] = pd.to_datetime(df_valid['order_delivered_carrier_date'], errors='coerce')
    
    df_valid['dock_to_ship_hours'] = (df_valid['order_delivered_carrier_date'] - df_valid['order_approved_at']).dt.total_seconds() / 3600
    
    df['dock_to_ship_hours'] = None
    df.loc[df_valid.index, 'dock_to_ship_hours'] = df_valid['dock_to_ship_hours']
    
    return df

def calculate_on_time_delivery(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate on-time delivery metric.
    
    Args:
        orders (pd.DataFrame): Orders data.
        
    Returns:
        pd.DataFrame: Orders with added on_time boolean column.
    """
    logger.info("Calculating on-time delivery...")
    
    df = orders.copy()
    
    mask = (df['order_status'] == 'delivered') & \
           df['order_delivered_customer_date'].notna() & \
           df['order_estimated_delivery_date'].notna()
           
    df_valid = df[mask].copy()
    
    df_valid['order_delivered_customer_date'] = pd.to_datetime(df_valid['order_delivered_customer_date'], errors='coerce')
    df_valid['order_estimated_delivery_date'] = pd.to_datetime(df_valid['order_estimated_delivery_date'], errors='coerce')
    
    df_valid['on_time'] = df_valid['order_delivered_customer_date'] <= df_valid['order_estimated_delivery_date']
    
    df['on_time'] = None
    df.loc[df_valid.index, 'on_time'] = df_valid['on_time']
    
    if len(df_valid) > 0:
        otd_pct = df_valid['on_time'].mean() * 100
        logger.info(f"Overall On-Time Delivery: {otd_pct:.2f}%")
        df.attrs['otd_percentage'] = otd_pct
        
    return df
