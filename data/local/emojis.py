import json

class Emojis:
       @staticmethod
       def load_emojis():
         with open('data/local/emojis.json', 'r') as file:
            return json.load(file)
         
emojis = Emojis.load_emojis()

blank_emoji = emojis['blank_emoji']
neko_lurk = emojis['neko_lurk']