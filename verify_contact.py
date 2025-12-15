
import requests
import json

url = "http://127.0.0.1:8000/api/v1/contact/"

payload = {
    "name": "Test User",
    "email": "test@example.com",
    "subject": "Test Subject",
    "message": "This is a test message."
}

headers = {
    'Content-Type': 'application/json'
}

response = requests.post(url, headers=headers, data=json.dumps(payload))

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 201:
    print("SUCCESS: Contact created successfully.")
else:
    print("FAILURE: Contact creation failed.")
