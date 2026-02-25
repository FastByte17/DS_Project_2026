import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3.2",
        "prompt": "Is a 25-hour phone call possible? Answer yes or no.",
        "stream": False
    }
)

print(response.json()['response'])
# Expected: "No" (or explanation why not)