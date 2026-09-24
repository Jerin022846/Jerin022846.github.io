"""3D Car Parking Game - Police Patrol System.

Restored indentation and broken lines from the supplied complete source.
Requires PyOpenGL and a GLUT implementation to run.
"""

import sys
import math
import random
import time

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

PI = math.pi
LOT_W = 80.0
LOT_D = 80.0
CAR_LEN = 4.0
CAR_WID = 2.0
CAR_H = 1.4

MAX_SPEED = 14.0
ACCEL = 6.0
BRAKE_F = 10.0
FRICTION = 3.0
STEER_SPD = 70.0

POLICE_BASE_SPEED = 7.0
POLICE_CATCH_DIST = 3.0
STOP_CATCH_TIME = 1.2
DETECT_RADIUS = 22.0

MAX_POLICE = 3
GAME_TIME = 60.0
MAX_CRASHES = 3
MAX_LEVELS = 10

WIN_W, WIN_H = 1000, 700

player = dict(px=0.0, pz=0.0, angle=180.0, speed=0.0,
              stop_timer=0.0)
police_cars = []
parked_cars = []
extra_parked = []
trees = []
obstacles = []
park_zone = dict(cx=0.0, cz=0.0, hw=3.0, hd=3.0, angle=0.0)

state = dict(
    level=1, time_left=GAME_TIME, crashes=0,
    cheat=False, game_over=False, game_won=False,
    police_alert=False, alert_timer=0.0, scene_time=0.0,
    crash_cd=0.0, level_flash=0.0, win_cooldown=0.0,
)
camera = dict(first_person=False, yaw=0.0, pitch=30.0, dist=18.0)
keys = dict(W=False, S=False, A=False, D=False, X=False)
last_time = [0.0]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def len2(x, z):
    return math.sqrt(x * x + z * z)


def randf(a, b):
    return a + (b - a) * random.random()


def set_color(r, g, b):
    glColor3f(r, g, b)


def draw_box(hw, hh, hd):
    glPushMatrix()
    glScalef(hw * 2, hh * 2, hd * 2)
    glutSolidCube(1.0)
    glPopMatrix()


def draw_cylinder(r, h, slices=12):
    q = gluNewQuadric()
    glPushMatrix()
    glRotatef(-90, 1, 0, 0)
    gluCylinder(q, r, r, h, slices, 1)
    glBegin(GL_TRIANGLES)
    for i in range(slices):
        a0 = 2 * PI * i / slices
        a1 = 2 * PI * (i + 1) / slices
        glVertex3f(0, 0, 0)
        glVertex3f(r * math.cos(a0), r * math.sin(a0), 0)
        glVertex3f(r * math.cos(a1), r * math.sin(a1), 0)
    glEnd()
    glTranslatef(0, 0, h)
    glBegin(GL_TRIANGLES)
    for i in range(slices):
        a0 = 2 * PI * i / slices
        a1 = 2 * PI * (i + 1) / slices
        glVertex3f(0, 0, 0)
        glVertex3f(r * math.cos(a0), r * math.sin(a0), 0)
        glVertex3f(r * math.cos(a1), r * math.sin(a1), 0)
    glEnd()
    glPopMatrix()
    gluDeleteQuadric(q)


def draw_cone(base_r, top_r, h, slices=10):
    q = gluNewQuadric()
    glPushMatrix()
    glRotatef(-90, 1, 0, 0)
    gluCylinder(q, base_r, top_r, h, slices, 4)
    glBegin(GL_TRIANGLES)
    for i in range(slices):
        a0 = 2 * PI * i / slices
        a1 = 2 * PI * (i + 1) / slices
        glVertex3f(0, 0, 0)
        glVertex3f(base_r * math.cos(a0), base_r * math.sin(a0), 0)
        glVertex3f(base_r * math.cos(a1), base_r * math.sin(a1), 0)
    glEnd()
    glPopMatrix()
    gluDeleteQuadric(q)


def draw_disk(r, slices=8):
    glBegin(GL_TRIANGLES)
    for i in range(slices):
        a0 = 2 * PI * i / slices
        a1 = 2 * PI * (i + 1) / slices
        glVertex3f(0, 0, 0)
        glVertex3f(r * math.cos(a0), r * math.sin(a0), 0)
        glVertex3f(r * math.cos(a1), r * math.sin(a1), 0)
    glEnd()


def obb_collide(ax, az, aAng, aw, al, bx, bz, bAng, bw, bl):
    dx, dz = bx - ax, bz - az
    if len2(dx, dz) > len2(aw, al) + len2(bw, bl):
        return False
    aR = math.radians(aAng)
    bR = math.radians(bAng)
    aX = (math.sin(aR), math.cos(aR))
    aZ = (-math.cos(aR), math.sin(aR))
    bX = (math.sin(bR), math.cos(bR))
    bZ = (-math.cos(bR), math.sin(bR))
    for ax2 in [aX, aZ, bX, bZ]:
        t = dx * ax2[0] + dz * ax2[1]
        pA = (abs(aw * (ax2[0] * aX[0] + ax2[1] * aX[1]))
              + abs(al * (ax2[0] * aZ[0] + ax2[1] * aZ[1])))
        pB = (abs(bw * (ax2[0] * bX[0] + ax2[1] * bX[1]))
              + abs(bl * (ax2[0] * bZ[0] + ax2[1] * bZ[1])))
        if abs(t) > pA + pB:
            return False
    return True


def check_parked():
    return (abs(player['px'] - park_zone['cx']) < park_zone['hw']
            and abs(player['pz'] - park_zone['cz']) < park_zone['hd'])


def pick_random_zone():
    sx, sz, margin = 0.0, LOT_D - 15.0, 14.0
    pillars = [(p, q)
               for p in [-LOT_W + 8, 0, LOT_W - 8]
               for q in [-LOT_D + 8, 0, LOT_D - 8]]
    for _ in range(300):
        cx = randf(-LOT_W + margin, LOT_W - margin)
        cz = randf(-LOT_D + margin, LOT_D - margin)
        if len2(cx - sx, cz - sz) < 22.0:
            continue
        if any(len2(cx - p, cz - q) < 7.0 for p, q in pillars):
            continue
        return cx, cz
    return -30.0, -30.0


def init_level():
    random.seed(state['level'] * 7919 + int(last_time[0] * 1000) % 7919)
    lv = state['level']
    player.update(px=0.0, pz=LOT_D - 15.0, angle=180.0,
                  speed=0.0, stop_timer=0.0)
    pf = state.get('level_flash', 0.0)
    pc = state.get('win_cooldown', 0.0)
    state.update(time_left=GAME_TIME + (lv - 1) * 10.0, crashes=0,
                 cheat=False, game_over=False, game_won=False,
                 police_alert=False, alert_timer=0.0, crash_cd=0.0,
                 level_flash=pf, win_cooldown=pc)

    cx, cz = pick_random_zone()
    park_zone.update(cx=cx, cz=cz, hw=CAR_WID * 1.4,
                     hd=CAR_LEN * 1.1, angle=0.0)
    parked_cars.clear()
    colors = [(0.8, 0.1, 0.1), (0.1, 0.2, 0.8), (0.1, 0.7, 0.2),
              (0.8, 0.5, 0.0), (0.6, 0.0, 0.6), (0.7, 0.7, 0.0)]
    for row in range(2):
        rz = -LOT_D + 13.0 if row == 0 else LOT_D - 13.0
        for s in range(8):
            sx2 = (-LOT_W + 6.0) + s * 3.7
            if len2(sx2 - park_zone['cx'], rz - park_zone['cz']) < 8.0:
                continue
            ci = (s + row * 8) % len(colors)
            parked_cars.append(dict(px=sx2, pz=rz,
                                    angle=0.0 if row == 0 else 180.0,
                                    r=colors[ci][0], g=colors[ci][1],
                                    b=colors[ci][2]))

    extra_parked.clear()
    for ex, ez, ea, er, eg, eb in [
        (-45.0, 5.0, 90.0, 0.9, 0.3, 0.1),
        (45.0, -5.0, 90.0, 0.1, 0.5, 0.9),
        (-50.0, 40.0, 0.0, 0.3, 0.8, 0.3),
        (50.0, -40.0, 0.0, 0.8, 0.8, 0.1),
        (-30.0, 0.0, 45.0, 0.7, 0.1, 0.7),
        (30.0, 0.0, 135.0, 0.2, 0.8, 0.8)
    ]:
        if len2(ex - park_zone['cx'], ez - park_zone['cz']) > 8.0:
            extra_parked.append(dict(px=ex, pz=ez, angle=ea,
                                     r=er, g=eg, b=eb))

    trees.clear()
    for tx, tz in [(-LOT_W + 5, -LOT_D + 5),
                   (LOT_W - 5, -LOT_D + 5),
                   (-LOT_W + 5, LOT_D - 5),
                   (LOT_W - 5, LOT_D - 5)]:
        trees.append((tx, tz))
    for i in range(-2, 3):
        trees.append((i * 20.0, -LOT_D + 3.0))
        trees.append((i * 20.0, LOT_D - 3.0))
    for tx, tz in [(-55.0, 0.0), (55.0, 0.0), (-55.0, 30.0),
                   (55.0, -30.0), (-55.0, -30.0), (55.0, 30.0)]:
        if len2(tx - park_zone['cx'], tz - park_zone['cz']) > 8.0:
            trees.append((tx, tz))

    obstacles.clear()
    pool_a = [
        (-20.0, 10.0), (20.0, -10.0), (10.0, 40.0), (-10.0, -40.0),
        (50.0, 20.0), (-50.0, -20.0), (35.0, -55.0), (-35.0, 55.0),
        (0.0, 30.0), (0.0, -30.0), (30.0, 0.0), (-30.0, 0.0),
        (45.0, -40.0), (-45.0, 40.0), (20.0, 55.0), (-20.0, -55.0),
    ]
    pool_b = [
        (0.0, 20.0), (-15.0, -20.0), (25.0, 35.0), (-25.0, -35.0),
        (40.0, 0.0), (-40.0, 0.0), (15.0, -50.0), (-15.0, 50.0),
        (10.0, -20.0), (-10.0, 20.0), (35.0, 20.0), (-35.0, -20.0),
        (55.0, -10.0), (-55.0, 10.0), (5.0, 50.0), (-5.0, -50.0),
    ]
    a_count = min(lv * 3, len(pool_a))
    b_count = max(0, min((lv - 5) * 3, len(pool_b)))
    for ox, oz in pool_a[:a_count] + pool_b[:b_count]:
        if (len2(ox - park_zone['cx'], oz - park_zone['cz']) > 7.0
                and len2(ox, oz - (LOT_D - 15.0)) > 6.0):
            obstacles.append((ox, oz))

    police_cars.clear()
    for i, ang in enumerate([0.0, 120.0, 240.0]):
        a = math.radians(ang)
        police_cars.append(dict(
            px=math.cos(a) * 30.0, pz=math.sin(a) * 30.0,
            angle=ang + 90.0, speed=POLICE_BASE_SPEED,
            chasing=False,
            target=[randf(-LOT_W + 10, LOT_W - 10),
                    randf(-LOT_D + 10, LOT_D - 10)],
            light_t=i * 0.5, catch_timer=0.0
        ))


def update(dt):
    if state['game_over'] or state['game_won']:
        return
    state['scene_time'] += dt
    state['time_left'] -= dt
    state['crash_cd'] -= dt
    state['level_flash'] = max(0.0, state['level_flash'] - dt)
    state['win_cooldown'] = max(0.0, state.get('win_cooldown', 0.0) - dt)

    if keys['W']:
        player['speed'] = min(player['speed'] + ACCEL * dt, MAX_SPEED)
    if keys['S']:
        player['speed'] = max(player['speed'] - ACCEL * dt, -MAX_SPEED * 0.6)
    if keys['X']:
        s = player['speed']
        if s > 0:
            player['speed'] = max(0.0, s - BRAKE_F * dt)
        elif s < 0:
            player['speed'] = min(0.0, s + BRAKE_F * dt)
    if not (keys['W'] or keys['S'] or keys['X']):
        s = player['speed']
        if abs(s) < 0.05:
            player['speed'] = 0.0
        else:
            player['speed'] -= (1.0 if s > 0 else -1.0) * FRICTION * dt

    player['stop_timer'] = (player.get('stop_timer', 0.0) + dt
                            if abs(player['speed']) < 0.05 else 0.0)
    sf = clamp(abs(player['speed']) / MAX_SPEED, 0.2, 1.0)
    rv = 1 if player['speed'] >= 0 else -1
    if keys['A']:
        player['angle'] += STEER_SPD * sf * dt * rv
    if keys['D']:
        player['angle'] -= STEER_SPD * sf * dt * rv

    rad = math.radians(player['angle'])
    nx = player['px'] + math.sin(rad) * player['speed'] * dt
    nz = player['pz'] + math.cos(rad) * player['speed'] * dt
    m = CAR_LEN
    if nx < -LOT_W + m:
        nx = -LOT_W + m
        player['speed'] *= -0.4
    if nx > LOT_W - m:
        nx = LOT_W - m
        player['speed'] *= -0.4
    if nz < -LOT_D + m:
        nz = -LOT_D + m
        player['speed'] *= -0.4
    if nz > LOT_D - m:
        nz = LOT_D - m
        player['speed'] *= -0.4

    hit = False
    for pc in parked_cars + extra_parked:
        if obb_collide(nx, nz, player['angle'], CAR_WID * 0.55,
                       CAR_LEN * 0.55, pc['px'], pc['pz'], pc['angle'],
                       CAR_WID * 0.55, CAR_LEN * 0.55):
            hit = True
            player['speed'] *= -0.5
            nx = player['px']
            nz = player['pz']
            break
    if not hit:
        for px2, pz2 in [(p, q)
                         for p in [-LOT_W + 8, 0, LOT_W - 8]
                         for q in [-LOT_D + 8, 0, LOT_D - 8]]:
            if len2(nx - px2, nz - pz2) < 2.0:
                hit = True
                player['speed'] *= -0.5
                nx = player['px']
                nz = player['pz']
                break
    if not hit:
        for ox, oz in obstacles:
            if len2(nx - ox, nz - oz) < 2.2:
                hit = True
                player['speed'] *= -0.5
                nx = player['px']
                nz = player['pz']
                break
    if not hit:
        for tx2, tz2 in trees:
            if len2(nx - tx2, nz - tz2) < 1.2:
                hit = True
                player['speed'] *= -0.5
                nx = player['px']
                nz = player['pz']
                break
    if hit and state['crash_cd'] <= 0:
        state['crashes'] += 1
        state['crash_cd'] = 0.8
    player['px'] = nx
    player['pz'] = nz

    if state['win_cooldown'] <= 0 and check_parked():
        state['level'] += 1
        if state['level'] > MAX_LEVELS:
            state['game_won'] = True
        else:
            state['level_flash'] = 2.5
            state['win_cooldown'] = 2.5
            init_level()
        return
    if state['crashes'] >= MAX_CRASHES:
        state['game_over'] = True
        return
    if state['time_left'] <= 0:
        state['game_over'] = True
        return

    any_chasing = False
    for cop in police_cars:
        cop['light_t'] += dt
        dx = player['px'] - cop['px']
        dz = player['pz'] - cop['pz']
        dist = len2(dx, dz)
        if state['cheat']:
            cop['chasing'] = False
            cop['catch_timer'] = 0.0
        else:
            if dist < DETECT_RADIUS:
                cop['chasing'] = True
            elif dist > DETECT_RADIUS * 1.8:
                cop['chasing'] = False

        if cop['chasing']:
            any_chasing = True
            tx, tz = player['px'], player['pz']
        else:
            tx, tz = cop['target']
            if len2(tx - cop['px'], tz - cop['pz']) < 4.0:
                cop['target'] = [randf(-LOT_W + 12, LOT_W - 12),
                                 randf(-LOT_D + 12, LOT_D - 12)]

        desired = (math.degrees(math.atan2(tx - cop['px'], tz - cop['pz']))
                   - cop['angle'] + 180) % 360 - 180
        turn_rate = 180.0 if cop['chasing'] else 90.0
        cop['angle'] += clamp(desired, -turn_rate * dt, turn_rate * dt)
        pspd = POLICE_BASE_SPEED * (1.0 if cop['chasing'] else 0.6)
        r2 = math.radians(cop['angle'])
        cop['px'] = clamp(cop['px'] + math.sin(r2) * pspd * dt,
                          -LOT_W + 3, LOT_W - 3)
        cop['pz'] = clamp(cop['pz'] + math.cos(r2) * pspd * dt,
                          -LOT_D + 3, LOT_D - 3)
        if cop['chasing'] and dist < POLICE_CATCH_DIST and not state['cheat']:
            if player['stop_timer'] >= STOP_CATCH_TIME:
                state['game_over'] = True
                return
        else:
            cop['catch_timer'] = 0.0

    state['police_alert'] = any_chasing
    state['alert_timer'] = state['alert_timer'] + dt if any_chasing else 0.0


def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_shapes():
    glPushMatrix()
    # Floor
    set_color(0.28, 0.28, 0.30)
    glPushMatrix()
    glTranslatef(0, -0.02, 0)
    glScalef(LOT_W * 2, 0.04, LOT_D * 2)
    glutSolidCube(1.0)
    glPopMatrix()

    # Parking lines
    set_color(0.85, 0.85, 0.85)
    sw, sd, sx0 = 3.2, 6.0, -LOT_W + 6.0
    for row in range(2):
        rz = -LOT_D + 10.0 if row == 0 else LOT_D - 16.0
        for s in range(10):
            glPushMatrix()
            glTranslatef(sx0 + s * (sw + 0.5), 0.01, rz + sd * 0.5)
            glScalef(0.15, 0.02, sd)
            glutSolidCube(1.0)
            glPopMatrix()
        lx = sx0 + 5 * (sw + 0.5) * 0.5 - sw * 0.5
        for zz in [rz, rz + sd]:
            glPushMatrix()
            glTranslatef(lx, 0.01, zz)
            glScalef(10 * (sw + 0.5), 0.02, 0.15)
            glutSolidCube(1.0)
            glPopMatrix()
    set_color(0.9, 0.75, 0.0)
    glPushMatrix()
    glTranslatef(0, 0.01, 0)
    glScalef(0.3, 0.02, LOT_D * 1.8)
    glutSolidCube(1.0)
    glPopMatrix()

    # Walls
    set_color(0.55, 0.50, 0.45)
    for wx, wy, wz, hw, hh, hd in [
        (0, 2.5, -LOT_D + 1.0, LOT_W, 2.5, 1.0),
        (0, 2.5, LOT_D - 1.0, LOT_W, 2.5, 1.0),
        (LOT_W - 1.0, 2.5, 0, 1.0, 2.5, LOT_D),
        (-LOT_W + 1.0, 2.5, 0, 1.0, 2.5, LOT_D),
    ]:
        glPushMatrix()
        glTranslatef(wx, wy, wz)
        draw_box(hw, hh, hd)
        glPopMatrix()

    # Pillars
    set_color(0.60, 0.58, 0.55)
    for px3 in [-LOT_W + 8, 0, LOT_W - 8]:
        for pz3 in [-LOT_D + 8, 0, LOT_D - 8]:
            glPushMatrix()
            glTranslatef(px3, 3.0, pz3)
            draw_box(0.6, 3.0, 0.6)
            glPopMatrix()

    # Ceiling beams
    set_color(0.4, 0.4, 0.4)
    for i in range(-3, 4):
        glPushMatrix()
        glTranslatef(i * 12.0, 5.8, 0)
        draw_box(0.15, 0.15, LOT_D - 1.0)
        glPopMatrix()
    for j in range(-3, 4):
        glPushMatrix()
        glTranslatef(0, 5.8, j * 12.0)
        draw_box(LOT_W - 1.0, 0.15, 0.15)
        glPopMatrix()

    # Trees
    for tx, tz in trees:
        glPushMatrix()
        glTranslatef(tx, 0, tz)
        set_color(0.4, 0.25, 0.1)
        draw_cylinder(0.25, 2.2, 8)
        set_color(0.15, 0.55, 0.15)
        for i in range(3):
            glPushMatrix()
            glTranslatef(0, 1.5 + i, 0)
            draw_cone(1.4 - i * 0.35, 0.0, 1.6, 10)
            glPopMatrix()
        glPopMatrix()

    # Obstacles
    for ox, oz in obstacles:
        glPushMatrix()
        glTranslatef(ox, 0, oz)
        set_color(0.50, 0.48, 0.45)
        glPushMatrix()
        glTranslatef(0, 1.0, 0)
        draw_box(1.5, 1.0, 1.5)
        glPopMatrix()
        set_color(0.9, 0.45, 0.05)
        glPushMatrix()
        glTranslatef(0, 1.75, 0)
        draw_box(1.55, 0.12, 1.55)
        glPopMatrix()
        glPopMatrix()

    # Parked cars
    for pc in parked_cars + extra_parked:
        glPushMatrix()
        glTranslatef(pc['px'], 0, pc['pz'])
        glRotatef(pc['angle'], 0, 1, 0)
        set_color(pc['r'], pc['g'], pc['b'])
        glPushMatrix()
        glTranslatef(0, CAR_H * 0.35, 0)
        draw_box(CAR_WID * 0.5, CAR_H * 0.35, CAR_LEN * 0.5)
        glPopMatrix()
        set_color(pc['r'] * 0.7, pc['g'] * 0.7, pc['b'] * 0.7)
        glPushMatrix()
        glTranslatef(0, CAR_H * 0.78, -CAR_LEN * 0.05)
        draw_box(CAR_WID * 0.42, CAR_H * 0.28, CAR_LEN * 0.30)
        glPopMatrix()
        set_color(0.2, 0.25, 0.4)
        for gz in [CAR_LEN * 0.28, -CAR_LEN * 0.38]:
            glPushMatrix()
            glTranslatef(0, CAR_H * 0.78, gz)
            draw_box(CAR_WID * 0.38, CAR_H * 0.22, 0.04)
            glPopMatrix()
        set_color(0.15, 0.15, 0.15)
        for i, wx in enumerate([-CAR_WID * 0.52, CAR_WID * 0.52]):
            for wz in [CAR_LEN * 0.32, -CAR_LEN * 0.33]:
                glPushMatrix()
                glTranslatef(wx, 0.38, wz)
                glRotatef(90, 0, 0, 1)
                draw_cylinder(0.38, 0.22, 12)
                glPopMatrix()
                set_color(0.7, 0.7, 0.7)
                hx = wx - (0.12 if i == 0 else -0.12)
                glPushMatrix()
                glTranslatef(hx, 0.38, wz)
                draw_disk(0.25, 8)
                glPopMatrix()
        set_color(1.0, 1.0, 0.6)
        for s in [-1, 1]:
            glPushMatrix()
            glTranslatef(s * CAR_WID * 0.35, CAR_H * 0.38, CAR_LEN * 0.51)
            draw_box(0.18, 0.12, 0.05)
            glPopMatrix()
        set_color(0.9, 0.1, 0.1)
        for s in [-1, 1]:
            glPushMatrix()
            glTranslatef(s * CAR_WID * 0.35, CAR_H * 0.38, -CAR_LEN * 0.51)
            draw_box(0.18, 0.10, 0.05)
            glPopMatrix()
        glPopMatrix()

    # Police cars
    for cop in police_cars:
        glPushMatrix()
        glTranslatef(cop['px'], 0, cop['pz'])
        glRotatef(cop['angle'], 0, 1, 0)
        set_color(0.05, 0.05, 0.05)
        glPushMatrix()
        glTranslatef(0, CAR_H * 0.35, 0)
        draw_box(CAR_WID * 0.5, CAR_H * 0.35, CAR_LEN * 0.5)
        glPopMatrix()
        set_color(1.0, 1.0, 1.0)
        for s in [-1, 1]:
            glPushMatrix()
            glTranslatef(s * CAR_WID * 0.51, CAR_H * 0.35, 0)
            draw_box(0.04, CAR_H * 0.18, CAR_LEN * 0.35)
            glPopMatrix()
        set_color(1.0, 1.0, 1.0)
        glPushMatrix()
        glTranslatef(0, CAR_H * 0.78, -CAR_LEN * 0.05)
        draw_box(CAR_WID * 0.42, CAR_H * 0.28, CAR_LEN * 0.32)
        glPopMatrix()
        set_color(0.2, 0.25, 0.4)
        glPushMatrix()
        glTranslatef(0, CAR_H * 0.78, CAR_LEN * 0.28)
        draw_box(CAR_WID * 0.38, CAR_H * 0.22, 0.04)
        glPopMatrix()
        glPushMatrix()
        glTranslatef(0, CAR_H * 0.78, -CAR_LEN * 0.38)
        draw_box(CAR_WID * 0.38, CAR_H * 0.22, 0.04)
        glPopMatrix()
        set_color(0.1, 0.1, 0.1)
        glPushMatrix()
        glTranslatef(0, CAR_H * 1.08, -CAR_LEN * 0.05)
        draw_box(CAR_WID * 0.25, 0.08, CAR_LEN * 0.12)
        glPopMatrix()
        phase = math.sin(cop['light_t'] * 8.0)
        rI = 1.0 if phase > 0 else 0.3
        bI = 1.0 if phase < 0 else 0.3
        set_color(rI, 0.05, 0.05)
        glPushMatrix()
        glTranslatef(-CAR_WID * 0.12, CAR_H * 1.17, -CAR_LEN * 0.05)
        draw_box(0.15, 0.12, 0.22)
        glPopMatrix()
        set_color(0.05, 0.2, bI)
        glPushMatrix()
        glTranslatef(CAR_WID * 0.12, CAR_H * 1.17, -CAR_LEN * 0.05)
        draw_box(0.15, 0.12, 0.22)
        glPopMatrix()
        set_color(0.15, 0.15, 0.15)
        for i, (wx, wz) in enumerate([
            (wx, wz) for wx in [-CAR_WID * 0.52, CAR_WID * 0.52]
            for wz in [CAR_LEN * 0.32, -CAR_LEN * 0.33]
        ]):
            glPushMatrix()
            glTranslatef(wx, 0.38, wz)
            glRotatef(90, 0, 0, 1)
            draw_cylinder(0.38, 0.22, 14)
            glPopMatrix()
            set_color(0.55, 0.55, 0.55)
            hx = wx - (0.12 if wx < 0 else -0.12)
            glPushMatrix()
            glTranslatef(hx, 0.38, wz)
            draw_disk(0.22, 8)
            glPopMatrix()
        glPopMatrix()

    # Player's car
    if not camera['first_person']:
        glPushMatrix()
        glTranslatef(player['px'], 0, player['pz'])
        glRotatef(player['angle'], 0, 1, 0)
        if state['cheat']:
            br, bg, bb = 0.28, 0.28, 0.30
        else:
            br, bg, bb = 1.0, 0.85, 0.0
        set_color(br, bg, bb)
        glPushMatrix()
        glTranslatef(0, CAR_H * 0.35, 0)
        draw_box(CAR_WID * 0.5, CAR_H * 0.35, CAR_LEN * 0.5)
        glPopMatrix()
        set_color(br * 0.7, bg * 0.7, bb * 0.7)
        glPushMatrix()
        glTranslatef(0, CAR_H * 0.78, -CAR_LEN * 0.05)
        draw_box(CAR_WID * 0.42, CAR_H * 0.28, CAR_LEN * 0.32)
        glPopMatrix()
        set_color(0.2, 0.25, 0.4)
        for gz in [CAR_LEN * 0.28, -CAR_LEN * 0.38]:
            glPushMatrix()
            glTranslatef(0, CAR_H * 0.78, gz)
            draw_box(CAR_WID * 0.38, CAR_H * 0.22, 0.04)
            glPopMatrix()
        wc = 0.28 if state['cheat'] else 0.15
        set_color(wc, wc, wc)
        for i, wx in enumerate([-CAR_WID * 0.52, CAR_WID * 0.52]):
            for wz in [CAR_LEN * 0.32, -CAR_LEN * 0.33]:
                glPushMatrix()
                glTranslatef(wx, 0.38, wz)
                glRotatef(90, 0, 0, 1)
                draw_cylinder(0.38, 0.22, 14)
                glPopMatrix()
                hc = 0.28 if state['cheat'] else 0.7
                set_color(hc, hc, hc)
                hx2 = wx - (0.12 if i == 0 else -0.12)
                glPushMatrix()
                glTranslatef(hx2, 0.38, wz)
                draw_disk(0.25, 8)
                glPopMatrix()
        if not state['cheat']:
            set_color(1.0, 1.0, 0.6)
            for s in [-1, 1]:
                glPushMatrix()
                glTranslatef(s * CAR_WID * 0.35, CAR_H * 0.38, CAR_LEN * 0.51)
                draw_box(0.18, 0.12, 0.05)
                glPopMatrix()
        set_color(0.9, 0.1, 0.1)
        for s in [-1, 1]:
            glPushMatrix()
            glTranslatef(s * CAR_WID * 0.35, CAR_H * 0.38, -CAR_LEN * 0.51)
            draw_box(0.18, 0.10, 0.05)
            glPopMatrix()
        glPopMatrix()

    # Parking zone
    t = state['scene_time']
    pz = park_zone
    pulse = 0.55 + 0.25 * math.sin(t * 3.0)
    glPushMatrix()
    glTranslatef(pz['cx'], 0.05, pz['cz'])
    glRotatef(pz['angle'], 0, 1, 0)
    hw, hd = pz['hw'], pz['hd']
    set_color(0.0, pulse, 0.1)
    glBegin(GL_QUADS)
    glVertex3f(-hw, 0, -hd)
    glVertex3f(hw, 0, -hd)
    glVertex3f(hw, 0, hd)
    glVertex3f(-hw, 0, hd)
    glEnd()
    set_color(0.0, 1.0, 0.0)
    glLineWidth(3.0)
    glBegin(GL_LINE_LOOP)
    glVertex3f(-hw, 0, -hd)
    glVertex3f(hw, 0, -hd)
    glVertex3f(hw, 0, hd)
    glVertex3f(-hw, 0, hd)
    glEnd()
    glLineWidth(1.0)
    set_color(1.0, 1.0, 0.0)
    glBegin(GL_TRIANGLES)
    glVertex3f(0, 0, -1.5)
    glVertex3f(-0.7, 0, 0.5)
    glVertex3f(0.7, 0, 0.5)
    glEnd()
    glPopMatrix()
    glPopMatrix()


def keyboardListener(key, x, y):
    k = key.decode('utf-8', errors='ignore').upper()
    if k == 'W':
        keys['W'] = True
    elif k == 'S':
        keys['S'] = True
    elif k == 'A':
        keys['A'] = True
    elif k == 'D':
        keys['D'] = True
    elif k == 'X':
        keys['X'] = True
    elif k == 'C':
        state['cheat'] = not state['cheat']
    elif k == 'R':
        state['level'] = 1
        state['level_flash'] = 0.0
        state['win_cooldown'] = 0.0
        init_level()
    elif key == b'\x1b':
        sys.exit(0)


def specialKeyListener(key, x, y):
    pass


def mouseListener(button, state_val, x, y):
    if button == GLUT_RIGHT_BUTTON and state_val == GLUT_DOWN:
        camera['first_person'] = not camera['first_person']


def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(55.0, WIN_W / WIN_H, 0.3, 400.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    carRad = math.radians(player['angle'])
    if camera['first_person']:
        eyeH = CAR_H + 0.35
        fwd = CAR_LEN * 0.38
        ex = player['px'] + math.sin(carRad) * fwd
        ez = player['pz'] + math.cos(carRad) * fwd
        lx = player['px'] + math.sin(carRad) * (fwd + 20.0)
        lz = player['pz'] + math.cos(carRad) * (fwd + 20.0)
        gluLookAt(ex, eyeH, ez, lx, 0.3, lz, 0, 1, 0)
    else:
        orbitRad = math.radians(player['angle'] + camera['yaw'])
        pitchRad = math.radians(camera['pitch'])
        d = camera['dist']
        ex = player['px'] - math.sin(orbitRad) * d * math.cos(pitchRad)
        ez = player['pz'] - math.cos(orbitRad) * d * math.cos(pitchRad)
        ey = d * math.sin(pitchRad) + 1.0
        gluLookAt(ex, ey, ez, player['px'], 1.2, player['pz'], 0, 1, 0)


def idle():
    now = glutGet(GLUT_ELAPSED_TIME) / 1000.0
    dt = now - last_time[0]
    last_time[0] = now
    if dt > 0.05:
        dt = 0.05
    update(dt)
    glutPostRedisplay()


def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WIN_W, WIN_H)
    setupCamera()
    draw_shapes()
    glDisable(GL_DEPTH_TEST)
    lv = state['level']
    tl = state['time_left']
    cr = state['crashes']
    spd = abs(player['speed'])
    t = state['scene_time']

    # HUD panel
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    set_color(0.05, 0.05, 0.05)
    glBegin(GL_QUADS)
    glVertex2f(0, WIN_H - 78)
    glVertex2f(380, WIN_H - 78)
    glVertex2f(380, WIN_H)
    glVertex2f(0, WIN_H)
    glEnd()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glColor3f(1.0, 1.0, 0.2)
    draw_text(12, WIN_H - 26, f"LEVEL: {lv} / {MAX_LEVELS}")
    tc = 1.0 if tl > 20 else (1.0 if math.sin(t * 6) > 0 else 0.3)
    glColor3f(tc, tc * 0.5, 0.0)
    draw_text(12, WIN_H - 48, f"TIME: {tl:.1f}s")
    glColor3f(1.0 if cr >= MAX_CRASHES - 1 else 0.7, 0.3, 0.3)
    draw_text(200, WIN_H - 26, f"CRASHES: {cr}/{MAX_CRASHES}")
    glColor3f(0.4, 0.9, 1.0)
    draw_text(200, WIN_H - 48, f"SPD: {spd:.1f}")
    glColor3f(0.7, 0.7, 0.4)
    draw_text(12, WIN_H - 70,
              "CAM: 1ST-PERSON" if camera['first_person'] else "CAM: 3RD-PERSON")
    if state['cheat']:
        glColor3f(0.0, 1.0, 0.5)
        draw_text(200, WIN_H - 70, "CHEAT ON")

    # Police alert
    if state['police_alert']:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, WIN_W, 0, WIN_H)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        flash_on = math.sin(t * 10) > 0
        cx2 = WIN_W // 2
        set_color(0.6 if flash_on else 0.15, 0.0, 0.0)
        glBegin(GL_QUADS)
        glVertex2f(cx2 - 135, WIN_H - 42)
        glVertex2f(cx2 + 135, WIN_H - 42)
        glVertex2f(cx2 + 135, WIN_H - 8)
        glVertex2f(cx2 - 135, WIN_H - 8)
        glEnd()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glColor3f(1.0, 1.0, 0.0)
        draw_text(cx2 - 115, WIN_H - 36, "! POLICE ALERT !",
                  font=GLUT_BITMAP_TIMES_ROMAN_24)

    # Bottom bar
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    set_color(0.05, 0.05, 0.05)
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(WIN_W, 0)
    glVertex2f(WIN_W, 22)
    glVertex2f(0, 22)
    glEnd()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glColor3f(0.75, 0.75, 0.75)
    draw_text(8, 5, "W/S:Drive A/D:Steer X:Brake C:Cheat "
                     "RMB:Cam R:Reset ESC:Quit")

    # Level complete banner
    if state['level_flash'] > 0 and not state['game_over'] and not state['game_won']:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, WIN_W, 0, WIN_H)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        set_color(0.0, 0.12, 0.0)
        glBegin(GL_QUADS)
        glVertex2f(WIN_W // 2 - 240, WIN_H // 2 - 60)
        glVertex2f(WIN_W // 2 + 240, WIN_H // 2 - 60)
        glVertex2f(WIN_W // 2 + 240, WIN_H // 2 + 60)
        glVertex2f(WIN_W // 2 - 240, WIN_H // 2 + 60)
        glEnd()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glColor3f(0.1, 1.0, 0.3)
        draw_text(WIN_W // 2 - 165, WIN_H // 2 + 16,
                  f"LEVEL {lv - 1} COMPLETE!",
                  font=GLUT_BITMAP_TIMES_ROMAN_24)
        glColor3f(0.95, 0.95, 0.2)
        draw_text(WIN_W // 2 - 130, WIN_H // 2 - 20,
                  f"Find the new green zone - Level {lv}")

    # Game over overlay
    if state['game_over']:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, WIN_W, 0, WIN_H)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        set_color(0.0, 0.0, 0.0)
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(WIN_W, 0)
        glVertex2f(WIN_W, WIN_H)
        glVertex2f(0, WIN_H)
        glEnd()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glColor3f(1.0, 0.1, 0.1)
        draw_text(WIN_W // 2 - 115, WIN_H // 2 + 20, "GAME OVER",
                  font=GLUT_BITMAP_TIMES_ROMAN_24)
        glColor3f(1.0, 1.0, 1.0)
        draw_text(WIN_W // 2 - 110, WIN_H // 2 - 18, "Press R to restart")

    # Win overlay
    if state['game_won']:
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, WIN_W, 0, WIN_H)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        set_color(0.0, 0.08, 0.0)
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(WIN_W, 0)
        glVertex2f(WIN_W, WIN_H)
        glVertex2f(0, WIN_H)
        glEnd()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glColor3f(0.2, 1.0, 0.4)
        draw_text(WIN_W // 2 - 195, WIN_H // 2 + 20,
                  "YOU WIN! ALL LEVELS DONE!",
                  font=GLUT_BITMAP_TIMES_ROMAN_24)
        glColor3f(1.0, 1.0, 1.0)
        draw_text(WIN_W // 2 - 100, WIN_H // 2 - 18,
                  "Press R to play again")

    glEnable(GL_DEPTH_TEST)
    glutSwapBuffers()


def keyboardUpListener(key, x, y):
    k = key.decode('utf-8', errors='ignore').upper()
    if k == 'W':
        keys['W'] = False
    elif k == 'S':
        keys['S'] = False
    elif k == 'A':
        keys['A'] = False
    elif k == 'D':
        keys['D'] = False
    elif k == 'X':
        keys['X'] = False


def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WIN_W, WIN_H)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"3D Car Parking Game - Police Patrol System")
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.18, 0.18, 0.22, 1.0)
    random.seed(int(time.time()))
    state['level'] = 1
    init_level()
    last_time[0] = glutGet(GLUT_ELAPSED_TIME) / 1000.0
    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)
    glutKeyboardUpFunc(keyboardUpListener)
    glutMainLoop()


if __name__ == '__main__':
    main()