"""Remappable human inputs produce ordinary frozen-simulation actions."""
from math import copysign
import pygame
from pygame._sdl2 import controller
from ..config import PHYSICS, VIEWER
from ..sim.physics import approach, clamp
from .config import CLIENT


def analog(value):
    magnitude=max(0.,(abs(value)-CLIENT.deadzone)/(1-CLIENT.deadzone))
    return copysign(min(1.,magnitude)**CLIENT.analog_curve,value)


class Controls:
    def __init__(self,settings):
        self.settings=settings
        self.steer=0.
        self.pad=None
        controller.init()
        self.refresh()

    def refresh(self):
        # Offscreen checks must not consume a connected user's controller input.
        if pygame.display.get_driver()=='dummy': return
        if self.pad is not None:
            try:
                if self.pad.attached(): return
            except pygame.error: pass
            self.pad=None
        for index in range(controller.get_count()):
            if controller.is_controller(index):
                try: self.pad=controller.Controller(index)
                except pygame.error: continue
                break

    def action(self,state):
        keys=pygame.key.get_pressed()
        bindings=self.settings['bindings']
        def held(name,fallback):
            try: return keys[bindings[name]] or keys[fallback]
            except (IndexError,KeyError): return keys[fallback]
        target=float(held('left',pygame.K_LEFT))-float(held('right',pygame.K_RIGHT))
        pedal=float(held('throttle',pygame.K_UP))-float(held('brake',pygame.K_DOWN))
        if self.pad:
            try:
                stick=-analog(self.pad.get_axis(pygame.CONTROLLER_AXIS_LEFTX)/32767)
                throttle=max(0.,self.pad.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT)/32767)
                brake=max(0.,self.pad.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT)/32767)
                if abs(stick)>abs(target): target=stick
                if abs(throttle-brake)>abs(pedal): pedal=throttle-brake
            except pygame.error:
                self.pad=None
        self.steer=approach(self.steer,target,VIEWER.keyboard_rate*PHYSICS.dt)
        # Optional countersteer changes input only, never physics or tire grip.
        steer=self.steer
        if self.settings['assist'] and abs(state.vx)>3:
            steer-=clamp(state.slip_rear,-.5,.5)*CLIENT.assist_yaw
        return clamp(steer,-1,1),clamp(pedal,-1,1)
