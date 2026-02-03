"""Configuration management"""

import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """Load and validate YAML configuration"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def __getitem__(self, key: str):
        """Allow dict-like access"""
        return self.config[key]
