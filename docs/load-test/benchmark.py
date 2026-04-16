# Load test skeleton using locust
# Install: pip install locust
# Usage: locust -f benchmark.py --host http://localhost:8000

from locust import HttpUser, task, between

TARGET_HOST = "http://localhost:8000"

# Configure your load test user behavior and thresholds here
