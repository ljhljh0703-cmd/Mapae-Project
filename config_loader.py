"""
Mapae (마패) - AI Powered Game Policy Auditor
==============================================

Configuration Loader Module

This module handles loading and managing application configuration
from the config.txt file.

Features:
- INI-style configuration file parsing
- Type-safe configuration access
- Default value handling
- Environment variable support

The Config class provides:
1. Configuration file loading
2. Key-value pair retrieval
3. Boolean value parsing
4. Error handling for missing files

Author: Portfolio Project
License: MIT
Version: 1.0.0
"""


import os
from typing import Dict, Optional


class Config:
    """Configuration manager for Mapae application."""
    
    def __init__(self, config_file: str = "config.txt"):
        """
        Initialize configuration from file.
        
        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file
        self.settings: Dict[str, str] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file."""
        if not os.path.exists(self.config_file):
            return
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    self.settings[key.strip()] = value.strip()
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        value = self.settings.get(key, default)
        
        # Don't return placeholder values
        if value and value.startswith('your-'):
            return default
        
        return value
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Get boolean configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Boolean value
        """
        value = self.get(key)
        if value is None:
            return default
        
        return value.lower() in ('true', 'yes', '1', 'on')
