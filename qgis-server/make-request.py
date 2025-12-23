import requests

url = "http://localhost:5000/ml-request"

# Send ONLY the parameters you want to change (e.g., just the output folder)
payload = {
    "CLASSIFICATION_FOLDER": "C:/Users/User/OneDrive/Desktop/TEST"
}

response = requests.post(url, json=payload)
print(response.json())