import sys
import os

# Add the exporter directory to sys.path so 'from api_server import app'
# and 'from api_auth import ...' resolve correctly during pytest collection.
sys.path.insert(0, os.path.dirname(__file__) + "/..")
