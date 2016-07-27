import time
import numpy
import argparse

from pypot.dynamixel import Dxl320IO, DxlError


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Benchmark low-level communication with dynamixel motor.')

    parser.add_argument('--duration', type=int, default=30,
                        help='benchmark duration in second')

    parser.add_argument('--live', action='store_true',
                        help='show the stats at the duration period.')

    args = parser.parse_args()


    io = Dxl320IO('/dev/serial0', timeout=0.01, use_sync_read=False)
    ids = [1, 2, 3, 4, 5]#, 6]

    while True:
        read_dt, write_dt, error = [], [], 0
        start = time.time()

        while time.time() - start < args.duration:
            try:
                t0 = time.time()
                io.get_present_position_speed_load(ids)
                t1 = time.time()
                read_dt.append(t1 - t0)
            except DxlError:
                error += 1

            pos = 30 * numpy.sin(2 * numpy.pi * 0.5 * time.time())
            try:
                t0 = time.time()
                io.set_goal_position({id: pos for id in ids})
                t1 = time.time()
                write_dt.append(t1 - t0)
            except DxlError:
                error += 1

            time.sleep(0.001)

        r = numpy.array(read_dt) * 1000
        print('Read dt: {}ms (STD={})'.format(numpy.mean(r), numpy.std(r)))

        w = numpy.array(write_dt) * 1000
        print('Write dt: {}ms (STD={})'.format(numpy.mean(w), numpy.std(w)))

        print('Error: {}'.format(error))

        if not args.live:
            break
