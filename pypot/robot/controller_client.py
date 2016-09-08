import zmq

from collections import defaultdict

from .controller import MotorsController


class DetachedControllerClient(MotorsController):
    def __init__(self, motors,
                 remote_host='127.0.0.1', zmq_transport='tcp',
                 req_port=6901, sub_port=6902):
        MotorsController.__init__(self, None, motors)

        c = zmq.Context()

        self.req_socket = c.socket(zmq.REQ)
        self.req_socket.connect('{}://{}:{}'.format(zmq_transport, remote_host, req_port))

        self.sub_socket = c.socket(zmq.SUB)
        self.sub_socket.setsockopt(zmq.CONFLATE, 1)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, '')
        self.sub_socket.connect('{}://{}:{}'.format(zmq_transport, remote_host, sub_port))

        self._m = {m.name: m for m in self.motors}

    def setup(self):
        default_registers = ['present_position', 'present_speed', 'present_load',
                             'angle_limit', 'present_voltage', 'present_temperature']

        registers = {}
        for m in self.motors:
            registers[m.name] = default_registers

        req = {}
        for m in self.motors:
            default_reg = ['goal_position', 'moving_speed', 'torque_limit', 'compliant']
            r = list(default_reg)

            if (m.model.startswith('AX') or m.model.startswith('RX')):
                r += ['compliance_margin', 'compliance_slope']
            elif (m.model.startswith('MX') or m.model.startswith('XL-320')):
                r += ['pid']
            if m.model.startswith('XL-320'):
                r += ['led']

            req[m.name] = r

        self.req_socket.send_json({
            'register': registers,
            'get': req
        })

        for name, values in self.req_socket.recv_json()['values'].items():
            motor = self._m[name]
            for reg, val in values.items():
                motor.__dict__[reg] = val

    def update(self):
        data = self.sub_socket.recv_json()
        if 'values' in data:
            for name, values in data['values'].items():
                motor = self._m[name]
                for reg, val in values.items():
                    motor.__dict__[reg] = val

        req = defaultdict(dict)
        for m in self.motors:
            default_reg = ['goal_position', 'moving_speed', 'torque_limit', 'compliant']
            r = list(default_reg)

            if (m.model.startswith('AX') or m.model.startswith('RX')):
                r += ['compliance_margin', 'compliance_slope']
            elif (m.model.startswith('MX') or m.model.startswith('XL-320')):
                r += ['pid']
            if m.model.startswith('XL-320'):
                r += ['led']

            for reg in r:
                req[m.name][reg] = getattr(m, reg)

        self.req_socket.send_json({
            'set': req
        })
        self.req_socket.recv_json()
