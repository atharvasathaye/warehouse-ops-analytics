"""
Utility functions for the Warehouse Operations Analytics project.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml

def get_project_root() -> Path:
    """
    Returns the root directory of the project.
    
    Returns:
        Path: Project root directory.
    """
    return Path(__file__).resolve().parent.parent.parent

def load_config(config_path: Path | None = None) -> Dict[str, Any]:
    """
    Loads configuration settings from a YAML file.
    
    Args:
        config_path (Path | None, optional): Path to the config file. 
            Defaults to config/settings.yaml relative to project root.
            
    Returns:
        Dict[str, Any]: Dictionary containing configuration settings.
    """
    if config_path is None:
        config_path = get_project_root() / "config" / "settings.yaml"
    
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)

def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configures and returns the project logger.
    
    Args:
        level (str, optional): Logging level. Defaults to 'INFO'.
        
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger("warehouse_ops")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

def parse_timestamps(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """
    Converts string columns to datetime in a DataFrame.
    
    Args:
        df (pd.DataFrame): Input DataFrame.
        columns (List[str]): List of column names to convert.
        
    Returns:
        pd.DataFrame: DataFrame with converted timestamp columns.
    """
    df_out = df.copy()
    for col in columns:
        if col in df_out.columns:
            df_out[col] = pd.to_datetime(df_out[col], errors='coerce')
    return df_out

def ensure_directories(config: Dict[str, Any]) -> None:
    """
    Creates data directories if they don't exist based on the config.
    
    Args:
        config (Dict[str, Any]): Configuration dictionary.
    """
    root_dir = get_project_root()
    data_paths = config.get("data_paths", {})
    
    for _, path_str in data_paths.items():
        dir_path = root_dir / path_str
        dir_path.mkdir(parents=True, exist_ok=True)
