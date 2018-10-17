import cv2
import argparse
import numpy as np
import imutils
import json
import time
import uuid


class GameManager:

    def __init__(self):
        self._balls = {'white': {}, 'black': {}, 'yellow': {}, 'red': {}}

    def newBall(self, center, radius, label):
        u = uuid.uuid4()
        self._balls[label][u] = Ball(u, center, radius, label)

    def newFrame(self):
        self._balls = {'white': {}, 'black': {}, 'yellow': {}, 'red': {}}

    @property
    def balls(self):
        return [x for i in self._balls.values() for x in i.values()]

    @property
    def maxBalls(self):
        # Returns dict of ball count bool for max per label
        return self._maxBalls(self._balls)

    @property
    def totalMaxBalls(self):
        # Return one bool if all the max ball counts are satisfied - i.e. a new game is set up
        b = self._maxBalls(self._balls)
        return b['white'] and b['black'] and b['yellow'] and b['red']

    def _maxBalls(self, x):
        return {'white': len(x['white']) == 1,
                'black': len(x['black']) == 1,
                'yellow': len(x['yellow']) == 7,
                'red': len(x['red']) == 7}



class Ball:

    def __init__(self, uid, center, radius, label):
        self.uuid = uid
        self.centerX = center[0]
        self.centerY = center[1]
        self.radius = radius
        self.label = label

    def __eq__(self, other):
        return self.centerX == other.centerX and self.centerY == other.centerY

    def __hash__(self):
        return hash(self.uuid)

    def isBall(self, newCenter, label, missing=False):
        mg = 20
        if missing:
            return label == self.label and self.centerX - mg <= newCenter[0] <= self.centerX + mg and self.centerY - mg <= newCenter[1] <= self.centerY + mg
        return label == self.label and self.centerX-2 <= newCenter[0] <= self.centerX+2 and self.centerY-2 <= newCenter[1] <= self.centerY+2

    def update(self, center):
        self.centerX = center[0]
        self.centerY = center[1]



class Game:

    def get_arguments(self):
        ap = argparse.ArgumentParser()
        ap.add_argument('-l', '--live', required=False,
                        help='Use live video source', action='store_true')
        ap.add_argument('-v', '--video', required=False,
                        help='Use pre-recorded video source')
        ap.add_argument('-d', '--debug', required=False,
                        help='Toggles debugging features (shows masks etc)', action='store_true')
        args = vars(ap.parse_args())

        # TODO - Add checks for file extensions
        return args

    def loadSettings(self):
        with open('settings.json') as f:
            data = json.load(f)
        return data['rgb'], data['hsv'], data['yellow'], data['red'], data['black'], data['white'], data['roi'], data['roiblack']

    def __init__(self):
        self.rgb, self.hsv, self.yellow, self.red, self.black, self.white, self.roi, self.roiblack = self.loadSettings()
        self.yellowLower = tuple(self.yellow[:3])
        self.yellowHigher = tuple(self.yellow[3:])
        self.redLower = tuple(self.red[:3])
        self.redHigher = tuple(self.red[3:])
        self.blackLower = tuple(self.black[:3])
        self.blackHigher = tuple(self.black[3:])
        self.whiteLower = tuple(self.white[:3])
        self.whiteHigher = tuple(self.white[3:])
        self.args = self.get_arguments()
        self.debug = self.args['debug']
        self.gameManager = GameManager()
        self.firstRun = True

    def findCircles(self, frame, mask, label):
        labelColours = {'white': (225, 225, 225), 'black': (0, 0, 0), 'yellow': (225, 225, 0), 'red': (0, 0, 225)}
        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if imutils.is_cv2() else cnts[1]
        center = None

        if len(cnts) > 0:
            for c in cnts:
                ((x, y), radius) = cv2.minEnclosingCircle(c)
                M = cv2.moments(c)
                center = (int(M["m10"] / M["m00"])+1, int(M["m01"] / M["m00"])+1)

                if 3 < radius < 15:
                    self.gameManager.newBall(center, radius, label)
                    if label == 'black':
                        self.drawCircle(frame, center, x, y, radius, label, self.roiblack)
                    else:
                        self.drawCircle(frame, center, x, y, radius, label, self.roi)


    def drawCircle(self, frame, center, x, y, radius, label, r):
        cv2.circle(frame[int(r[1]):int(r[1] + r[3]), int(r[0]):int(r[0] + r[2])], (int(x), int(y)), int(radius),
                   (0, 255, 255), 2)
        cv2.circle(frame[int(r[1]):int(r[1] + r[3]), int(r[0]):int(r[0] + r[2])], center, 5, (0, 0, 255), -1)
        cv2.putText(frame[int(r[1]):int(r[1] + r[3]), int(r[0]):int(r[0] + r[2])], label, (center[0] + 10, center[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

    def printBallStates(self):
        counts = {'yellow': 0, 'red': 0, 'white': 0, 'black': 0}
        for b in self.gameManager.balls:
            counts[b.label] += 1
        print('\n White:%s, Black:%s, Red:%s, Yellow:%s\n' % (counts['white'], counts['black'], counts['red'], counts['yellow']))

    def ballCounts(self):
        counts = {'yellow': 0, 'red': 0, 'white': 0, 'black': 0}
        for b in self.gameManager.balls:
            counts[b.label] += 1
        return counts

    def processFrame(self, frame):
        self.gameManager.newFrame()
        frame = imutils.resize(frame, width=800)
        originialFrame = frame.copy()
        #kernel = np.ones((15, 15), np.float32) / 225
        #smoothed = cv2.filter2D(frame, -1, kernel)
        blur = cv2.GaussianBlur(frame, (5, 5), 0)
        r = self.roi
        rb = self.roiblack

        if self.hsv:
            yellowFilter = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)[int(r[1]):int(r[1]+r[3]), int(r[0]):int(r[0]+r[2])]
            redFilter = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)[int(r[1]):int(r[1]+r[3]), int(r[0]):int(r[0]+r[2])]
            blackFilter = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)[int(rb[1]):int(rb[1]+rb[3]), int(rb[0]):int(rb[0]+rb[2])]
            whiteFilter = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)[int(r[1]):int(r[1]+r[3]), int(r[0]):int(r[0]+r[2])]
        elif self.rgb:
            yellowFilter = blur.copy()[int(r[1]):int(r[1]+r[3]), int(r[0]):int(r[0]+r[2])]
            redFilter = blur.copy()[int(r[1]):int(r[1]+r[3]), int(r[0]):int(r[0]+r[2])]
            blackFilter = blur.copy()[int(rb[1]):int(rb[1]+rb[3]), int(rb[0]):int(rb[0]+rb[2])]
            whiteFilter = blur.copy()[int(r[1]):int(r[1]+r[3]), int(r[0]):int(r[0]+r[2])]
        else:
            raise NotImplementedError('Only HSV or RGB filters are supported. Please use one of these')

        yellowMask = cv2.inRange(yellowFilter, self.yellowLower, self.yellowHigher)
        redMask = cv2.inRange(redFilter, self.redLower, self.redHigher)
        blackMask = cv2.inRange(blackFilter, self.blackLower, self.blackHigher)
        whiteMask = cv2.inRange(whiteFilter, self.whiteLower, self.whiteHigher)

        yellowMask = cv2.erode(yellowMask, None, iterations=1)
        yellowMask = cv2.dilate(yellowMask, None, iterations=1)
        redMask = cv2.erode(redMask, None, iterations=1)
        redMask = cv2.dilate(redMask, None, iterations=1)
        blackMask = cv2.erode(blackMask, None, iterations=1)
        blackMask = cv2.dilate(blackMask, None, iterations=1)
        whiteMask = cv2.erode(whiteMask, None, iterations=1)
        whiteMask = cv2.dilate(whiteMask, None, iterations=1)

        self.findCircles(frame, whiteMask, 'white')
        self.findCircles(frame, redMask, 'red')
        self.findCircles(frame, yellowMask, 'yellow')
        self.findCircles(frame, blackMask, 'black')

        if self.debug:
            cv2.imshow("yellow", yellowMask)
            cv2.imshow("red", redMask)
            cv2.imshow("black", blackMask)
            cv2.imshow("white", whiteMask)

        return frame, originialFrame

    def image(self):
        # Show ball tracking for single image
        img = cv2.imread(self.args['image'], 0)
        imgS = cv2.resize(img, (960, 540))
        cv2.imshow('image', imgS)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def video(self):
        # Ball tracking using a pre-recorded video source
        stream = cv2.VideoCapture(self.args['video'])
        time.sleep(2.0)

        while True:
            grabbed, frame = stream.read()
            if not grabbed:
                break
            frame, originialFrame = self.processFrame(frame)
            cv2.imshow("Frame", frame)
            cv2.imshow("Original", originialFrame)
            self.printBallStates()
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            time.sleep(0.05)
        stream.release()

    def live(self):
        # Ball tracking using a live video source
        stream = cv2.VideoCapture(0)
        time.sleep(2.0)

        while True:
            grabbed, frame = stream.read()
            if not grabbed:
                break
            frame, originialFrame = self.processFrame(frame)
            cv2.imshow("Frame", frame)
            cv2.imshow("Original", originialFrame)
            self.printBallStates()
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            time.sleep(0.05)
        stream.release()

    def videoCount(self, video):
        # Ball tracking using a pre-recorded video source
        self.args = {'video': video}
        stream = cv2.VideoCapture(self.args['video'])
        time.sleep(0.5)

        grabbed, frame = stream.read()
        if not grabbed:
            raise Exception('Problem reading the video file')
        _, _ = self.processFrame(frame)

        values = self.ballCounts()
        stream.release()
        return values

    def liveCount(self):
        # Ball tracking using a live video source
        self.args = {'live': True}
        stream = cv2.VideoCapture(0)
        time.sleep(0.5)

        grabbed, frame = stream.read()
        if not grabbed:
            raise Exception('Problem reading frames from the webcam feed')
        tracked, _ = self.processFrame(frame)

        values = self.ballCounts()
        stream.release()
        return values, tracked

    def imageCount(self, path):
        img = cv2.imread(self.args['image'], 0)
        imgS = cv2.resize(img, (960, 540))
        _, _ = self.processFrame(imgS)

        values = self.ballCounts()
        return values

    def run(self):
        if self.args.get('video', False):
            self.video()
        elif self.args.get('live', False):
            self.live()
        else:
            raise ValueError('Either Video or Webcam not specified. At-least one needed')
        cv2.destroyAllWindows()


if __name__ == '__main__':
    game = Game()
    game.run()
