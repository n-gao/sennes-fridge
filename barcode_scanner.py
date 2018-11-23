import cv2
from pyzbar import pyzbar
import numpy as np
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import time
from datetime import *
from urllib.parse import quote_plus
from urllib.request import urlopen
import json
from Crypto.Cipher import Salsa20
import base64
 
def detect(image):
	# convert the image to grayscale
	gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
 
	# compute the Scharr gradient magnitude representation of the images
	# in both the x and y direction using OpenCV 2.4
	ddepth = cv2.CV_32F
	gradX = cv2.Sobel(gray, ddepth=ddepth, dx=1, dy=0, ksize=-1)
	gradY = cv2.Sobel(gray, ddepth=ddepth, dx=0, dy=1, ksize=-1)
 
	# subtract the y-gradient from the x-gradient
	gradient = cv2.subtract(gradX, gradY)
	gradient = cv2.convertScaleAbs(gradient)
 
	# blur and threshold the image
	blurred = cv2.blur(gradient, (9, 9))
	(_, thresh) = cv2.threshold(blurred, 225, 255, cv2.THRESH_BINARY)
 
	# construct a closing kernel and apply it to the thresholded image
	kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
	closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
 
	# perform a series of erosions and dilations
	closed = cv2.erode(closed, None, iterations=4)
	closed = cv2.dilate(closed, None, iterations=4)
 
	# find the contours in the thresholded image
	cnts = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE)
	cnts = cnts[1]
 
	# if no contours were found, return None
	if len(cnts) == 0:
		return None
 
	# otherwise, sort the contours by area and compute the rotated
	# bounding box of the largest contour
	c = sorted(cnts, key=cv2.contourArea, reverse=True)[0]
	rect = cv2.minAreaRect(c)
	box = cv2.boxPoints(rect)
	box = np.int0(box)
 
	# return the bounding box of the barcode
	return box

scanned = {}
cam = None


def encrypt(msg, key='STbHC6sDeLE1xoFfkIBzVA==:nr8EOH0'):
    keyBytes = key.encode('utf-8')
    cipher = Salsa20.new(key=keyBytes)
    encrypted = cipher.nonce + cipher.encrypt(msg.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')


def decrypt(msg, key='STbHC6sDeLE1xoFfkIBzVA==:nr8EOH0'):
    keyBytes = key.encode('utf-8')
    encrypted = base64.b64decode(msg.encode('utf-8'))
    cipher = Salsa20.new(key=keyBytes, nonce=encrypted[:8])
    decrypted = cipher.decrypt(encrypted[8:])
    return decrypted.decode('utf-8')


def detect_direction(points):
    diff = points[0] - points[-1]
    if abs(diff) < width/4:
        return None
    if diff < 0:
        return 'left-to-right'
    if diff > 0:
        return 'right-to-left'


def continous_scan():
    while True:
        ret, frame = cam.read()
        #box = detect(frame)
        barcodes = pyzbar.decode(frame)
        for barcode in barcodes:
            code = barcode.data.decode("utf-8")
            left = barcode.rect.left
            top = barcode.rect.top
            if code in scanned:
                scanned[code]['lefts'].append(left)
                scanned[code]['tops'].append(top)
                scanned[code]['last'] = datetime.now()
            else:
                scanned[code] = {
                    'code': code,
                    'lefts': [left],
                    'tops': [top],
                    'last': datetime.now()
                }
            print(left)

        cv2.imshow('image', frame)
        cv2.waitKey(0)

        to_delete = []
        for code, item in scanned.items():
            if (datetime.now()-item['last']).seconds > 0.2:
                to_delete.append(code)
                print("delete")
                print(detect_direction(item['lefts']))
                direction = detect_direction(item['lefts'])
                if direction != None:
                    update = json.dumps({
                        "method": int(direction == 'left-to-right'),
                        "method_name": 0 if direction == 'left-to-right' else 1,
                        "barcode": item['code'],
                        "name": ""
                    })
                    msg = encrypt(update)
                    result = urlopen('http://sennes.n-gao.de/api?request=%s' % quote_plus(json.dumps({
                        "fridge_id": "1",
                        "method": "add_update",
                        "update": msg
                    })))
                    print(result)
        for code in to_delete:
            del(scanned[code])


width = 1920
height = 1920

if __name__ == "__main__":
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    #cam.set(cv2.CAP_PROP_EXPOSURE, 0)
    #cam.set(28, 50)
    cv2.namedWindow('image', cv2.WINDOW_NORMAL)
    continous_scan()
