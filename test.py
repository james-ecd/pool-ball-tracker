from tracker import Game


authToken = 'xoxb-2527431116-453636589221-mmnC9RZTsEpywUoHhoVaSVpi'

def testRun():
    game = Game()
    print(game.videoCount('resources\\video-1531832402.mp4'))


if __name__ == '__main__':
    testRun()