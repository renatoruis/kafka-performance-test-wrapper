"""Payload file management"""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple


class PayloadManager:
    """Manage JSON payload files"""
    
    def __init__(self, script_dir: Path):
        self.script_dir = script_dir
    
    def create_payload_file(self, payload_file: str) -> Tuple[Optional[str], int]:
        """Create payload file for producer test - converts JSON to single line
        
        Returns:
            (temp_file_path, payload_size_bytes)
        """
        if not payload_file:
            return None, 0
        
        # Check if path is relative, make it relative to script dir
        payload_path = Path(payload_file)
        if not payload_path.is_absolute():
            payload_path = self.script_dir / payload_file
        
        if not payload_path.exists():
            print(f"⚠️  Payload file not found: {payload_file}")
            print(f"   Looked in: {payload_path}")
            return None, 0
        
        # Read JSON and convert to single line
        try:
            with open(payload_path, 'r') as f:
                json_data = json.load(f)
            
            # Minify JSON
            minified_json = json.dumps(json_data, separators=(',', ':'))
            payload_size = len(minified_json.encode('utf-8'))
            
            # Create temp file with minified JSON (single line)
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
            temp_file.write(minified_json)
            temp_file.close()
            
            # Set readable permissions for Docker container
            os.chmod(temp_file.name, 0o644)
            
            return temp_file.name, payload_size
            
        except json.JSONDecodeError as e:
            print(f"⚠️  Invalid JSON in payload file: {e}")
            return None, 0
        except Exception as e:
            print(f"⚠️  Error reading payload file: {e}")
            return None, 0
