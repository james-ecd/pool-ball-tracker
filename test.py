#from tracker import Game
import json
import time
import os
import sys
import threading
from slackclient import SlackClient

#def testRun():
#    game = Game()
#    print(game.videoCount('resources\\video-1531832402.mp4'))*/

breakfast_users = ['U632Q7URG', 'U5JRWM6KG', 'U6363BAMB', 'U5TRLN6LC']

def slackbot(token):
    bot = SlackClient(token)

    if bot.rtm_connect(False):
        while bot.server.connected:
            message_handler(bot.rtm_read(), bot)
            time.sleep(1)

def message_handler(msg, bot):
    if len(msg) is 0:
        return
    for m in msg:
        if 'type' in m:
            if m['type'] == 'message' and 'subtype' not in m:
                if '<@UDBJQHB6H>' in m['text']:
                    if 'status' in m['text']:
                        print(m['user'] + ' requested pool table status')
                        # Find out if the table is free
                        bot.rtm_send_message(m['channel'], '<@' + m['user'] + '> The pool table is currently free', m['ts'])
                    elif 'what is going on here' in m['text']:
                        print(m)
                        print(m['user'] + ' requested the current state of affairs')
                        if m['user'] in breakfast_users:
                            print(m['user'] + ' is worthy')
                            print(bot.api_call('chat.postEphemeral', channel=m['channel'], user=m['user'], text='BREAKFAST', as_user=True))
                        else:
                            print(m['user'] + ' is not worthy of the knowledge')

if __name__ == '__main__':
    with open('config.json', 'r') as cfgfile:
        config = json.load(cfgfile)

    slackbot(config['slack']['token'])