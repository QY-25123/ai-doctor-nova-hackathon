# Mock boto3 before any app.llm import so tests run without AWS deps
import sys
from unittest.mock import MagicMock

sys.modules["boto3"] = MagicMock()
sys.modules["botocore"] = MagicMock()
sys.modules["botocore.config"] = MagicMock()
sys.modules["botocore.exceptions"] = MagicMock()
