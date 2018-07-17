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
        args = vars(ap.parse_args())

        # TODO - Add checks for file extensions
        return args

    def loadSettings(self):
        with open('settings.json') as f:
            data = json.load(f)
        return data['rgb'], data['hsv'], data['values']

    def __init__(self):
        self.rgb, self.hsv, self.filterValues = self.loadSettings()
        self.args = self.get_arguments()

    def image(self):
        # Show ball tracking for single image
        img = cv2.imread(self.args['image'], 0)
        imgS = cv2.resize(img, (960, 540))
        cv2.imshow('image', imgS)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def video(self):
        # Ball tracking using a pre-recorded video source
        if self.hsv:
            ballLower = self.filterValues[:3]
            ballHigher = self.filterValues[3:]

            stream = cv2.VideoCapture(self.args['video'])
            time.sleep(2.0)

            while True:
                frame = stream.read()
                if frame is None:
                    break

                frame = imutils.resize(frame, width=600)
                blur = cv2.GaussianBlur(frame, (11, 11), 0)
                hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)

                mask = cv2.inRange(hsv, ballLower, ballHigher)
                mask = cv2.erode(mask, None, iterations=2)
                mask = cv2.dilate(mask, None, iterations=2)



        else:
            raise NotImplementedError('RGB filters are not implemented yet. Please use HSV')

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


if __name__ == '__main__':
    game = Game()
    game.run()