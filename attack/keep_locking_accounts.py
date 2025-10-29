import requests



def get_user_accounts():
    accounts = []
    
    headers = {
        'Authorization': '{"hash":"ea91c027e512f677a16c742ec3d4baa52a94b657be9431012ef6068e21859490","salt":"STATIC SALT EVERY DEVICE THAT USER LOG-IN TO PAGE TO HAVE THE SAME ONE","iterations":100000,"timestamp":1761592723004}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    url = 'https://cse418-project-mirror.pages.dev/friendPage'

    response = requests.get(url, headers=headers)
    print("status code" , response.status_code)
    print("headers" , response.headers)
    
    return accounts

async def attack_account(username):
    pass

def master():
    pass

if __name__ == "__main__":
    get_user_accounts()