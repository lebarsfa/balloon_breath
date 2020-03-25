#!/usr/bin/python
import ms5837
import RPi.GPIO as GPIO
import math
import sys
import os
import time
import threading
from timeit import default_timer as timer

from matplotlib.pyplot import *

#sudo apt-get install python-smbus
# or
#sudo pip install smbus
# if it did not work.
# Raspberry Pi configuration :
#sudo nano /boot/config.txt
# Add in /boot/config.txt
#dtparam=i2c_arm=on
#dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
# Then reboot and
#sudo python example.py

# Parameters
###############################################################################
p_delta_max = 20 # In mbar
p_delta_danger_max = 25 # In mbar
p_delta_danger_min = -5 # In mbar
breath_freq = 30 # In cycles/min
inspi_ratio = 1.0/3.0
#trim PWM value start, end depending on balloon size...
pwm_ns_min = 1000000
pwm_ns_max = 2000000
###############################################################################

# Software PWM init (for buzzer and status LED)
GPIO.setwarnings(False)	
GPIO.setmode(GPIO.BCM)
buz_pin = 26
GPIO.setup(buz_pin,GPIO.OUT)
buz_pwm = GPIO.PWM(buz_pin, 4000)
buz_pwm.start(50)
led_pin = 16
GPIO.setup(led_pin,GPIO.OUT)
led_pwm = GPIO.PWM(led_pin, 1000)
led_pwm.start(100)

# Hardware PWM init (for servos)
os.system('echo 0 > /sys/class/pwm/pwmchip0/export')
os.system('echo 1 > /sys/class/pwm/pwmchip0/export')
os.system('echo 20000000 > /sys/class/pwm/pwmchip0/pwm0/period')
os.system('echo 20000000 > /sys/class/pwm/pwmchip0/pwm1/period')
os.system('echo 1000000 > /sys/class/pwm/pwmchip0/pwm0/duty_cycle')
os.system('echo 1000000 > /sys/class/pwm/pwmchip0/pwm1/duty_cycle')
os.system('echo 1 > /sys/class/pwm/pwmchip0/pwm0/enable')
os.system('echo 1 > /sys/class/pwm/pwmchip0/pwm1/enable')

#sensor = ms5837.MS5837_30BA() # Default I2C bus is 1 (Raspberry Pi 3)
#sensor = ms5837.MS5837_30BA(0) # Specify I2C bus
sensor = ms5837.MS5837_02BA()
#sensor = ms5837.MS5837(model=ms5837.MS5837_MODEL_30BA, bus=0) # Specify model
#and bus
if not sensor.init():
    print('Sensor could not be initialized')
    exit(1)

if not sensor.read():
    print('Sensor read failed!')
    exit(1)

breath_freq_converted = breath_freq*(1.0/60.0) # In cycles/s
cycle_duration = 1.0/breath_freq_converted
inspi_duration = inspi_ratio*cycle_duration
expi_duration = cycle_duration-inspi_duration

t = timer()
t_prev = t
t0 = t
t_cycle_start = t
p = sensor.pressure()
p_prev = p
p0 = p
p_cycle_start = p
temperature = sensor.temperature()
inspi_end = False
inspi_duration_estim = inspi_duration
expi_duration_estim = expi_duration
cycle_duration_estim = cycle_duration

pwm_ns = pwm_ns_min

file = open('data.csv', 'a')

fig = figure('Pressure')
#clf()
#axis('square')
scalex = 10
scaley = 1.5*p_delta_max
offsetx = -scalex
offsety = p0

# Divisions by 0...

# Should check p behavior (too high, too low, should compute p_delta_meas_min,
# p_delta_meas_max)...
count = 0
while True:

    #pwm_ns =
    #1000000*(1.5-0.5*math.cos(2*math.pi*(t-t_cycle_start)/cycle_duration_estim))

    # Should check bounds of pwm...
    if (t-t_cycle_start < inspi_duration_estim):
        pwm_ns = pwm_ns_min+(pwm_ns_max-pwm_ns_min)*(t-t_cycle_start)/inspi_duration_estim
    else:
        pwm_ns = pwm_ns_max-(pwm_ns_max-pwm_ns_min)*(t-t_cycle_start-inspi_duration_estim)/expi_duration_estim
    pwm_ns = min(pwm_ns_max, max(pwm_ns_min, pwm_ns))

    #if (p-p_cycle_start < p_delta_max) and !inspi_end:
    #    pwm_ns = 1000000*(1+(t-t_cycle_start)/inspi_duration_estim)
    #    if (t-t_cycle_start > inspi_duration_estim):
    #        print('!!!  WARNING !!!')
    #        inspi_end = True
    #        inspi_duration_estim = inspi_duration
    #        expi_duration_estim = expi_duration
    #        cycle_duration_estim = cycle_duration
    #else:
    #    if (!inspi_end):
    #       inspi_end = True
    #       inspi_duration_estim = t-t_cycle_start
    #       expi_duration_estim = (1-inspi_ratio)*inspi_duration_estim
    #       cycle_duration_estim = inspi_duration_estim+expi_duration_estim
    #    pwm_ns = 1000000*(1-(t-t_cycle_start)/expi_duration_estim)

    pwm0_cmd = 'echo {} > /sys/class/pwm/pwmchip0/pwm0/duty_cycle'
    pwm1_cmd = 'echo {} > /sys/class/pwm/pwmchip0/pwm1/duty_cycle'
    os.system(pwm0_cmd.format(math.trunc(pwm_ns)))
    os.system(pwm1_cmd.format(math.trunc(pwm_ns)))
    #print(pwm_ns)

    # Test...
    buz_pwm.ChangeFrequency(math.trunc(pwm_ns/1000.0))
    led_pwm.ChangeDutyCycle(min(100, max(0, math.trunc(100*min(1.0, (t-t_cycle_start)/cycle_duration_estim)))))
    
    line = '{};{};{}\n'
    file.write(line.format(t, p, temperature))
    file.flush()

    if ((t-t_cycle_start) != 0) and (count % 200 == 0): # Clear from time to time since the plots accumulate...
        clf()
    axis([-scalex+offsetx,scalex+offsetx,-scaley+offsety,scaley+offsety])
    plot([t_prev-t0,t-t0], [p_prev,p], 'b')
    pause(0.000001)
    offsetx = offsetx+t-t_prev
 
    if sensor.read(ms5837.OSR_256):
        print('t-t0: %0.2f s \tdt: %0.2f s \tP: %0.1f mbar \tT: %0.2f C ') % (t-t0, t-t_prev, p, temperature) 
    else:
        print('Sensor read failed!')
        exit(1)
    
    t_prev = t
    t = timer()
    p_prev = p
    p = sensor.pressure()
    temperature = sensor.temperature()
    if (t-t_cycle_start > cycle_duration_estim):
        t_cycle_start = t
        p_cycle_start = p
        inspi_end = False
    count = count+1
