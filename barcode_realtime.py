#Importing the Packages
from imutils.video import VideoStream
from pyzbar import pyzbar
import argparse
import datetime
import imutils
import time
import cv2

pdt = argparse.ArgumentParser()
pdt.add_argument("-o", "--output", type=str, default="barcode.csv", help="Path to outputCSV file Containing barcodes")
args = vars(pdt.parse_args())

#Initializing Video Stream
print("[INFO] starting scanner... ")

vs = VideoStream(usePiCamera=True).start()
time.sleep(2.0)

#CSV output file for writing barcodes
csv = open(args["output"], "w")
found = set()

#Looping over frames from video stream
while True:
    frame = vs.read()
    frame = imutils.resize(frame, width=400)
    
    #Finding and Decoding barcodes in the frame.
    barcodes = pyzbar.decode(frame)
    
    #Looping over detected barcodes
    for barcode in barcodes:
        
        #Bounded Box Location. Scans through each line of the barcode
        (x, y, w, h) = barcode.rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 5)
        
        #Converting barcode data from bytes to String. 
        barcodeData = barcode.data.decode("utf-8")
        barcodeType = barcode.type
        
        text = "{} ({})".format(barcodeData, barcodeType)
        cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        if barcodeData not in found:
            csv.write("{},{}\n".format(datetime.datetime.now(), barcodeData))
            
            #Flush not found entry
            csv.flush
            found.add(barcodeData)
            
            cv2.imshow("Barcode Scanner", frame)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord("q"):
                break
print("[INFO] Cleaning up ... ")

#Closes the CSV file where barcodes are written
csv.close()

#closes all windows
cv2.destroyAllWindows()
vs.stop()