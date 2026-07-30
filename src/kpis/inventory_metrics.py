
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def calculate_inventory_turns(order_items: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate monthly inventory turns.
    
    Args:
        order_items (pd.DataFrame): Order items data.
        orders (pd.DataFrame): Orders data.
        
    Returns:
        pd.DataFrame: Monthly inventory turns metrics.
    """
    logger.info("Calculating inventory turns...")
    
    merged = pd.merge(order_items, orders, on='order_id', how='inner')
    delivered = merged[merged['order_status'] == 'delivered'].copy()
    
    delivered['order_purchase_timestamp'] = pd.to_datetime(delivered['order_purchase_timestamp'], errors='coerce')
    delivered = delivered.dropna(subset=['order_purchase_timestamp'])
    
    delivered['period'] = delivered['order_purchase_timestamp'].dt.to_period('M')
    
    monthly_cogs = delivered.groupby('period')['price'].sum().reset_index(name='cogs')
    monthly_cogs = monthly_cogs.sort_values('period')
    
    monthly_cogs['avg_inventory'] = monthly_cogs['cogs'].rolling(window=3, min_periods=1).mean()
    
    monthly_cogs['turns'] = (monthly_cogs['cogs'] * 12) / monthly_cogs['avg_inventory']
    monthly_cogs['turns'] = monthly_cogs['turns'].replace([np.inf, -np.inf], np.nan)
    
    monthly_cogs['days_on_hand'] = 365 / monthly_cogs['turns']
    monthly_cogs['days_on_hand'] = monthly_cogs['days_on_hand'].replace([np.inf, -np.inf], np.nan)
    
    monthly_cogs['period'] = monthly_cogs['period'].astype(str)
    
    return monthly_cogs

def classify_abc(order_items: pd.DataFrame, a_threshold: float = 0.80, b_threshold: float = 0.95) -> pd.DataFrame:
    """
    Perform ABC classification on products based on total revenue.
    
    Args:
        order_items (pd.DataFrame): Order items data.
        a_threshold (float): Cumulative threshold for A class.
        b_threshold (float): Cumulative threshold for B class.
        
    Returns:
        pd.DataFrame: Product ABC classification.
    """
    logger.info("Calculating ABC classification...")
    
    product_rev = order_items.groupby('product_id')['price'].sum().reset_index(name='total_revenue')
    product_rev = product_rev.sort_values('total_revenue', ascending=False).reset_index(drop=True)
    
    total_rev = product_rev['total_revenue'].sum()
    if total_rev > 0:
        product_rev['cumulative_pct'] = product_rev['total_revenue'].cumsum() / total_rev
    else:
        product_rev['cumulative_pct'] = 0.0
        
    def get_class(pct):
        if pct <= a_threshold:
            return 'A'
        elif pct <= b_threshold:
            return 'B'
        else:
            return 'C'
            
    product_rev['abc_class'] = product_rev['cumulative_pct'].apply(get_class)
    product_rev['rank'] = product_rev.index + 1
    
    return product_rev
