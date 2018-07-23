import cv2
import argparse
import numpy as np
import imutils
import json
import time


class Game:

    def get_arguments(self):
        ap = argparse.ArgumentParser()
        ap.add_argument('-l', '--live', required=False,
                        help='Use live video source', action='store_true')
        ap.add_argument('-i', '--image', required=False,
                        help='Still image - for debugging')
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
        return data['rgb'], data['hsv'], data['yellow'], data['red'], data['black'], data['white']

    def __init__(self):
        self.rgb, self.hsv, self.yellow, self.red, self.black, self.white = self.loadSettings()
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

    def drawCircles(self, frame, mask, label):
        labelColours = {'white': (225, 225, 225), 'black': (0, 0, 0), 'yellow': (225, 225, 0), 'red': (0, 0, 225)}
        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if imutils.is_cv2() else cnts[1]
        center = None

        if len(cnts) > 0:
            for c in cnts:
                ((x, y), radius) = cv2.minEnclosingCircle(c)
                M = cv2.moments(c)
                center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

                if 7 < radius < 20:
                    cv2.circle(frame, (int(x), int(y)), int(radius),
                               (0, 255, 255), 2)
                    cv2.circle(frame, center, 5, (0, 0, 255), -1)
                    cv2.putText(frame, label, (center[0] + 10, center[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, labelColours[label], 1)

    def processFrame(self, frame):
        frame = imutils.resize(frame, width=800)
        originialFrame = frame.copy()
        #kernel = np.ones((15, 15), np.float32) / 225
        #smoothed = cv2.filter2D(frame, -1, kernel)
        blur = cv2.GaussianBlur(frame, (5, 5), 0)

        if self.hsv:
            yellowFilter = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
            redFilter = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
            blackFilter = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
            whiteFilter = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
        elif self.rgb:
            yellowFilter = blur.copy()
            redFilter = blur.copy()
            blackFilter = blur.copy()
            whiteFilter = blur.copy()
            originialFrame = frame.copy()
        else:
            raise NotImplementedError('Only HSV or RGB filters are supported. Please use one of these')

        yellowMask = cv2.inRange(yellowFilter, self.yellowLower, self.yellowHigher)
        redMask = cv2.inRange(redFilter, self.redLower, self.redHigher)
        blackMask = cv2.inRange(blackFilter, self.blackLower, self.blackHigher)
        whiteMask = cv2.inRange(whiteFilter, self.whiteLower, self.whiteHigher)

        yellowMask = cv2.erode(yellowMask, None, iterations=2)
        yellowMask = cv2.dilate(yellowMask, None, iterations=2)
        redMask = cv2.erode(redMask, None, iterations=2)
        redMask = cv2.dilate(redMask, None, iterations=2)
        blackMask = cv2.erode(blackMask, None, iterations=2)
        blackMask = cv2.dilate(blackMask, None, iterations=2)
        whiteMask = cv2.erode(whiteMask, None, iterations=2)
        whiteMask = cv2.dilate(whiteMask, None, iterations=2)

        self.drawCircles(frame, yellowMask, 'yellow')
        self.drawCircles(frame, redMask, 'red')
        self.drawCircles(frame, blackMask, 'black')
        self.drawCircles(frame, whiteMask, 'white')

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
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            time.sleep(0.10)
        stream.release()

    def live(self):
        # Ball tracking using a live video source
        if self.hsv:
            pass
        else:
            raise NotImplementedError('RGB filters are not implemented yet. Please use HSV')

    def run(self):
        if self.args.get('image', False):
            self.image()
        elif self.args.get('video', False):
            self.video()
        elif self.args.get('live', False):
            self.live()
        else:
            raise ValueError('Either Image, Video or Webcam not specified. At-least one needed')
        cv2.destroyAllWindows()


if __name__ == '__main__':
    game = Game()
    game.run()
