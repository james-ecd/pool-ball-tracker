import json
import time
import os
import sys
import glob
import threading
import itertools
from collections import deque
from slackclient import SlackClient
from tracker import Game
from flask import Flask, request
from flask_restful import Resource, Api

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

    def updateImage(self):
        # Look for most recent file in directory
        filename = "img/%s.jpg" % str(min([int(x[:-4]) for x in glob.glob("img/*.jpg")]))
        ballData = self.game.imageCount(filename)
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
        self.restHandler = RestHandler(self.stateTracker)
        self.token = self.config['slack']['token']
        self.breakfastUsers = ['U632Q7URG', 'U5JRWM6KG', 'U6363BAMB', 'U5TRLN6LC']

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
                    if '<@UDBJQHB6H>' in m['text']:
                        if 'status' in m['text']:
                            inUse, balls = self.stateTracker.state
                            response = ""
                            if inUse:
                                response = "<@%s> The pool table is currently in use. Ball count: %s" % (m['user'], balls)
                                bot.rtm_send_message(m['channel'], response, m['ts'])
                            else:
                                response = "<@%s> The pool table is currently free!." % m['user']
                                bot.rtm_send_message(m['channel'], response, m['ts'])

                            print(m['user'] + " requested pool table status and received response: '%s'" % response)
                        elif 'what is going on here' in m['text']:
                            print(m['user'] + ' requested the current state of affairs')
                            if m['user'] in self.breakfastUsers:
                                print(m['user'] + ' is worthy')
                                print(bot.api_call('chat.postEphemeral', channel=m['channel'], user=m['user'],
                                                   text='BREAKFAST', as_user=True))
                            else:
                                print(m['user'] + ' is not worthy of the knowledge')

    def updateRecords(self):
        while True:
            self.stateTracker.update()
            time.sleep(9)

    def updateRecordsImage(self):
        while True:
            self.stateTracker.updateImage()
            time.sleep(9)


class RestHandler:
    
    class State(Resource):
        def get(self, state):
            inUse, balls = state.state
            return {'inuse': inUse, 'balls': balls}

    def __init__(self, state):
        self.state = state
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.api.add_resource(self.State, '/state', resource_class_args={'state': self.state})
        self.thread = threading.Thread(name='rest_thread', target=self.run)
        self.thread.start()

    def run(self):
        self.app.run()


if __name__ == '__main__':
    bothandler = BotHandler()
    bothandler.run()
