import argparse
import json
import sqlite3
import time
import threading
import itertools
import cv2
import random
import logging
import datetime
from collections import deque
from slackclient import SlackClient
from tracker import Game
from flask import Flask, request
from flask_restful import Resource, Api
from flask_cors import CORS


class Logger:

    def __init__(self):
        logging.basicConfig(filename="log.log", level=logging.DEBUG)
        logging.getLogger('requests').setLevel(logging.CRITICAL)
        logging.getLogger('werkzeug').setLevel(logging.CRITICAL)
        self.logger = logging.getLogger('')

    def log(self, e, severity='info'):
        e = str(e)
        now = datetime.datetime.now().strftime("%d/%b/%Y %H:%M:%S")
        if severity == 'debug':
            print("[%s][DEBUG] %s" % (now, e))
            self.logger.debug("[%s] %s" % (now, e))
        elif severity == 'error':
            print("[%s][ERROR] %s" % (now, e))
            self.logger.error("[%s] %s" % (now, e))
        elif severity == 'info':
            print("[%s][INFO] %s" % (now, e))
            self.logger.info("[%s] %s" % (now, e))
        else:
            print("[%s][WARNING] %s" % (now, e))
            self.logger.warning("[%s] %s" % (now, e))


class RestHandler:

    class State(Resource):
        def __init__(self, state, logger):
            self.state = state
            self.logger = logger

        def get(self):
            inUse, balls = self.state.state()
            return {'inuse': inUse, 'balls': balls.ballData,
                    'lastChanged': self.state.stateQueue[len(self.state.stateQueue) - 1].hasChanged}

    def __init__(self, state, logger):
        self.state = state
        self.logger = logger
        self.app = Flask(__name__)
        self.api = Api(self.app)
        CORS(self.app)
        self.api.add_resource(self.State, '/state', resource_class_kwargs={'state': self.state, 'logger': self.logger})
        self.thread = threading.Thread(name='rest_thread', target=self.run)
        self.thread.start()

    def run(self):
        self.app.run()


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

    def __init__(self, game, logger):
        self.game = game
        self.logger = logger
        ballData = self.game.liveCount()
        self.stateQueue = deque([], 360)
        self.stateQueue.append(self.StateRecord(ballData, None, first=True))
        for i in range(360):
            self.stateQueue.append(self.StateRecord(ballData, self.stateQueue[len(self.stateQueue) - 1]))
        print("Table state tracker initialized")
        self.folderName = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M")
        self.counter = 0
        self.signature = random.randint(0,1000)

    def update(self):
        ballData, tracked = self.game.liveCount()
        self.counter += 1
        rec = self.StateRecord(ballData, self.stateQueue[len(self.stateQueue) - 1])
        self.stateQueue.append(rec)
        cv2.imwrite("tmp\%s-%s.jpg" % (self.signature, self.counter), tracked)

    def state(self):
        """
        Looks back over the last 5 mins (30 newest queue entries) and returns the determined table state
        :return:
            - Game in progress : bool
            - The state record object of the latest capture
        """
        sample = list(reversed(list(itertools.islice(self.stateQueue, len(self.stateQueue) - 17, len(self.stateQueue)))))
        for r in sample:
            if r.hasChanged:
                return True, self.stateQueue[len(self.stateQueue) - 1]
        else:
            return False, self.stateQueue[len(self.stateQueue) - 1]


class BotHandler:

    class NotificationDB:

        def __init__(self):
            self.conn = sqlite3.connect('notifications.db', check_same_thread=False)
            self.conn.text_factory = str
            self.c = self.conn.cursor()

        def getAllEntries(self):
            # Returns list of tuples for each row in DB
            try:
                return list(self.c.execute("SELECT * FROM notifications"))
            except sqlite3.OperationalError as e:
                return False

        def getEntry(self, id):
            try:
                response = list(self.c.execute("SELECT * FROM notifications WHERE slackid = '%s'" % id))
                if response:
                    return list(self.c.execute("SELECT * FROM notifications WHERE slackid = '%s'" % id))[0]
                else:
                    return False
            except sqlite3.OperationalError as e:
                return False

        def removeEntry(self, id):
            if self.getEntry(id):
                self.c.execute("DELETE FROM notifications WHERE slackid = '%s'" % id)
                return True
            return False

        def addEntry(self, name, id, expire):
            self.c.execute("INSERT INTO notifications VALUES ('%s', '%s', %s)" % (name, id, expire))


    class MessageHandler:

        def __init__(self, tracker, bot, logger, notificationDB, botID, debug):
            self.stateTracker = tracker
            self.bot = bot
            self.logger = logger
            self.notificationDB = notificationDB
            self.id = botID
            self.debug = debug

            self.breakfastUsers = ['U632Q7URG', 'U5JRWM6KG', 'U6363BAMB', 'U5TRLN6LC']

        def process(self, msg):
            if len(msg) is 0:
                return None

            for m in msg:
                if 'type' in m:
                    if m['type'] == 'message' and 'subtype' not in m:
                        valid, command = self.validateCommand(m)
                        if valid:
                            realName, displayName = self.getUserDetails(m)

                            if 'status' == command[0]:
                                self._status(m)
                            elif 'what is going on here' in m['text']:
                                self._breakfast(m)
                            elif 'help' == command[0]:
                                self._help(m)
                            elif 'notify' == command[0]:
                                if len(command) < 2:
                                    self.reply(False, ":error-icon: *Please use correct command syntax. See `help` command for usage*", m)
                                    self.logger.log("User: %s (%s) requested <%s> and got an incorrect syntax error" %
                                            (realName, displayName, command))
                                else:
                                    self._notify(command[1], m)
                            elif 'exit' == command[0]:
                                self._exit(m)
                            else:
                                self.reply(False, ":error-icon: *Command does not exist. See `help` command for usage*", m)
                                self.logger.log("User: %s (%s) requested <%s> and got an incorrect syntax error" %
                                            (realName, displayName, command))

        def validateCommand(self, m):
            if self.isDmToBot(m):
                return True, m['text'].split()
            elif self.id in m['text']:
                return True, m['text'].split()[1:]
            else:
                return False, None

        def isDmToBot(self, m):
            ims = self.bot.api_call("im.list")
            for chan in ims['ims']:
                if chan['id'] == m['channel']:
                    return True
            else:
                return False

        def reply(self, command, reply, m, emotes=None):
            if self.isDmToBot(m):
                self.bot.rtm_send_message(m['channel'], reply)
            else:
                self.bot.rtm_send_message(m['channel'], reply, m['ts'])

            if emotes:
                if type(emotes) != list: emotes = [emotes]
                for emote in emotes:
                    self.addReaction(emote, m['channel'], m['ts'])

            realName, displayName = self.getUserDetails(m)
            if command:
                self.logger.log("User: %s (%s) requested <%s> and received response: %s" %
                            (realName, displayName, command, reply))

        def addReaction(self, emote, channel, ts):
            self.bot.api_call(
                "reactions.add",
                name=emote,
                channel=channel,
                timestamp=ts
            )

        def sendNotification(self, id, msg):
            self.bot.rtm_send_message(self.getUserDmChannelID(id), msg)

        def getUserDetails(self, m):
            userDetails = self.bot.api_call("users.info", user=m['user'])['user']['profile']
            return userDetails['real_name_normalized'], userDetails['display_name_normalized']

        def getUserDmChannelID(self, id):
            ims = self.bot.api_call("im.list")
            for chan in ims['ims']:
                if chan['user'] == id:
                    return chan['id']

        def _exit(self, m):
            if m['user'] in self.breakfastUsers:
                raise Exception("Quit triggered from slack")

        def _notify(self, command, m):
            realName, displayName = self.getUserDetails(m)
            id = m['user']
            if 'cancel' == command:
                # Cancel notification command
                if self.notificationDB.removeEntry(id):
                    self.reply("cancel notification", "*Successfully canceled your notifications*", m)
                else:
                    self.reply("cancel notification", ":error-icon: *You have no current request for notifications*", m)
            else:
                unit = filter(lambda x: x.isalpha(), command)
                amount = filter(lambda x: x.isdigit(), command)
                if unit and amount:
                    if unit == 'm':
                        timeout = int(time.time()) + (int(amount) * 60)
                    elif unit == 'h':
                        timeout = int(time.time()) + (int(amount) * 3600)
                    elif unit == 'd':
                        timeout = int(time.time()) + (int(amount) * 86400)
                    else:
                        self.reply(False, ":error-icon: *Please use correct command syntax. See `help` command for usage*", m)
                        return False
                else:
                    self.reply(False, ":error-icon: *Please use correct command syntax. See `help` command for usage*", m)
                    return False
                if self.notificationDB.getEntry(id):
                    # Notification allready exists so delete and write a new one
                    self.notificationDB.removeEntry(id)
                    self.notificationDB.addEntry(realName, id, timeout)
                    self.logger.log("User: %s (%s) requested notifications for the next %s. Had to overwrite" %
                                    (realName, displayName, command))
                    self.reply(False, "*Old notification request overwritten. You will now receive table status notifications for the next* `%s`" % command, m)
                else:
                    # No notification exists currently for this user
                    self.notificationDB.addEntry(realName, id, timeout)
                    self.logger.log("User: %s (%s) requested notifications for the next %s" % (realName, displayName, command))
                    self.reply(False, "*You will now receive table status notifications for the next* `%s`" % command, m)

        def _status(self, m):
            if self.debug:
                inUse = True
            else:
                inUse, balls = self.stateTracker.state()
            if inUse:
                self.reply("status", "<@%s> The pool table is currently in use :sadpanda:" % m['user'], m, emotes="busy")
            else:
                self.reply("status", "<@%s> The pool table is currently free! :happydance:" % m['user'], m, emotes="free")

        def _breakfast(self, m):
            self.logger.log('%s requested the current state of affairs' % m['user'])
            if m['user'] in self.breakfastUsers:
                self.logger.log('%s is worthy' % m['user'])
                self.bot.api_call('chat.postEphemeral', channel=m['channel'], user=m['user'], text='BREAKFAST', as_user=True)
            else:
                self.logger.log('%s is not worthy of the knowledge' % m['user'])

        def _help(self, m):
            helpMessage = """|---------------|
| *Commands* |
|---------------|
. *status* *:*    _Check if the table is in use_
. *notify* *<timeout>* *:*    _Notify me when the table becomes free for the next <period of time>_
      - usage : `notify 10m`, `notify 2h`, `notify 1d`
. *notify* *cancel* *:*    _Cancels a current notification period_
. *help* *:*    _Displays command usage instructions_

|---------------|
| *Interaction*  |
|---------------|
. *Recommended* :thumbsup:
 - Add `@Cambridge Pool Table` as an app (side bar at the bottom)
 - type commands in that app chat (no longer any need to @ the bot)
. *Frowned Upon* :thumbdown:
 - Tag @Cambridge Pool Table and then give it a command  in a channel
 - Please only do this if you have good reason. No one likes chat spam and there's no reason to do it :buildisbad:"""
            self.reply(False, helpMessage, m)
            realName, displayName = self.getUserDetails(m)
            self.logger.log("User: %s (%s) requested help" % (realName, displayName))

    def __init__(self):
        with open('config.json', 'r') as cfgfile:
            self.config = json.load(cfgfile)
        self.token = self.config['slack']['token']
        self.bot = SlackClient(self.token)
        self.logger = Logger()
        self.args = self.parseArgs()
        self.debug = self.args['debug']
        self.notificationDB = self.NotificationDB()
        if self.debug:
            self.game = None
            self.messageHandler = self.MessageHandler(None, self.bot, self.logger, self.notificationDB, '<@UDK0DP917>', True)
        else:
            self.game = Game()
            self.stateTracker = TableStateTracker(self.game, self.logger)
            self.messageHandler = self.MessageHandler(self.stateTracker, self.bot, self.logger, self.notificationDB, '<@UDBJQHB6H>', False)
            self.loggedFreeTable = False
            self.token = self.config['slack']['token']

    def parseArgs(self):
        ap = argparse.ArgumentParser()
        ap.add_argument('-d', '--debug', required=False,
                        help='Disable any opencv stuff', action='store_true')
        args = vars(ap.parse_args())
        return args

    def run(self):
        foreground = threading.Thread(name="foreground_bot", target=self.slackBot)
        notification = threading.Thread(name="background_notify", target=self.maintainNotificationDB)
        background = threading.Thread(name="background_updater", target=self.updateRecords)
        foreground.start()

        if not self.debug:
            notification.start()
            background.start()
            self.restHandler = RestHandler(self.stateTracker, self.logger)

    def slackBot(self):
        if self.bot.rtm_connect(False, auto_reconnect=True):
            while self.bot.server.connected:
                self.messageHandler.process(self.bot.rtm_read())
                time.sleep(1)

    def notifyUsers(self, msg):
        entries = self.notificationDB.getAllEntries()
        if entries:
            for entry in entries:
                self.messageHandler.sendNotification(entry[1], msg)

    def maintainNotificationDB(self):
        # Runs in a seperate thread and ensures entries removes from DB once timeout expired
        while True:
            now = time.time()
            entries = self.notificationDB.getAllEntries()
            if entries:
                for entry in entries:
                    if now > entry[2]:
                        self.notificationDB.removeEntry(entry[1])
            time.sleep(5)

    def updateRecords(self):
        while True:
            self.stateTracker.update()
            self.trackTableState()
            time.sleep(4)

    def trackTableState(self):
        # Track when table moves from inUse to Free and vice versa
        inUse, _ = self.stateTracker.state()
        if not inUse and not self.loggedFreeTable:
            # Table has become free for the first time
            self.loggedFreeTable = True
            self.logger.log("Table has become free")
            self.notifyUsers("*Notification:* :fire: _The pool table is now free_  :fire:")
        elif inUse and self.loggedFreeTable:
            # Table has transitioned from free to busy
            self.loggedFreeTable = False
            self.logger.log("Table is no longer free")
            self.notifyUsers("*Notification:* :angrylock: _The pool table is no longer free_  :angrylock:")


if __name__ == '__main__':
    bothandler = BotHandler()
    bothandler.run()
