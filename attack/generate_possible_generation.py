import re
import secrets
import string

def PasswordGenerator (number_generated, max_length):
    regex = re.compile(r'^(?=.*\d)(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{8,13}$')
    
    count = 0
    letters = string.ascii_letters
    digits = string.digits
    symbols = string.punctuation
    
    # Combine all characters
    all_characters = letters + digits + symbols

    with open("./attack/passwords.txt", "w") as f:
        while count < number_generated:
            password = ''
            length = secrets.choice(range(8, max_length))
            # Generate password
            for _ in range(length):
                password += secrets.choice(all_characters)

            if regex.match(password):
                    f.write(password + "\n")
                    count += 1
        
if __name__ == "__main__":
    PasswordGenerator(1000, 13)