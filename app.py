"""Streamlit Community Cloud Entrypoint."""
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the main dashboard application
import src.ui.app

