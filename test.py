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
                if '<@UDBJQHB6H>' in m['text'] and 'status' in m['text']:
                    print(m['user'] + " requested pool table status")
                    # Find out if the table is free
                    bot.rtm_send_message(m['channel'], "<@" + m['user'] + "> The pool table is currently free", m['ts'])

if __name__ == '__main__':
    with open('config.json', 'r') as cfgfile:
        config = json.load(cfgfile)

    slackbot(config['slack']['token'])