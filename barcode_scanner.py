import cv2
from pyzbar import pyzbar
import numpy as np
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import time
from urllib.parse import quote_plus
from urllib.request import urlopen
import json
from Crypto.Cipher import Salsa20
import base64
from datetime import datetime


def detect(image):
    # convert the image to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # cv2.imshow('image', gray)
    # cv2.waitKey(0)

    # compute the Scharr gradient magnitude representation of the images
    # in both the x and y direction using OpenCV 2.4
    ddepth = cv2.CV_32F
    gradX = cv2.Sobel(gray, ddepth=ddepth, dx=1, dy=0, ksize=-1)
    gradY = cv2.Sobel(gray, ddepth=ddepth, dx=0, dy=1, ksize=-1)

    # subtract the y-gradient from the x-gradient
    gradient = cv2.subtract(gradX, gradY)
    gradient = cv2.convertScaleAbs(gradient)

    # cv2.imshow('image', gradient)
    # cv2.waitKey(0)

    # blur and threshold the image
    blurred = cv2.blur(gradient, (9, 9))
    (_, thresh) = cv2.threshold(blurred, 225, 255, cv2.THRESH_BINARY)

    # cv2.imshow('image', blurred)
    # cv2.waitKey(0)

    thresh = cv2.dilate(thresh, None, iterations=4)
    # cv2.imshow('image', thresh)
    # cv2.waitKey(0)

    # construct a closing kernel and apply it to the thresholded image
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # cv2.imshow('image', closed)
    # cv2.waitKey(0)

    # perform a series of erosions and dilations
    closed = cv2.erode(closed, None, iterations=8)

    # cv2.imshow('image', closed)
    # cv2.waitKey(0)

    closed = cv2.dilate(closed, None, iterations=4)

    # cv2.imshow('image', closed)
    # cv2.waitKey(0)

    # find the contours in the thresholded image
    cnts = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL,
                            cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[1]

    # if no contours were found, return None
    if len(cnts) == 0:
        return None

    # otherwise, sort the contours by area and compute the rotated
    # bounding box of the largest contour
    minBox = None
    maxScore = 0
    for cnt in cnts:
        box = np.int0(cv2.boxPoints(cv2.minAreaRect(cnt)))
        left, right, top, bottom = bounding_box(box, offset=0)
        width = right - left
        height = bottom - top
        score = width*height* (10**-(1-closed[top:bottom,left:right].mean()/255))
        # print((1-closed[top:bottom,left:right].mean()/255), score)
        if score > maxScore:
            maxScore = score
            minBox = box
    # c = sorted(cnts, key=cv2.contourArea, reverse=True)[0]
    # rect = cv2.minAreaRect(c)
    # box = cv2.boxPoints(rect)
    # box = np.int0(box)

    # return the bounding box of the barcode
    return minBox


def order_points(pts):
    # initialzie a list of coordinates that will be ordered
    # such that the first entry in the list is the top-left,
    # the second entry is the top-right, the third is the
    # bottom-right, and the fourth is the bottom-left
    rect = np.zeros((4, 2), dtype="float32")

    # the top-left point will have the smallest sum, whereas
    # the bottom-right point will have the largest sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # now, compute the difference between the points, the
    # top-right point will have the smallest difference,
    # whereas the bottom-left will have the largest difference
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    # return the ordered coordinates
    return rect


def four_point_transform(image, pts):
    # obtain a consistent order of the points and unpack them
    # individually
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # compute the width of the new image, which will be the
    # maximum distance between bottom-right and bottom-left
    # x-coordiates or the top-right and top-left x-coordinates
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # compute the height of the new image, which will be the
    # maximum distance between the top-right and bottom-right
    # y-coordinates or the top-left and bottom-left y-coordinates
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    # now that we have the dimensions of the new image, construct
    # the set of destination points to obtain a "birds eye view",
    # (i.e. top-down view) of the image, again specifying points
    # in the top-left, top-right, bottom-right, and bottom-left
    # order
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    # compute the perspective transform matrix and then apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    # return the warped image
    return warped


def bounding_box(box, offset=200):
    top = box[:, 1].min()-offset
    bottom = box[:, 1].max()+offset
    left = box[:, 0].min()-offset
    right = box[:, 0].max()+offset
    left = left if left > 0 else 0
    right = right if right < width else width-1
    top = top if top > 0 else 0
    bottom = bottom if bottom < height else height
    return left, right, top, bottom

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
        print("Scan")
        ret, frame = cam.read()
        # start = time.time()
        # box = detect(frame)
        # if box is None:
        #     continue
        # print(time.time()-start)
        # start = time.time()
        # left, right, top, bottom = bounding_box(box)
        # selection = frame[top:bottom, left:right, :]
        # selection = cv2.filter2D(selection, -1, kernel)
        # cv2.waitKey(0)
        # barcodes = pyzbar.decode(selection)
        # print(time.time()-start)
        # start = time.time()
        # print(barcodes)
        barcodes = pyzbar.decode(frame)
        # print(time.time()-start)
        # print(barcodes)
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

        # cv2.drawContours(frame, [box], -1, (0, 255, 0), 3)
        # cv2.imshow('image', frame)
        # cv2.waitKey(0)

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
                        "fridge_id": "2",
                        "method": "add_update",
                        "update": msg
                    })))
                    print(result)
        for code in to_delete:
            del(scanned[code])


width = 1920
height = 1440
kernel = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])

if __name__ == "__main__":
    cam = cv2.VideoCapture(0)
    # cam.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    # cam.set(cv2.CAP_PROP_EXPOSURE, -6)
    # cam.set(28, 50)
    # cv2.namedWindow('image', cv2.WINDOW_NORMAL)
    continous_scan()
