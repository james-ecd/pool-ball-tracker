import json
import time
import os
import sys
import threading
import itertools
from collections import deque
from slackclient import SlackClient
from tracker import Game


class TableStateTracker:
    """
    Keeps a running track of the tables state incase balls left on table after game
    """

    class StateRecord:

        def __init__(self, ballData, previousRecord, first=False):
            self.ballData = ballData
            if first:
                self.hasChanged = False
            else:
                self.hasChanged = previousRecord.ballData != self.ballData

    def __init__(self, game):
        self.stateQueue = deque([], 360)
        self.stateQueue.append(self.StateRecord({'yellow': 0, 'red': 0, 'white': 0, 'black': 0}, None, first=True))
        for i in range(360):
            self.stateQueue.append(self.StateRecord(
                {'yellow': 0, 'red': 0, 'white': 0, 'black': 0},
                self.stateQueue[len(self.stateQueue) - 1]
            ))
        print("Table state tracker initialized")
        self.game = game

    def update(self):
        ballData = self.game.liveCount()
        self.stateQueue.append(self.StateRecord(ballData, self.stateQueue[len(self.stateQueue) - 1]))
        print("Table state tracker updated")

    @property
    def state(self):
        """
        Looks back over the last 5 mins (30 newest queue entries) and returns the determined table state
        :return:
            - Game in progress : bool
            - The state record object of the latest capture
        """
        sample = list(reversed(list(itertools.islice(self.stateQueue, len(self.stateQueue) - 30, len(self.stateQueue)))))
        for r in sample:
            if r.hasChanged:
                return True, self.stateQueue[len(self.stateQueue) - 1]
        else:
            return False, self.stateQueue[len(self.stateQueue) - 1]
        

class BotHandler:

    def __init__(self):
        with open('config.json', 'r') as cfgfile:
            self.config = json.load(cfgfile)

        self.game = Game()
        self.stateTracker = TableStateTracker(self.game)
        self.token = self.config['slack']['token']

    def run(self):
        background = threading.Thread(name="background_updater", target=self.updateRecords)
        foreground = threading.Thread(name="foreground_bot", target=self.slackBot)

        background.start()
        foreground.start()

    def slackBot(self):
        bot = SlackClient(self.token)

        if bot.rtm_connect(False):
            while bot.server.connected:
                self.messageHandler(bot.rtm_read(), bot)
                time.sleep(1)

    def messageHandler(self, msg, bot):
        if len(msg) is 0:
            return
        for m in msg:
            if 'type' in m:
                if m['type'] == 'message' and 'subtype' not in m:
                    if '<@UDBJQHB6H>' in m['text'] and 'status' in m['text']:
                        inUse, balls = self.stateTracker.state
                        response = ""
                        if inUse:
                            response = "<@%s> The pool table is currently in use. Ball count: %s" % (m['user'], balls)
                            bot.rtm_send_message(m['channel'], response, m['ts'])
                        else:
                            response = "<@%s> The pool table is currently free!." % m['user']
                            bot.rtm_send_message(m['channel'], response, m['ts'])

                        print(m['user'] + " requested pool table status and received response: '%s'" % response)

    def updateRecords(self):
        while True:
            self.stateTracker.update()
            time.sleep(9)


if __name__ == '__main__':
    bothandler = BotHandler()
    bothandler.run()
