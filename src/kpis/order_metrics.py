
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def calculate_order_cycle_time(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate order cycle time for delivered orders.
    
    Args:
        orders (pd.DataFrame): Orders data.
        
    Returns:
        pd.DataFrame: DataFrame with cycle times. Summary stats are stored in attrs.
    """
    logger.info("Calculating order cycle time...")
    
    df = orders.copy()
    delivered = df[df['order_status'] == 'delivered'].copy()
    
    delivered['order_purchase_timestamp'] = pd.to_datetime(delivered['order_purchase_timestamp'], errors='coerce')
    delivered['order_delivered_customer_date'] = pd.to_datetime(delivered['order_delivered_customer_date'], errors='coerce')
    
    delivered['cycle_time_days'] = (delivered['order_delivered_customer_date'] - delivered['order_purchase_timestamp']).dt.total_seconds() / 86400
    
    valid_times = delivered['cycle_time_days'].dropna()
    stats = {
        'mean': valid_times.mean() if not valid_times.empty else None,
        'median': valid_times.median() if not valid_times.empty else None,
        'p90': valid_times.quantile(0.90) if not valid_times.empty else None,
        'p95': valid_times.quantile(0.95) if not valid_times.empty else None
    }
    
    logger.info(f"Cycle time stats: {stats}")
    
    df['cycle_time_days'] = None
    df.update(delivered[['cycle_time_days']])
    
    df.attrs['cycle_time_stats'] = stats
    return df

def calculate_fill_rate(wms_order_items: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate order fill rate.
    
    Args:
        wms_order_items (pd.DataFrame): WMS order items data.
        orders (pd.DataFrame): Orders data.
        
    Returns:
        pd.DataFrame: DataFrame containing fill rate per order.
    """
    logger.info("Calculating fill rate...")
    
    ordered = wms_order_items.groupby('order_id').size().reset_index(name='items_ordered')
    
    delivered_orders = orders[orders['order_status'] == 'delivered']['order_id']
    delivered_items = wms_order_items[wms_order_items['order_id'].isin(delivered_orders)]
    delivered_counts = delivered_items.groupby('order_id').size().reset_index(name='items_delivered')
    
    fill_df = pd.merge(ordered, delivered_counts, on='order_id', how='left')
    fill_df['items_delivered'] = fill_df['items_delivered'].fillna(0)
    
    fill_df['fill_rate'] = fill_df['items_delivered'] / fill_df['items_ordered']
    
    total_ordered = fill_df['items_ordered'].sum()
    total_delivered = fill_df['items_delivered'].sum()
    overall_fill_rate = total_delivered / total_ordered if total_ordered > 0 else 0.0
    
    logger.info(f"Overall fill rate: {overall_fill_rate:.2%}")
    fill_df.attrs['overall_fill_rate'] = overall_fill_rate
    
    return fill_df
