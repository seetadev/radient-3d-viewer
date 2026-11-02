__author__ = 'sdpatro'
import os
import sys

from controllers import main

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) >= 2 else os.environ.get("PORT")
    if not port:
        sys.exit("Error: please pass a port (python run.py 8888) or set PORT.")
    main.run(port, debug=os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))
