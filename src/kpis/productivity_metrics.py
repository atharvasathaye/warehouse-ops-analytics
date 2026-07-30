
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def calculate_picks_per_hour(
    order_items: pd.DataFrame,
    orders: pd.DataFrame,
    seconds_per_pick: int = 45
) -> pd.DataFrame:
    """
    Calculate estimated picks per hour per day.
    
    IMPORTANT: This metric is SIMULATED since Olist dataset has no actual labor data.
    It relies on an estimated time per pick to derive productivity.
    
    Args:
        order_items (pd.DataFrame): Order items data.
        orders (pd.DataFrame): Orders data.
        seconds_per_pick (int): Estimated seconds to pick a single item.
        
    Returns:
        pd.DataFrame: Daily productivity metrics (date, total_picks, estimated_hours, picks_per_hour).
    """
    logger.info("Calculating simulated picks per hour...")
    
    merged = pd.merge(order_items, orders, on='order_id', how='inner')
    
    picks_per_order = merged.groupby(['order_id', 'order_purchase_timestamp']).size().reset_index(name='item_count')
    
    picks_per_order['order_purchase_timestamp'] = pd.to_datetime(picks_per_order['order_purchase_timestamp'], errors='coerce')
    picks_per_order['date'] = picks_per_order['order_purchase_timestamp'].dt.date
    
    picks_per_order['pick_time_hours'] = (picks_per_order['item_count'] * seconds_per_pick) / 3600
    
    daily_agg = picks_per_order.groupby('date').agg(
        total_picks=('item_count', 'sum'),
        estimated_hours=('pick_time_hours', 'sum')
    ).reset_index()
    
    daily_agg['picks_per_hour'] = daily_agg['total_picks'] / daily_agg['estimated_hours']
    daily_agg['picks_per_hour'] = daily_agg['picks_per_hour'].fillna(0)
    
    return daily_agg
