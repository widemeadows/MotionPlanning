import os
import sys
import math
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.abspath(__file__)) +
                "/../../MotionPlanning/")

import Control.draw as draw
import Control.reeds_shepp_path as rs


class C:
    Kp = 0.3  # proportional gain
    Ld = 3.0  # look ahead distance
    kf = 0.1  # look forward gain
    dt = 0.1  # T step
    dref = 0.5  # stop distance
    dc = 0.0

    # vehicle config
    RF = 3.3  # [m] distance from rear to vehicle front end of vehicle
    RB = 0.8  # [m] distance from rear to vehicle back end of vehicle
    W = 2.4  # [m] width of vehicle
    WD = 0.7 * W  # [m] distance between left-right wheels
    WB = 2.5  # [m] Wheel base
    TR = 0.44  # [m] Tyre radius
    TW = 0.7  # [m] Tyre width
    MAX_STEER = 0.25


class Node:
    def __init__(self, x, y, yaw, v, direct):
        self.x = x
        self.y = y
        self.yaw = yaw
        self.v = v
        self.direct = direct

    def update(self, a, delta, direct):
        self.x += self.v * math.cos(self.yaw) * C.dt
        self.y += self.v * math.sin(self.yaw) * C.dt
        self.yaw += self.v / C.WB * math.tan(delta) * C.dt
        self.direct = direct
        self.v += self.direct * a * C.dt


class Nodes:
    def __init__(self):
        self.x = []
        self.y = []
        self.yaw = []
        self.v = []
        self.t = []
        self.direct = []

    def add(self, t, node):
        self.x.append(node.x)
        self.y.append(node.y)
        self.yaw.append(node.yaw)
        self.v.append(node.v)
        self.t.append(t)
        self.direct.append(node.direct)


class Trajectory:
    def __init__(self, cx, cy):
        self.cx = cx
        self.cy = cy
        self.ind_end = len(self.cx) - 1
        self.index_old = None

    def target_index(self, node):
        if self.index_old is None:
            dx = [node.x - x for x in self.cx]
            dy = [node.y - y for y in self.cy]
            ind = np.argmin(np.hypot(dx, dy))
            self.index_old = ind
        else:
            ind = self.index_old

            if ind >= self.ind_end:
                self.index_old = self.ind_end
            else:
                d = self.calc_distance(node, ind)
                while True:
                    d_next = self.calc_distance(node, ind + 1)
                    if d_next > d:
                        break
                    if ind + 1 >= self.ind_end:
                        break
                    ind += 1
                    d = d_next

                self.index_old = ind

        Lf = C.kf * node.v + C.Ld

        while True:
            if self.calc_distance(node, ind) > Lf:
                break
            if ind >= self.ind_end:
                break
            ind += 1

        return ind, Lf

    def calc_distance(self, node, ind):
        return math.hypot(node.x - self.cx[ind], node.y - self.cy[ind])


def pure_pursuit(node, trajectory, pind):
    ind, Lf = trajectory.target_index(node)
    ind = max(ind, pind)

    tx = trajectory.cx[ind]
    ty = trajectory.cy[ind]

    alpha = math.atan2(ty - node.y, tx - node.x) - node.yaw
    delta = math.atan2(2.0 * C.WB * math.sin(alpha) / Lf, 1.0)

    return delta, ind


def pid_control(target_v, v, dist, direct):
    a = 0.2 * (target_v - direct * v)
    if dist > 10.0:
        a = 0.3 * (target_v - direct * v)
    else:
        if v > 2:
            a = -3.0
        elif v < -2:
            a = -1.0
    return a


def generate_path(s):
    max_c = math.tan(C.MAX_STEER) / C.WB
    path_x, path_y, yaw, direct = [], [], [], []
    x_rec, y_rec, yaw_rec, direct_rec = [], [], [], []
    direc_flag = 1.0

    for i in range(len(s) - 1):
        s_x, s_y, s_yaw = s[i][0], s[i][1], np.deg2rad(s[i][2])
        g_x, g_y, g_yaw = s[i + 1][0], s[i + 1][1], np.deg2rad(s[i + 1][2])

        path_i = rs.calc_optimal_path(s_x, s_y, s_yaw,
                                      g_x, g_y, g_yaw, max_c)

        ix = path_i.x
        iy = path_i.y
        iyaw = path_i.yaw
        idirect = path_i.directions

        for j in range(len(ix)):
            if idirect[j] == direc_flag:
                x_rec.append(ix[j])
                y_rec.append(iy[j])
                yaw_rec.append(iyaw[j])
                direct_rec.append(idirect[j])
            else:
                if len(x_rec) == 0 or direct_rec[0] != direc_flag:
                    direc_flag = idirect[j]
                    continue

                path_x.append(x_rec)
                path_y.append(y_rec)
                yaw.append(yaw_rec)
                direct.append(direct_rec)
                x_rec, y_rec, yaw_rec, direct_rec = \
                    [x_rec[-1]], [y_rec[-1]], [yaw_rec[-1]], [-direct_rec[-1]]

    path_x.append(x_rec)
    path_y.append(y_rec)
    yaw.append(yaw_rec)
    direct.append(direct_rec)

    x_all, y_all = [], []
    for ix, iy in zip(path_x, path_y):
        x_all += ix
        y_all += iy

    return path_x, path_y, yaw, direct, x_all, y_all


def main():
    # generate path
    # states = [(0, 0, 0), (20, 15, 0), (35, 20, 90), (40, 0, 180),
    #           (20, 0, 120), (5, -10, 180), (15, 5, 30)]

    states = [(-3, 3, 120), (10, -7, 30), (10, 13, 30), (20, 5, -25),
              (35, 10, 180), (30, -10, 160), (5, -12, 90)]

    x, y, yaw, direct, pathx, pathy = generate_path(states)

    # simulation
    maxTime = 100.0
    yaw_old = 0.0
    x0, y0, yaw0, direct0 = x[0][0], y[0][0], yaw[0][0], direct[0][0]
    xrec, yrec = [], []

    for cx, cy, cyaw, cdirect in zip(x, y, yaw, direct):
        t = 0.0
        node = Node(x=x0, y=y0, yaw=yaw0, v=0.0, direct=direct0)
        nodes = Nodes()
        nodes.add(t, node)
        ref_trajectory = Trajectory(cx, cy)
        target_ind, _ = ref_trajectory.target_index(node)

        while t <= maxTime:
            if cdirect[0] > 0:
                target_speed = 30.0 / 3.6
                C.Ld = 3.5
                C.dref = 1.5
                C.dc = -1.1
            else:
                target_speed = 20.0 / 3.6
                C.Ld = 2.5
                C.dref = 0.2
                C.dc = 0.2

            xt = node.x + C.dc * math.cos(node.yaw)
            yt = node.y + C.dc * math.sin(node.yaw)
            dist = math.hypot(xt - cx[-1], yt - cy[-1])

            if dist < C.dref and target_ind == len(cx) - 1:
                break

            accel = pid_control(target_speed, node.v, dist, cdirect[0])
            delta, target_ind = pure_pursuit(node, ref_trajectory, target_ind)

            t += C.dt

            node.update(accel, delta, cdirect[0])
            nodes.add(t, node)
            xrec.append(node.x)
            yrec.append(node.y)

            dy = (node.yaw - yaw_old) / (node.v * C.dt)
            steer = rs.pi_2_pi(-math.atan(C.WB * dy))

            yaw_old = node.yaw
            x0 = nodes.x[-1]
            y0 = nodes.y[-1]
            yaw0 = nodes.yaw[-1]
            direct0 = nodes.direct[-1]

            # ainimation
            plt.cla()
            plt.plot(node.x, node.y, marker='.', color='k')
            plt.plot(pathx, pathy, color='gray', linewidth=2)
            plt.plot(xrec, yrec, color='darkviolet', linewidth=2)
            plt.plot(cx[target_ind], cy[target_ind], ".r")
            draw.draw_car(node.x, node.y, yaw_old, steer, C)

            # for m in range(len(states)):
            #     draw.Arrow(states[m][0], states[m][1], np.deg2rad(states[m][2]), 2, 'dimgray')

            plt.axis("equal")
            plt.title("PurePursuit: v=" + str(node.v * 3.6)[:4] + "km/h")
            plt.gcf().canvas.mpl_connect('key_release_event',
                                         lambda event: [exit(0) if event.key == 'escape' else None])
            plt.pause(0.001)

    plt.show()


if __name__ == '__main__':
    main()