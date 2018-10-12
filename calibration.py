import cv2
import argparse
import json
import time
import os
import imutils

class Calibrate:

    def get_arguments(self):
        ap = argparse.ArgumentParser()
        ap.add_argument('-l', '--live', required=False,
                        help='Use live video source', action='store_true')
        ap.add_argument('-i', '--image', required=False,
                        help='Still image - for debugging')
        ap.add_argument('-v', '--video', required=False,
                        help='Use pre-recorded video source')
        args = vars(ap.parse_args())
        return args

    def __init__(self):
        self.args = self.get_arguments()

    def selectROI(self, frame):
        print('')
        r = cv2.selectROI(frame)
        return r

    def saveToFile(self, roi):
        if os.path.isfile('settings.json'):
            print('\nSettings file found and read')
            with open('settings.json') as file:
                data = json.load(file)
            data['roi'] = roi
            with open('settings.json', 'w') as file:
                json.dump(data, file)
        else:
            print('\nEither settings file is missing or not readable... Creating new settings file')
            data = {'roi': roi}
            with open('settings.json', 'w') as file:
                json.dump(data, file)

    def image(self):
        # Calibration using an image from a video source
        raise NotImplementedError('Calibration not implemented for images yet')

    def video(self):
        # Ball tracking using a pre-recorded video source
        stream = cv2.VideoCapture(self.args['video'])
        time.sleep(2.0)

        grabbed, frame = stream.read()
        frame = imutils.resize(frame, width=800)
        self.saveToFile(self.selectROI(frame))
        print("Sucessfully updated settings.json")

        stream.release()

    def live(self):
        # Calibration using a live video source
        stream = cv2.VideoCapture(0)
        time.sleep(2.0)

        grabbed, frame = stream.read()
        frame = imutils.resize(frame, width=800)
        self.saveToFile(self.selectROI(frame))
        print("Sucessfully updated settings.json")

        stream.release()

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
    calibrate = Calibrate()
    calibrate.run()
