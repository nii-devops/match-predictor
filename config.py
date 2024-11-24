import os


import random
import string


def generate_secret_key():
    """Generate a random 32-character string."""
    invalid_chars = ['=' ,'#', ";", "'", '"', "(", ")", "[", "]", "{", "}"]

    characters = string.ascii_letters + string.digits + string.punctuation
    secret_key = ""

    while len(secret_key) < 33:
        i = random.choice(characters)
        if i not in invalid_chars:
            secret_key += i  
    # Read existing lines from .env file
    with open('.env', 'r') as env_file:
        lines = env_file.readlines()

    # Check if SECRET_KEY exists and replace it
    with open('.env', 'w') as env_file:
        secret_key_written = False  # Track if the secret key has been written
        for line in lines:
            if line.startswith('SECRET_KEY='):
                env_file.write(f'SECRET_KEY={secret_key}\n')  # Replace the existing key
                secret_key_written = True  # Mark that the key has been written
            else:
                env_file.write(line)  # Write unchanged lines
        
        if not secret_key_written:  # If SECRET_KEY was not found, append it
            env_file.write(f'SECRET_KEY={secret_key}\n')  # Append the new key


generate_secret_key()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('LOCAL_DB_URI')


