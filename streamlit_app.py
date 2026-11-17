"""
Streamlit Community Cloud Default Entry Point.
Delegates directly to app.py so both 'app.py' and 'streamlit_app.py' work seamlessly.
"""

import os
import sys
import runpy

# Ensure repository root is on sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Execute main application
runpy.run_path(os.path.join(root_dir, "app.py"), run_name="__main__")
