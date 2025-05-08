import json

class Fun_Emojis:
       @staticmethod
       def load_emojis():
         with open('data/commands/fun/emojis.json', 'r') as file:
            return json.load(file)
         
emojis = Fun_Emojis.load_emojis()

blank_emoji = emojis['blank_emoji']