#! /usr/bin/python
import time
from nrf24 import NRF24

import flask
import threading
import os
import json

os.nice(-19)

# FLASK CONFIGURATION
app = flask.Flask(__name__)

# RADIO CONFIGURATION
NAMES = {
        32: 'Student 1',
        33: 'Student 2'
        } # Device ID Alias for teacher interface

devices = [32, 33]

pipes = {
    32: [0xc2, 0xc2, 0xc2, 0xc2, 0xc2],
    33: [0xe7, 0xe7, 0xe7, 0xe7, 0xe7]
}

answers = []

r = NRF24()
rf_lock = threading.Lock()  # Regulates access to RF Radio
CLASS_ID = 0x00
device_id = 32
polling = False

@app.route('/')
def index():
    return flask.render_template('index.html')


@app.route('/question_start')
def start_question():
    poll_thread = threading.Thread(target=poll_student)
    poll_thread.start()
    return flask.redirect(flask.url_for('index'))


@app.route('/question_stop')
def stop_question():
    print("STOPPING")
    global polling
    polling = False
    for dev_id in devices:
        r_write(33, dev_id)
    students = []
    for sid in answers:
        students.append(NAMES[sid])
    print(students)
    return json.dumps(students)


@app.route('/next_ans')
def next_ans():
    print(answers)
    if len(answers) > 0:
        next_dev = answers.pop(0)
        print(answers)
        for dev_id in devices:
            if not dev_id == next_dev:
                r_write(33, dev_id)
        r_write(35, next_dev)
    else:
        for dev_id in devices:
            r_write(33, dev_id)
    return flask.redirect(flask.url_for('index'))


"""
operations
16 - check button - teacher
17 - button on - student
18 - button off - student
32 - light up LED - teacher
33 - light off LED - teacher
34 - light up yellow - teacher
"""


def setup_radio(details=True, write_pipe=pipes[32], read_pipe=pipes[32]):
    r.begin(0, 0, 17, 0) #Set CE and IRQ pins
    r.setRetries(15, 15)
    #r.setPayloadSize(8)
    r.setChannel(0x60)
    r.setDataRate(NRF24.BR_250KBPS)
    r.enableDynamicPayloads()
    r.setPALevel(NRF24.PA_MAX)
    r.setAutoAck(1)
    r.enableAckPayload()
    r.openReadingPipe(1, read_pipe)
    r.openWritingPipe(write_pipe)
    r.startListening()
    r.stopListening()
    if details:
        r.printDetails()


def r_write(opcode, dev_id, operand=0, class_id=0, retry=5):
    payload = [class_id, dev_id, opcode, operand, 0x00, 0x00, 0x00, 0x00]
    success = False
    rf_lock.acquire()
    r.openWritingPipe(pipes[dev_id]) # Open correct com pipe

    attempt = 0 # Retry iterator
    while attempt < retry:
        attempt += 1
        success = r.write(payload)
        if success:
            print('OUT <<', payload)
            break
    rf_lock.release()
    return success


def read_resp(dev_id, max_retry=20):
    buff = [0, 0, 0, 0, 0, 0, 0, 0]
    retry = 0
    rf_lock.acquire()
    r.openReadingPipe(1, pipes[dev_id])
    r.startListening()
    while not r.available() and retry < max_retry:
        retry += 1
        time.sleep(1/1000.0)
    if r.read(buff):
        r.stopListening()
        rf_lock.release()
        print('IN >>', buff)
        return buff
    r.stopListening()
    rf_lock.release()
    return None


def poll_student():
    global answers
    global polling
    answers = []
    polling = True

    def handle_recv(buff):
        device = buff[1]
        opcode = buff[2]
        if opcode == 17:  # Button Closed Opcode
            r_write(32, device)
            if device not in answers:
                answers.append(device)
            print(NAMES[device] + ' Button Pressed')

    print('poll_student Question')
    for dev_id in devices:
        print('Write Color', r_write(10, dev_id))  # Set Device to answer Color

    while polling:
        for dev in devices:
            r_write(16, dev)
            time.sleep(1/100)
            buff = read_resp(dev)
            if buff:
                handle_recv(buff)


    for dev_id in devices:
        if dev_id not in answers:
            r_write(33, dev_id)
    polling = False
    return answers


#  Execution Code
if __name__ == "__main__":
    setup_radio(details=True)
    app.debug = True
    app.run(host='0.0.0.0')
