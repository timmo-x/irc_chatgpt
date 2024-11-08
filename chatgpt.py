import openai
import socket
import ssl
import time
import configparser
import json
import os

# Load configuration
config = configparser.ConfigParser()
config.read("chatgpt.conf")

openai.api_key = config.get('openai', 'api_key')
model = config.get('chatcompletion', 'model')
context = config.get('chatcompletion', 'context')
temperature = config.getfloat('chatcompletion', 'temperature')
max_tokens = config.getint('chatcompletion', 'max_tokens')
top_p = config.getfloat('chatcompletion', 'top_p')
frequency_penalty = config.getfloat('chatcompletion', 'frequency_penalty')
presence_penalty = config.getfloat('chatcompletion', 'presence_penalty')
request_timeout = config.getint('chatcompletion', 'request_timeout')

server = config.get('irc', 'server')
port = config.getint('irc', 'port')
use_ssl = config.getboolean('irc', 'ssl')
channels = config.get('irc', 'channels').split(',')
nickname = config.get('irc', 'nickname')
ident = config.get('irc', 'ident')
realname = config.get('irc', 'realname')

# Define keywords for triggering responses
keywords = ["bot", "gpt", "ai", "assistant"]

# Memory file for conversation history
MEMORY_FILE = "chat_memory.json"

# Load or initialize memory
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)
      
# Memory starts with 10 but can be adjusted to increase recall
def get_recent_memory(memory, identifier, limit=10):
    return memory.get(identifier, [])[-limit:]

def add_to_memory(memory, identifier, role, content):
    if identifier not in memory:
        memory[identifier] = []
    memory[identifier].append({"role": role, "content": content})
    save_memory(memory)

# Fetch response from ChatGPT API
def get_chatgpt_response(question, recent_memory):
    messages = [{"role": "system", "content": context}]
    messages.extend(recent_memory)
    messages.append({"role": "user", "content": question})

    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            request_timeout=request_timeout
        )
        return response.choices[0].message['content']
    except openai.error.OpenAIError as e:
        print(f"API error: {e}")
        return "Sorry, an API error occurred."
    except Exception as e:
        print(f"Unexpected error: {e}")
        return "Sorry, an unexpected error occurred."

# Connect to IRC server
def connect_irc():
    while True:
        try:
            irc = socket.create_connection((server, port))
            if use_ssl:
                irc = ssl.wrap_socket(irc)
            irc.send(bytes(f"USER {ident} 0 * :{realname}\n", "UTF-8"))
            irc.send(bytes(f"NICK {nickname}\n", "UTF-8"))
            print(f"Connected to IRC server: {server}")

            while True:
                data = irc.recv(4096).decode("UTF-8", errors="ignore")
                print(f"Received: {data}")
                
                if "001" in data:
                    print("Connected successfully. Joining channels...")
                    for channel in channels:
                        irc.send(bytes(f"JOIN {channel}\n", "UTF-8"))
                        print(f"Joined channel: {channel}")
                    return irc
                elif data.startswith("PING"):
                    irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))
        except Exception as e:
            print(f"Connection failed: {e}")
            time.sleep(5)

# Main function to listen and respond
def main():
    irc = connect_irc()
    memory = load_memory()
    while True:
        data = irc.recv(4096).decode("UTF-8", errors="ignore")
        print(f"Received: {data}")

        if data.startswith("PING"):
            irc.send(bytes(f"PONG {data.split()[1]}\n", "UTF-8"))
        
        elif "PRIVMSG" in data:
            user = data.split('!')[0][1:]
            message = ':'.join(data.split(':')[2:])
            channel = data.split(' PRIVMSG ')[-1].split(' :')[0]
            
            if any(keyword in message.lower() for keyword in keywords):
                question = message.strip()
                identifier = channel if channel != nickname else user
                recent_memory = get_recent_memory(memory, identifier)
                answer = get_chatgpt_response(question, recent_memory)
                
                add_to_memory(memory, identifier, "user", question)
                add_to_memory(memory, identifier, "assistant", answer)

                response_channel = channel if channel != nickname else user
                irc.send(bytes(f"PRIVMSG {response_channel} :{answer}\n", "UTF-8"))

if __name__ == "__main__":
    main()
