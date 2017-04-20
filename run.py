#! /usr/bin/python
import time
from nrf24 import NRF24

import flask
import threading


# FLASK CONFIGURATION
app = flask.Flask(__name__)

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
    r_write(33)
    return flask.redirect(flask.url_for('index'))


# RADIO CONFIGURATION

NAMES = {32: 'Student 1'} # Device ID Alias for teacher interface
w_pipes = { # pipes for writing to a device id
    32: [0xc2, 0xc2, 0xc2, 0xc2, 0xc2]
}
r_pipes = { # pipes for reading from a device id
    32: [0xe7, 0xe7, 0xe7, 0xe7, 0xe7]
}
answers = [] # Records device ids that have responded to question

r = NRF24()
rf_lock = threading.Lock()  # Regulates access to RF Radio
CLASS_ID = 0x00
device_id = 32
polling = False

"""
operations
16 - check button - teacher
17 - button on - student
18 - button off - student
32 - light up LED - teacher
33 - light off LED - teacher
34 - AK, light change - student
"""


def setup_radio(details=True, write_pipe=w_pipes[32], read_pipe=w_pipes[32]):
    r.begin(0, 0, 17, 0) #Set CE and IRQ pins
    r.setRetries(15, 15)
    r.setPayloadSize(8)
    r.setChannel(0x60)
    r.setDataRate(NRF24.BR_250KBPS)
    r.setPALevel(NRF24.PA_MAX)
    r.setAutoAck(1)
    r.enableAckPayload()
    r.openReadingPipe(1, read_pipe)
    r.openWritingPipe(write_pipe)
    r.startListening()
    r.stopListening()
    if details:
        r.printDetails()


def r_write(opcode, operand=0, dev_id=device_id, class_id=0):
    payload = [class_id, dev_id, opcode, operand, 0x00, 0x00, 0x00, 0x00]
    with rf_lock:
        for itr in range(0, 40): # Retry many times
            if r.write(payload):
                print('Wrote after {}'.format(itr))
                return True
    return False

def handle_recv(buff):
    device = buff[1]
    opcode = buff[2]
    if opcode == 17:  # Button Closed Opcode
        r_write(32)
        answers.append(device_id)
        #print(NAMES[device] + ' Button Pressed')

def read_resp(retry=1, avails=20):
    buff = [0, 0, 0, 0, 0, 0, 0, 0]
    unavail = 0
    r.startListening()
    for i in range(0, retry):  # try 20 times
        while not r.available() and unavail <= avails:
            unavail += 1
            time.sleep(1/1000.0)
        r.read(buff)
        if buff != [0,0,0,0,0,0,0,0]:  # Check if data is available
            r.stopListening()
            return buff
    r.stopListening()
    return None


def poll_student(duration=3):
    print('Starting Question')
    print('Write Color', r_write(10))  # Set Device to answer Color
    global polling
    polling = True
    start_t = time.time()
    print('Checking device')
    while time.time()-start_t < duration and polling:
        time.sleep(1/100)
        buff = read_resp()
        if buff:
            handle_recv(buff)
    r_write(33)
    polling = False
    print('Polling Stopped', polling)


#  Execution Code
if __name__ == "__main__":
    setup_radio(details=True)
    app.debug = True
    app.run(host='0.0.0.0')
