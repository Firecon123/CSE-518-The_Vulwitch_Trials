import requests
import sys


def send_code(api_url: str, user_id: str, email: str) -> None:
    payload = {
        "userId": user_id,
        "email": email,
    }
    resp = requests.post(api_url, json=payload)
    resp.raise_for_status()

if __name__ == "__main__":
    api_url = sys.argv[1]
    user_id = sys.argv[2]
    email = sys.argv[3]
    repeat = int(sys.argv[4])
    for _ in range(repeat):
        send_code(api_url, user_id, email)
