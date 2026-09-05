import requests

BASE_URL = "https://gps.easytracking.bg/api"

def login(email, password):
    """Login with email and password, returns user_api_hash"""
    response = requests.post(f"{BASE_URL}/login", json={
        "email": email,
        "password": password
    })
    response.raise_for_status()
    return response.json()["user_api_hash"]
