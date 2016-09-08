import zmq
import datetime
import threading

from threading import Lock
from collections import defaultdict

from pypot.robot import from_json
from pypot.utils import StoppableLoopThread


class RemoteRobotController(object):
    def __init__(self, config,
                 host='*', transport='tcp',
                 req_port=6901, pub_port=6902,
                 publish_freq=50.0):

        self.robot = from_json(config)
        self.robot._primitive_manager.stop()

        context = zmq.Context()
        self.rep_socket = context.socket(zmq.REP)
        self.rep_socket.bind('{}://{}:{}'.format(transport, host, req_port))

        self.pub_socket = context.socket(zmq.PUB)
        self.pub_socket.bind('{}://{}:{}'.format(transport, host, pub_port))

        self.pub_lock = Lock()
        self.published = defaultdict(set)

        self.pub_t = StoppableLoopThread(publish_freq, update=self.publish)
        self.pub_t.start()

    def close(self):
        self.pub_t.stop()

        self.rep_socket.close()
        self.pub_socket.close()

    def run4ever(self):
        t = threading.Thread(target=self.handle_requests)
        t.daemon = True
        t.start()

        while True:
            try:
                t.join(timeout=1.)
                if not t.is_alive:
                    break

            except KeyboardInterrupt:
                break

        self.close()

    def handle_requests(self):
        while True:
            try:
                request = self.rep_socket.recv_json()

            except ValueError:
                answer = {
                    'timestamp': datetime.datetime.now().isoformat(),
                    'error': 'Could not decode request'
                }
                self.rep_socket.send_json(answer)
                continue

            except KeyboardInterrupt:
                break

            answer = {'values': defaultdict(dict)}

            if 'get' in request:
                for motor, registers in request['get'].items():
                    m = getattr(self.robot, motor)
                    d = answer['values'][motor]

                    for reg in registers:
                        d[reg] = getattr(m, reg)

            if 'set' in request:
                for motor, values in request['set'].items():
                    m = getattr(self.robot, motor)
                    d = answer['values'][motor]

                    for reg, val in values.items():
                        setattr(m, reg, val)
                        d[reg] = val

            if 'register' in request:
                with self.pub_lock:
                    for motor, registers in request['register'].items():
                        m = getattr(self.robot, motor)
                        d = answer['values'][motor]

                        for reg in registers:
                            d[reg] = getattr(m, reg)
                            self.published[motor].add(reg)

            answer['timestamp'] = datetime.datetime.now().isoformat()
            self.rep_socket.send_json(answer)

    def publish(self):
        with self.pub_lock:
            answer = {}

            for motor, registers in self.published.items():
                m = getattr(self.robot, motor)
                answer[motor] = {reg: getattr(m, reg) for reg in registers}

            self.pub_socket.send_json({
                'timestamp': datetime.datetime.now().isoformat(),
                'values': answer
            })


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Streaming from dynamixel motors to ZMQ')
    parser.add_argument('config', type=str,
                        help='Json config file of the used robot')
    parser.add_argument('--req-port', type=int, default=6901,
                        help='Zmq port for the REQ/REP')
    parser.add_argument('--pub-port', type=int, default=6902,
                        help='Zmq port for the PUB/SUB')
    args = parser.parse_args()

    robot = RemoteRobotController(config=args.config,
                                  req_port=args.req_port, pub_port=args.pub_port)
    robot.run4ever()
