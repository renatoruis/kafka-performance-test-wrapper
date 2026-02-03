"""HTTP server for viewing reports"""

import os
import http.server
import socketserver
import webbrowser
from pathlib import Path


class ReportServer:
    """HTTP server to view performance reports"""
    
    def __init__(self, reports_dir: Path, port: int = 8000):
        self.reports_dir = reports_dir
        self.port = port
    
    def serve(self):
        """Start HTTP server"""
        if not self.reports_dir.exists():
            print(f"Reports directory not found: {self.reports_dir}")
            print("Run a test first to generate reports.")
            return
        
        os.chdir(self.reports_dir)
        
        handler = http.server.SimpleHTTPRequestHandler
        
        with socketserver.TCPServer(("", self.port), handler) as httpd:
            print(f"🌐 Serving reports at http://localhost:{self.port}")
            print(f"📁 Directory: {self.reports_dir}")
            print("Press Ctrl+C to stop")
            
            # Try to open browser
            try:
                webbrowser.open(f'http://localhost:{self.port}')
            except:
                pass
            
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n\n👋 Server stopped")
