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

width = 1280
height = 1080
scanned = {}
cam = None

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
                    'code' : code,
                    'lefts' : [left],
                    'tops' : [top],
                    'last' : datetime.now()
                }
            print(left)
        
        to_delete = []
        for code, item in scanned.items():
            if (datetime.now()-item['last']).seconds > 0.2:
                to_delete.append(code)
                print("delete")
                print(detect_direction(item['lefts']))
                direction = detect_direction(item['lefts'])
                if direction != None:
                    update = json.dumps({
                        "method" : int(direction == 'left-to-right'),
                        "method_name" : 0 if direction == 'left-to-right' else 1,
                        "barcode" : item['code'],
                        "name" : ""
                    })
                    secret = b'*Thirty-two byte (256 bits) key*'
                    cipher = Salsa20.new(key=secret)
                    msg = cipher.nonce + cipher.encrypt(update.encode('utf-8'))
                    print(base64.b64encode(msg))
                    print(cipher.nonce)
                    urlopen('http://localhost:3000/api?request=%s' % json.dumps({
                        "fridge_id" : "1",
                        "method_name" : "add_update",
                        "update" : msg
                    }))
        for code in to_delete:
            del(scanned[code])

if __name__ == "__main__":
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_AUTOFOCUS, 1)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cam.set(cv2.CAP_PROP_EXPOSURE, -6)
    continous_scan()
