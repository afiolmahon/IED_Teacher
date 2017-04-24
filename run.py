#! /usr/bin/python
import time
from nrf24 import NRF24

import flask
import threading


# FLASK CONFIGURATION
app = flask.Flask(__name__)

# RADIO CONFIGURATION

NAMES = {
        32: 'Student 1',
        33: 'Student 2'
        } # Device ID Alias for teacher interface


w_pipes = { # pipes for writing to a device id
    32: [0xc2, 0xc2, 0xc2, 0xc2, 0xc2],
    #32: [0xc2, 0xc2, 0xc2, 0xc2, 0xc2],
    33: [0xe7, 0xe7, 0xe7, 0xe7, 0xe7]
}
r_pipes = { # pipes for reading from a device id
    32: [0xc2, 0xc2, 0xc2, 0xc2, 0xc2],
    #32: [0xe7, 0xe7, 0xe7, 0xe7, 0xe7],
    33: [0xe7, 0xe7, 0xe7, 0xe7, 0xe7],
    #33: [0xc2, 0xc2, 0xc2, 0xc2, 0xc2]
}

r = NRF24()
rf_lock = threading.Lock()  # Regulates access to RF Radio
CLASS_ID = 0x00
device_id = 32
polling = False

devices = [32, 33]


@app.route('/')
def index():
    return flask.render_template('index.html')


@app.route('/question_start')
def start_question():
    poll_thread = threading.Thread(target=poll_student)
    poll_thread.start()
    return flask.redirect(flask.url_for('index'))


@app.route('/clear')
def clear_question():
    global polling
    polling = False  # Stops Poll thread if it's running
    print('Clearing LEDs...')
    for dev_id in devices:
        r_write(33, dev_id)
    print('write complete...')
    return flask.redirect(flask.url_for('index'))


"""
operations
16 - check button - teacher
17 - button on - student
18 - button off - student
32 - light up LED - teacher
33 - light off LED - teacher
34 - AK, light change - student
"""


def setup_radio(details=True, write_pipe=w_pipes[32], read_pipe=r_pipes[32]):
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


def r_write(opcode, dev_id, operand=0, class_id=0):
    payload = [class_id, dev_id, opcode, operand, 0x00, 0x00, 0x00, 0x00]
    rf_lock.acquire()
    r.openWritingPipe(w_pipes[dev_id]) # Open correct com pipe
    if r.write(payload):
        print('OUT <<', payload)
        rf_lock.release()
        return True
    rf_lock.release()
    return False


def read_resp(dev_id, max_retry=20):
    buff = [0, 0, 0, 0, 0, 0, 0, 0]
    retry = 0
    rf_lock.acquire()
    r.openReadingPipe(1, r_pipes[dev_id])
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


def poll_student(duration=6):
    answers = {}

    def handle_recv(buff):
        device = buff[1]
        opcode = buff[2]
        if opcode == 17:  # Button Closed Opcode
            r_write(32, device)
            answers[device] = True
            print(NAMES[device] + ' Button Pressed')

    global polling
    polling = True
    start_t = time.time()
    print('poll_student Question')
    for dev_id in devices:
        print('Write Color', r_write(10, dev_id))  # Set Device to answer Color
    while time.time() - start_t < duration and polling:
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
