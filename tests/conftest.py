import sys
from pathlib import Path

# Make sure `import scraper`, `import database`, etc. work regardless of
# which directory pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
