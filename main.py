
from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.datatables import MDDataTable
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.config import Config
from kivy.metrics import dp
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
from kivy.properties import ObjectProperty
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import os
#import minimalmodbus
import time
import serial
from serial.tools import list_ports


plt.style.use('bmh')

colors = {
    "Red": {
        "200": "#EE2222",
        "500": "#EE2222",
        "700": "#EE2222",
    },
    "Blue": {
        "200": "#196BA5",
        "500": "#196BA5",
        "700": "#196BA5",
    },
    "Light": {
        "StatusBar": "E0E0E0",
        "AppBar": "#202020",
        "Background": "#EEEEEE",
        "CardsDialogs": "#FFFFFF",
        "FlatButtonDown": "#CCCCCC",
    },
    "Dark": {
        "StatusBar": "101010",
        "AppBar": "#E0E0E0",
        "Background": "#111111",
        "CardsDialogs": "#000000",
        "FlatButtonDown": "#333333",
    },
}

DEBUG = False

STEPS = 51
MAX_POINT = 10000
ELECTRODES_NUM = 48

PIN_ENABLE = 23 #16
PIN_POLARITY = 24 #18

USERNAME = "labtek"
DISK_ADDRESS = Path("D:\\") #windows version
SERIAL_NUMBER = "2301212112233412"

BAUDRATE = 9600
BYTESIZE = 8
PARITY = serial.PARITY_NONE
STOPBIT = 1
TIMEOUT = 0.5

REQUEST_TIME_OUT = 5.0
DELAY_INITIAL = 7 #in seconds
UPDATE_INTERVAL = 2 #in seconds
UPDATE_INTERVAL_GRAPH = 5
GRAPH_STATE_COUNT = 5

x_electrode = np.zeros((4, MAX_POINT))
n_electrode = np.zeros((ELECTRODES_NUM, STEPS))
c_electrode = np.array(["#196BA5","#FF0000","#FFDD00","#00FF00","#00FFDD"])
l_electrode = np.array(["Datum","C1","C2","P1","P2"])
arr_electrode = np.zeros([4, 0], dtype=int)
data_base = np.zeros([5, 0])
data_electrode = np.zeros([4, 0], dtype=int)
data_pos = np.zeros([2, 0])

checks_mode = []
checks_config = []
dt_mode = ""
dt_config = ""
dt_distance = 1
dt_constant = 1
real_constant = 1
dt_time = 500
dt_cycle = 1
dt_threshold = 20.0

dt_measure = np.zeros(6)
dt_current = np.zeros(10)
dt_voltage = np.zeros(10)
flag_run = False
flag_run_prev = False
flag_measure = False
flag_dongle = True
flag_autosave_data = False
flag_autosave_graph = False

data_rtu = np.zeros([216, 0], dtype=int)
data_rtu1 = np.zeros(36, dtype=int)
data_rtu2 = np.zeros(36, dtype=int)
data_rtu3 = np.zeros(36, dtype=int)
data_rtu4 = np.zeros(36, dtype=int)
data_rtu5 = np.zeros(36, dtype=int)
data_rtu6 = np.zeros(36, dtype=int)

step = 0
max_step = 1

count_mounting = 0
inject_state = 0
graph_state = 0

class ScreenSplash(BoxLayout):
    screen_manager = ObjectProperty(None)
    screen_setting = ObjectProperty(None)
    app_window = ObjectProperty(None)
    
    def __init__(self, **kwargs):
        super(ScreenSplash, self).__init__(**kwargs)
        try:
            os.system('cmd /c "cd /media"')
            os.system('cmd /c "sudo rm -r /labtek"')
        except:
            pass
        Clock.schedule_interval(self.update_progress_bar, 0.035)

    def update_progress_bar(self, *args):
        if (self.ids.progress_bar.value + 1) < 100:
            raw_value = self.ids.progress_bar_label.text.split("[")[-1]
            value = raw_value[:-2]
            value = eval(value.strip())
            new_value = value + 1
            self.ids.progress_bar.value = new_value
            self.ids.progress_bar_label.text = "Loading.. [{:} %]".format(new_value)
        else:
            self.ids.progress_bar.value = 100
            self.ids.progress_bar_label.text = "Loading.. [{:} %]".format(100)
            self.screen_manager.current = "screen_setting"
            return False

class ScreenSetting(BoxLayout):
    screen_manager = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(ScreenSetting, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, DELAY_INITIAL)

    def delayed_init(self, dt):
        global rtu1, rtu2, rtu3, rtu4, rtu5, rtu6
        global data_rtu1, data_rtu2, data_rtu3, data_rtu4, data_rtu5, data_rtu6
        global arr_electrode
        global serial_obj

        Clock.schedule_interval(self.regular_check_event, UPDATE_INTERVAL)

        self.ids.bt_shutdown.md_bg_color = "#A50000"
        self.ids.mode_ves.active = True

        self.fig, self.ax = plt.subplots()
        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        l, b, w, h = self.ax.get_position().bounds
        self.ax.set_position(pos=[l, b + 0.3*h, w, h*0.7])
        
        self.ax.set_xlabel("distance [m]", fontsize=10)
        self.ax.set_ylabel("n", fontsize=10)

        self.ids.layout_illustration.add_widget(FigureCanvasKivyAgg(self.fig))

        try:
            self.connect_to_mcu()
            Clock.schedule_interval(self.read_mcu, REQUEST_TIME_OUT)
            toast("Switching unit is sucessfully connected")
        except:
            Clock.schedule_interval(self.auto_reconnect, REQUEST_TIME_OUT)
            toast("Switching unit is disconnected")

        try:
            serial_obj.write(b"%") # reset switching
            data_reset = serial_obj.readline().decode("utf-8").strip()  # read the incoming data and remove newline character
            while True:
                print(data_reset)
                if data_reset == "Semua decoder mati":
                    break
                else:
                    serial_obj.write(b"%") # reset switching
                    data_reset = serial_obj.readline().decode("utf-8").strip()

        except:
            toast("No Switching Unit connected")
            # print("no switching box connected")

    def auto_reconnect(self, dt):
        try:
            self.connect_to_mcu()
            Clock.schedule_interval(self.read_mcu, REQUEST_TIME_OUT)
            Clock.unschedule(self.auto_reconnect)
        except:
            toast("Switching unit is disconnected, try reconnecting..")

    def read_mcu(self, dt):
        global serial_obj
        global dt_threshold

        if(not DEBUG):
            try:
                print("Reading mcu")
                serial_obj.write(b" ")
            except Exception as e:
                Clock.schedule_interval(self.auto_reconnect, REQUEST_TIME_OUT)
                error_msg = "Error reading Switching unit :" + str(e)
                print(error_msg)

    def connect_to_mcu(self):
        global serial_obj

        if(not DEBUG):
            try:
                serial_obj = serial.Serial("COM8")  # COM to Microcontroller, checked manually
                serial_obj.baudrate = BAUDRATE
                serial_obj.parity = PARITY
                serial_obj.bytesize = BYTESIZE
                toast("Sucessfully connect to Switching unit")
            except Exception as e:
                error_msg = "Error connect to Switching unit :" + str(e)
                print(error_msg)
                toast("Error connect to Switching unit, try reconnecting")
    
    def regular_check_event(self, dt):
        # print("this is regular check event at setting screen")
        global flag_run
        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"
        else:
            self.ids.bt_measure.text = "RUN MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#196BA5"

    def threshold_up(self):
        global dt_threshold
        global serial_obj

        if(not DEBUG):
            serial_obj.write(b">")
            data_threshold_up = serial_obj.readline().decode("utf-8").strip()
            while True:
                print(data_threshold_up)
                if data_threshold_up[0] == "t":                
                # if data_threshold_up != "":
                    serial_threshold_up = float(data_threshold_up[1:])
                    dt_threshold = serial_threshold_up
                    self.ids.lb_volt_threshold.text = str(dt_threshold) + " mV"
                    break
                else:
                    serial_obj.write(b">")
                    data_threshold_up = serial_obj.readline().decode("utf-8").strip()
                    break

    def threshold_down(self):
        global dt_threshold
        global serial_obj

        if(not DEBUG):
            serial_obj.write(b"<")
            data_threshold_down = serial_obj.readline().decode("utf-8").strip()
            while True:
                print(data_threshold_down)
                if data_threshold_down[0] == "t":
                # if data_threshold_down != "":
                    data_threshold_down = float(data_threshold_down[1:])
                    dt_threshold = data_threshold_down
                    self.ids.lb_volt_threshold.text = str(dt_threshold) + " mV"
                    break
                else:
                    serial_obj.write(b"<")
                    data_threshold_down = serial_obj.readline().decode("utf-8").strip()
                    break


    def illustrate(self):
        global dt_mode, dt_config, dt_distance, dt_constant, dt_time, dt_cycle
        global x_datum, y_datum, data_pos, data_rtu, max_step, arr_electrode

        dt_distance = self.ids.slider_distance.value
        dt_constant = self.ids.slider_constant.value
        dt_time = int(self.ids.slider_time.value)
        dt_cycle = int(self.ids.slider_cycle.value)

        self.fig, self.ax = plt.subplots()
        self.ids.layout_illustration.remove_widget(FigureCanvasKivyAgg(self.fig))
        x_datum = np.zeros(MAX_POINT)
        y_datum = np.zeros(MAX_POINT)
        x_electrode = np.zeros((4, MAX_POINT))

        if("WENNER (ALPHA)" in dt_config):
            num_step = 0
            num_trial = 1
            for multiplier in range(dt_constant):
                for pos_el in range(ELECTRODES_NUM - 3 * num_trial):
                    x_electrode[0, num_step] = pos_el
                    x_electrode[1, num_step] = num_trial + x_electrode[0, num_step]
                    x_electrode[2, num_step] = num_trial + x_electrode[1, num_step]
                    x_electrode[3, num_step] = num_trial + x_electrode[2, num_step]
                    x_datum[num_step] = (
                        x_electrode[1, num_step]
                        + (x_electrode[2, num_step] - x_electrode[1, num_step]) / 2
                    ) * dt_distance
                    y_datum[num_step] = (multiplier + 1) * dt_distance

                    num_step += 1

                num_trial += 1

        elif("WENNER (BETA)" in dt_config):
            num_step = 0
            num_trial = 1
            for multiplier in range(dt_constant):
                for pos_el in range(ELECTRODES_NUM - 3 * num_trial):
                    x_electrode[0, num_step] = pos_el
                    x_electrode[1, num_step] = num_trial + x_electrode[0, num_step]
                    x_electrode[2, num_step] = num_trial + x_electrode[1, num_step]
                    x_electrode[3, num_step] = num_trial + x_electrode[2, num_step]
                    x_datum[num_step] = (x_electrode[1, num_step] + (x_electrode[2, num_step] - x_electrode[1, num_step])/2) * dt_distance
                    y_datum[num_step] = (multiplier + 1) * dt_distance
                    
                    num_step += 1

                num_trial += 1

        if("WENNER (GAMMA)" in dt_config):
            num_step = 0
            num_trial = 1
            for multiplier in range(dt_constant):
                for pos_el in range(ELECTRODES_NUM - 3 * num_trial):
                    x_electrode[0, num_step] = pos_el
                    x_electrode[1, num_step] = num_trial + x_electrode[0, num_step]
                    x_electrode[2, num_step] = num_trial + x_electrode[1, num_step]
                    x_electrode[3, num_step] = num_trial + x_electrode[2, num_step]
                    x_datum[num_step] = (x_electrode[1, num_step] + (x_electrode[2, num_step] - x_electrode[1, num_step])/2) * dt_distance
                    y_datum[num_step] = (multiplier + 1) * dt_distance
                    
                    num_step += 1

                num_trial += 1

        elif("SCHLUMBERGER" in dt_config):
            num_step = 0
            num_trial = 1
            for multiplier in range(dt_constant):
                for pos_el in range(ELECTRODES_NUM - 3 * num_trial):
                    x_electrode[0, num_step] = pos_el
                    x_electrode[1, num_step] = num_trial + x_electrode[0, num_step]
                    x_electrode[2, num_step] = num_trial + x_electrode[1, num_step]
                    x_electrode[3, num_step] = num_trial + x_electrode[2, num_step]
                    x_datum[num_step] = (x_electrode[1, num_step] + (x_electrode[2, num_step] - x_electrode[1, num_step])/2) * dt_distance
                    y_datum[num_step] = (multiplier + 1) * dt_distance
                    
                    num_step += 1

                num_trial += 1

        elif("DIPOLE-DIPOLE" in dt_config):
            nmax_available = 0
            if(ELECTRODES_NUM % 2) != 0:
                if(dt_constant > (ELECTRODES_NUM - 3) / 2):
                    nmax_available = (ELECTRODES_NUM - 3) / 2
                else:
                    nmax_available = dt_constant
            else:
                if(dt_constant > (ELECTRODES_NUM - 3) / 2):
                    nmax_available = round((ELECTRODES_NUM - 3) / 2)
                else:
                    nmax_available = dt_constant

            num_datum = 0
            count_datum = 0      
            for i in range(nmax_available):
                for j in range(ELECTRODES_NUM - 1 - i * 2):
                    num_datum = num_datum + j
                count_datum = count_datum + num_datum
                num_datum = 0     

            num_step = 0
            num_trial = 0
            for i in range(nmax_available):
                for j in range(ELECTRODES_NUM - 1 - i * 2):
                    for k in range(ELECTRODES_NUM - i * 2 - j - 1):
                        x_electrode[1, num_step] = j - 1
                        x_electrode[0, num_step] = j + (i - 2)
                        x_electrode[2, num_step] = num_trial + 2 + x_electrode[0, num_step]
                        x_electrode[3, num_step] = i + 1 + x_electrode[2, num_step]
                        x_datum[num_step] = (x_electrode[0, num_step] + (x_electrode[2, num_step] - x_electrode[0, num_step])/2) * dt_distance
                        y_datum[num_step] = (i + 1) * dt_distance
                        
                        num_step += 1
                        num_trial += 1

                    num_trial = 0
        else:
            x_electrode[0,0] = 0
            x_electrode[1,0] = 1
            x_electrode[2,0] = 2
            x_electrode[3,0] = 3

        try:
            max_step = np.trim_zeros(x_electrode[1,:]).size

            data_c1 = x_electrode[0,:max_step]
            data_p1 = x_electrode[1,:max_step]
            data_p2 = x_electrode[2,:max_step]
            data_c2 = x_electrode[3,:max_step]

            arr_electrode = np.array([data_c1, data_p1, data_p2, data_c2], dtype=int)

        except:
            # print("error simulating")
            toast("Error simulating measurement configuration")

        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        l, b, w, h = self.ax.get_position().bounds
        self.ax.set_position(pos=[l, b + 0.3*h, w*0.9, h*0.7])
        self.ax.set_xlabel("distance [m]", fontsize=10)
        self.ax.set_ylabel("n", fontsize=10)
       
        self.ax.set_facecolor("#eeeeee")
        
        x_data = np.trim_zeros(x_datum)
        y_data = np.trim_zeros(y_datum)
        data_pos = np.array([x_data, y_data])

        #datum location
        self.ax.scatter(x_data, y_data, c=c_electrode[0], label=l_electrode[0], marker='.')

        #electrode location
        self.ax.scatter(x_electrode[0,0]*dt_distance , 0, c=c_electrode[1], label=l_electrode[1], marker=7)
        self.ax.scatter(x_electrode[1,0]*dt_distance , 0, c=c_electrode[2], label=l_electrode[2], marker=7)
        self.ax.scatter(x_electrode[2,0]*dt_distance , 0, c=c_electrode[3], label=l_electrode[3], marker=7)
        self.ax.scatter(x_electrode[3,0]*dt_distance , 0, c=c_electrode[4], label=l_electrode[4], marker=7)

        self.ax.invert_yaxis()
        self.ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), title="Electrode")         
        self.ids.layout_illustration.clear_widgets()
        self.ids.layout_illustration.add_widget(FigureCanvasKivyAgg(self.fig))

    def measure(self):
        global flag_run

        if(flag_run):
            flag_run = False
        else:
            flag_run = True

    def checkbox_mode_click(self, instance, value, waves):
        global checks_mode
        global dt_mode
        
        if value == True:
            checks_mode.append(waves)
            modes = ''
            for x in checks_mode:
                modes = f'{modes} {x}'
            self.ids.output_mode_label.text = f'{modes} MODE CHOSEN'
        else:
            checks_mode.remove(waves)
            modes = ''
            for x in checks_mode:
                modes = f'{modes} {x}'
            self.ids.output_mode_label.text = ''
        
        dt_mode = modes

    def checkbox_config_click(self, instance, value, waves):
        global checks_config
        global dt_config

        if value == True:
            checks_config.append(waves)
            configs = ''
            for x in checks_config:
                configs = f'{configs} {x}'
            self.ids.output_config_label.text = f'{configs} CONFIGURATION CHOSEN'
        else:
            checks_config.remove(waves)
            configs = ''
            for x in checks_config:
                configs = f'{configs} {x}'
            self.ids.output_config_label.text = ''
        
        dt_config = configs

    def screen_setting(self):
        self.screen_manager.current = 'screen_setting'

    def screen_data(self):
        self.screen_manager.current = 'screen_data'

    def screen_graph(self):
        self.screen_manager.current = 'screen_graph'

    def exec_shutdown(self):
        global flag_run

        if(not flag_run):        
            toast("Shutting down system")
            os.system("shutdown /s /t 1") #for windows os
            # os.system("shutdown -h now") #for linux os
        else:
            toast("Cannot shutting down while measuring")


class ScreenData(BoxLayout):
    screen_manager = ObjectProperty(None)

    def __init__(self, **kwargs):
        global dt_time
        global dt_cycle

        super(ScreenData, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, DELAY_INITIAL)

    def delayed_init(self, dt):
        Clock.schedule_interval(self.regular_check_event, UPDATE_INTERVAL)

        self.ids.bt_shutdown.md_bg_color = "#A50000"
        layout = self.ids.layout_tables
        
        self.data_tables = MDDataTable(
            use_pagination=True,
            pagination_menu_pos="auto",
            rows_num=4,
            column_data=[
                ("No.", dp(10), self.sort_on_num),
                ("Volt [V]", dp(27)),
                ("Curr [mA]", dp(27)),
                ("Resi [kOhm]", dp(27)),
                ("Std Dev Res", dp(27)),
                ("IP (R decay)", dp(27)),
            ],
        )
        layout.add_widget(self.data_tables)

    def regular_check_event(self, dt):
        # print("this is regular check event at data screen")
        global flag_run, flag_run_prev
        global flag_measure
        global flag_dongle
        global count_mounting
        global dt_time
        global dt_cycle
        global dt_mode
        global inject_state
        global flag_autosave_data
        global step
        global max_step
        global serial_obj

        if not DISK_ADDRESS.exists() and flag_dongle:
             try:
                 toast("Try mounting The Dongle")
                 serial_file = str(DISK_ADDRESS) + "\serial.key" #for windows os
                #  serial_file = str(DISK_ADDRESS) + "/serial.key" #for linux os 
                 # print(serial_file)
                 with open(serial_file,"r") as f:
                     serial_number = f.readline()
                     if serial_number == SERIAL_NUMBER:
                         toast("Successfully mounting The Dongle, the Serial number is valid")
                         self.ids.bt_save_data.disabled = False
                     else:
                         toast("Failed mounting The Dongle, the Serial number is invalid")
                         self.ids.bt_save_data.disabled = True                    
             except:
                 toast("The Dongle could not be mounted")
                 self.ids.bt_save_data.disabled = True
                 count_mounting += 1
                 if(count_mounting > 2):
                     flag_dongle = False 

        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"

            flag_autosave_data = True
            measure_interval = (int(4 * dt_cycle * dt_time) / 1000)
            inject_interval = (int(dt_time) / 1000)
            # print("measure interval:", measure_interval, " inject interval:", inject_interval)

            if("(VES) VERTICAL ELECTRICAL SOUNDING" in dt_mode):
                if(flag_measure == False):
                    Clock.schedule_interval(self.measurement_check_event, measure_interval)
                    Clock.schedule_interval(self.inject_current_event, inject_interval)
                flag_measure = True
        
            elif("(SP) SELF POTENTIAL" in dt_mode):
                if(flag_measure == False):
                    Clock.schedule_interval(self.measurement_check_event, measure_interval)
                    Clock.schedule_interval(self.measurement_sampling_event, inject_interval)
                flag_measure = True
                
            elif("(R) RESISTIVITY" in dt_mode):
                if(flag_measure == False):
                    Clock.schedule_interval(self.measurement_check_event, measure_interval)
                    Clock.schedule_interval(self.inject_current_event, inject_interval)
                flag_measure = True
                
            elif("(R+IP) INDUCED POLARIZATION" in dt_mode):
                if(flag_measure == False):
                    Clock.schedule_interval(self.measurement_check_event, measure_interval)
                    Clock.schedule_interval(self.inject_current_event, inject_interval)
                flag_measure = True                        
            else:
                pass

        else:
            self.ids.bt_measure.text = "RUN MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#196BA5"
            self.stop_measure()
        
        if(flag_run == False and flag_run_prev == True):
            self.reset_switching()
        
        flag_run_prev = flag_run

    def stop_measure(self):
        global flag_measure
        global inject_state
        global flag_autosave_data
        global step
        global max_step
        global serial_obj

        self.ids.bt_measure.text = "RUN MEASUREMENT"
        self.ids.bt_measure.md_bg_color = "#196BA5"
        Clock.unschedule(self.measurement_sampling_event)
        Clock.unschedule(self.measurement_check_event)
        Clock.unschedule(self.inject_current_event)
        inject_state = 0
        flag_measure = False
        step = 0
        max_step = 0

        if flag_autosave_data:
            self.autosave_data()
            flag_autosave_data = False

    def measurement_check_event(self, dt):
        # print("this is measurement check event at data screen")
        global flag_run
        global dt_time
        global dt_cycle
        global data_base
        global arr_electrode
        global data_electrode
        global dt_current
        global dt_voltage
        global x_electrode
        global step
        global serial_obj

        if("WENNER (ALPHA)" in dt_config):
            k = 2 * np.pi * dt_distance * dt_constant
        elif("WENNER (BETA)" in dt_config):
            k = 6 * np.pi * dt_distance * dt_constant
        elif("WENNER (GAMMA)" in dt_config):
            k = 3 * np.pi * dt_distance * dt_constant
        elif("POLE-POLE" in dt_config):
            k = 2 * np.pi * dt_distance * dt_constant
        elif("DIPOLE-DIPOLE" in dt_config):
            k = np.pi * dt_distance * dt_constant * (dt_constant + 1) * (dt_constant + 2)
        elif("SCHLUMBERGER" in dt_config):
            k = np.pi * dt_distance * dt_constant * (dt_constant + 1)
        else:
            k = 1

        voltage = np.max(np.fabs(dt_voltage))
        current = np.max(np.fabs(dt_current))
        if(current > 0.0):
            resistivity = k * voltage / current
            resistivity = k * voltage / current
        else:
            resistivity = 0.0
            resistivity = 0.0
            
        std_resistivity = np.std(data_base[2, :])
        ip_decay = (np.sum(dt_voltage) / voltage ) * (int(dt_cycle * dt_time)/10000)

        data_acquisition = np.array([voltage, current, resistivity, std_resistivity, ip_decay])
        data_acquisition.resize([5, 1])
        data_base = np.concatenate([data_base, data_acquisition], axis=1)

        try:
            data_c1 = arr_electrode[0, step] + 1
            data_p1 = arr_electrode[1, step] + 1
            data_p2 = arr_electrode[2, step] + 1
            data_c2 = arr_electrode[3, step] + 1
            electrode_pos = np.array([data_c1, data_p1, data_p2, data_c2])
        except:
            electrode_pos = np.array([1, 2, 3, 4])

        electrode_pos.resize([4, 1])
        data_electrode = np.concatenate([data_electrode, electrode_pos], axis=1)

        try:
            data_c1 = arr_electrode[0, step] + 1
            data_p1 = arr_electrode[1, step] + 1
            data_p2 = arr_electrode[2, step] + 1
            data_c2 = arr_electrode[3, step] + 1
            electrode_pos = np.array([data_c1, data_p1, data_p2, data_c2])
        except:
            electrode_pos = np.array([1, 2, 3, 4])

        electrode_pos.resize([4, 1])
        data_electrode = np.concatenate([data_electrode, electrode_pos], axis=1)

        self.ids.realtime_voltage.text = f"{voltage:.3f}"
        self.ids.realtime_current.text = f"{current:.3f}"
        self.ids.realtime_resistivity.text = f"{resistivity:.3f}"

        avg_voltage = np.average(data_base[0, :])
        avg_current = np.average(data_base[1, :])
        avg_resistivity = np.average(data_base[2, :])

        self.ids.average_voltage.text = f"{avg_voltage:.3f}"
        self.ids.average_current.text = f"{avg_current:.3f}"
        self.ids.average_resistivity.text = f"{avg_resistivity:.3f}"

        avg_voltage = np.average(data_base[0, :])
        avg_current = np.average(data_base[1, :])
        avg_resistivity = np.average(data_base[2, :])

        self.ids.average_voltage.text = f"{avg_voltage:.3f}"
        self.ids.average_current.text = f"{avg_current:.3f}"
        self.ids.average_resistivity.text = f"{avg_resistivity:.3f}"

        self.data_tables.row_data=[(f"{i + 1}", f"{data_base[0,i]:.3f}", f"{data_base[1,i]:.3f}", f"{data_base[2,i]:.3f}", f"{data_base[3,i]:.3f}", f"{data_base[4,i]:.3f}") for i in range(len(data_base[1]))]

    def inject_current_event(self, dt):
        # print("this is inject current event at data screen")
        global inject_state
        global step
        global dt_cycle
        global dt_time
        global serial_obj

        time_sampling = (int(dt_time) / 10000)
        # print("sampling time:", time_sampling, ", inject state:", inject_state)

        if(inject_state >= int(4 * dt_cycle)):
            Clock.unschedule(self.measurement_sampling_event)
            inject_state = 0
            step += 1
            
        if(inject_state == 0 or inject_state == 4 or inject_state == 8 or inject_state == 12 or inject_state == 16 or inject_state == 20 or inject_state == 24 or inject_state == 28 or inject_state == 32 or inject_state == 36):
            Clock.unschedule(self.measurement_sampling_event)
            
            if(not DEBUG):
                serial_obj.write(b"_") # inject positive current
                data_stop_inject = serial_obj.readline().decode("utf-8").strip()
                
                print(data_stop_inject)
                # toast(data_stop_inject)
                while True:  
                    if data_stop_inject == "Not Injected":
                        break
                    else:
                        serial_obj.write(b"_")
                        data_stop_inject = serial_obj.readline().decode("utf-8").strip()
                self.switching_commands()
            
        elif(inject_state == 1 or inject_state == 5 or inject_state == 9 or inject_state == 13 or inject_state == 17 or inject_state == 21 or inject_state == 25 or inject_state == 29 or inject_state == 33 or inject_state == 37):
            Clock.schedule_interval(self.measurement_sampling_event, time_sampling)

            if(not DEBUG):
                serial_obj.write(b"/")
                data_reset_inject = serial_obj.readline().decode("utf-8").strip()
                print(data_reset_inject)
                # toast(data_reset_inject)
                while True:
                    if data_reset_inject == "Reset Inject Voltage":
                        break
                    else:
                        serial_obj.write(b"/")
                        data_reset_inject = serial_obj.readline().decode("utf-8").strip()
                
                serial_obj.write(b"+")
                data_plus_inject = serial_obj.readline().decode("utf-8").strip()
                print(data_plus_inject)
                toast(data_plus_inject)
                while True:
                    if data_plus_inject == "Inject Positif":
                        break
                    else:
                        serial_obj.write(b"+")
                        data_plus_inject = serial_obj.readline().decode("utf-8").strip()

                data_indikasi_lanjut = serial_obj.readline().decode("utf-8").strip()
                print(data_indikasi_lanjut)
                # toast(data_indikasi_lanjut)
                while True:
                    if data_indikasi_lanjut == "Lanjut":
                        break
                    else:
                        data_indikasi_lanjut = serial_obj.readline().decode("utf-8").strip()

                serial_obj.write(b"+")
                data_plus_inject = serial_obj.readline().decode("utf-8").strip()
                print(data_plus_inject)
                # toast(data_plus_inject)
                while True:
                    if data_plus_inject == "Inject Positif":
                        break
                    else:
                        serial_obj.write(b"+")
                        data_plus_inject = serial_obj.readline().decode("utf-8").strip()
            
        elif(inject_state == 2 or inject_state == 6 or inject_state == 10 or inject_state == 14 or inject_state == 18 or inject_state == 22 or inject_state == 26 or inject_state == 30 or inject_state == 34 or inject_state == 38):
            Clock.unschedule(self.measurement_sampling_event)

            if(not DEBUG):
                serial_obj.write(b"_")
                data_stop_inject = serial_obj.readline().decode("utf-8").strip()
                print(data_stop_inject)
                # toast(data_stop_inject)
                while True:
                    if data_stop_inject == "Not Injected":
                        break
                    else:
                        serial_obj.write(b"_")
                        data_stop_inject = serial_obj.readline().decode("utf-8").strip()
            
        elif(inject_state == 3 or inject_state == 7 or inject_state == 11 or inject_state == 15 or inject_state == 19 or inject_state == 23 or inject_state == 27 or inject_state == 31 or inject_state == 35 or inject_state == 39):
            Clock.schedule_interval(self.measurement_sampling_event, time_sampling)
            if(not DEBUG):
                serial_obj.write(b"-")
                data_negatif_inject = serial_obj.readline().decode("utf-8").strip()
                print(data_negatif_inject)
                toast(data_negatif_inject)
                while True:
                    if data_negatif_inject == "Inject Negatif":
                        break
                    else:
                        serial_obj.write(b"-")
                        data_negatif_inject = serial_obj.readline().decode("utf-8").strip()
        inject_state += 1
        
    def measurement_sampling_event(self, dt):
        # print("this is measurment sampling event at data screen")
        global dt_current
        global dt_voltage
        global serial_obj
        global flag_run

        # Data acquisition
        dt_voltage_temp = np.zeros_like(dt_voltage)
        dt_current_temp = np.zeros_like(dt_current)

        if(flag_run):
            if (not DEBUG):
                #try:
                serial_obj.write(b"a")
                data_current = serial_obj.readline().decode("utf-8").strip()  # read the incoming data and remove newline character
                while True:
                    if data_current[0] == "a":
                        curr = float(data_current[1:])
                        realtime_current = curr
                        
                        print("Realtime Curr:", realtime_current)
                        dt_current_temp[:1] = realtime_current
                        #time.sleep(0.5)
                        break
                    else:
                        serial_obj.write(b"a")
                        data_current = serial_obj.readline().decode("utf-8").strip()  # read the incoming data and remove newline character
                #except:
                    #toast("Error read Current")
                    #dt_current_temp[:1] = 0.0
                
                #try:
                serial_obj.write(b"v")
                data_millivoltage = serial_obj.readline().decode("utf-8").strip()  # read the incoming data and remove newline character
                #print(data_millivoltage)
                while True:
                    if data_millivoltage[0] == 'v':
                        millivolt = float(data_millivoltage[1:])
                        volt = millivolt / 1000
                        realtime_voltage = volt

                        print("Realtime Volt:", realtime_voltage)
                        dt_voltage_temp[:1] = realtime_voltage
                        #print(data_millivoltage)
                        break
                    else:
                        serial_obj.write(b"v")
                        data_millivoltage = serial_obj.readline().decode("utf-8").strip()
                #except:
                #   toast("Error read Voltage")
                #  dt_voltage_temp[:1] = 0.0

        dt_voltage_temp[1:] = dt_voltage[:-1]
        dt_voltage = dt_voltage_temp

        dt_current_temp[1:] = dt_current[:-1]
        dt_current = dt_current_temp

    def switching_commands(self):
        global step
        global max_step
        global serial_obj
        global arr_electrode

        try:
            serial_text = str(f"*{arr_electrode[0, step]},{arr_electrode[1, step]},{arr_electrode[2, step]},{arr_electrode[3, step]}")
            print(serial_text)
            serial_obj.write(serial_text.encode('utf-8'))
            validasi_patok = serial_obj.readline()#.decode("utf-8").strip()
            while True:
                print(validasi_patok)
                if  validasi_patok == 'Good':
                    break
                else :
                    serial_obj.write(serial_text.encode('utf-8'))
                    print(serial_text)
                    #time.sleep(0.1)
                    validasi_patok = serial_obj.readline().decode("utf-8").strip()
                    print(validasi_patok)
        except:
            pass
                   

    def reset_switching(self):
        try:
            serial_obj.write(b"%") # reset switching
            data_reset = serial_obj.readline().decode("utf-8").strip()  # read the incoming data and remove newline character
            while True:
                print(data_reset)
                if data_reset == "Semua decoder mati":
                    break
                else:
                    serial_obj.write(b"%") # reset switching
                    data_reset = serial_obj.readline().decode("utf-8").strip()
            
            serial_obj.write(b"_")
            data_stop_inject = serial_obj.readline().decode("utf-8").strip()
            while True:
                print(data_stop_inject)
                if data_stop_inject == "Not Injected":
                    break
                else:
                    serial_obj.write(b"_")
                    data_stop_inject = serial_obj.readline().decode("utf-8").strip()
        except:
            print("Error reset switching")

    def reset_data(self):
        global data_base
        global data_electrode
        global dt_measure
        global dt_current
        global dt_voltage
        global flag_run
        global serial_obj

        if(not flag_run):        
            toast("Resetting data")
            data_base = np.zeros([5, 0])
            data_electrode = np.zeros([4, 0], dtype=int)
            dt_measure = np.zeros(6)
            dt_current = np.zeros(10)
            dt_voltage = np.zeros(10)
            
            layout = self.ids.layout_tables
            
            self.data_tables = MDDataTable(
                use_pagination=True,
                pagination_menu_pos="auto",
                rows_num=4,
                column_data=[
                    ("No.", dp(10), self.sort_on_num),
                    ("Volt [V]", dp(27)),
                    ("Curr [mA]", dp(27)),
                    ("Resi [kOhm]", dp(27)),
                    ("Std Dev Res", dp(27)),
                    ("IP (R decay)", dp(27)),
                ],
            )
            layout.add_widget(self.data_tables)

        else:
            toast("Cannot reset data while measuring")
        

    def sort_on_num(self, data):
        try:
            return zip(
                *sorted(
                    enumerate(data),
                    key=lambda l: l[0][0]
                )
            )
        except:
            toast("Error sorting data")
            
    def save_data(self):
        global data_base
        global data_electrode
        global dt_distance
        global dt_config
        global data_pos
        global serial_obj

        if(not flag_run):
            try:
                if("WENNER (ALPHA)" in dt_config):
                    mode = 1
                    
                elif("WENNER (BETA)" in dt_config):
                    mode = 1
                    
                elif("WENNER (GAMMA)" in dt_config):
                    mode = 1
                    
                elif("POLE-POLE" in dt_config):
                    mode = 2
                    
                elif("DIPOLE-DIPOLE" in dt_config):
                    mode = 3
                    
                elif("SCHLUMBERGER" in dt_config):
                    mode = 7
                    
                toast("Saving data")

                x_loc = data_pos[0, :]
                # print(x_loc)

                data = data_base[2, :len(x_loc)]
                # print(data)

                spaces = data_pos[0, :] - data_pos[0, :-1]
                print(spaces)

                data_write = np.vstack((x_loc, spaces, data))
                if(data_write.size == 0):
                    data_write = np.array([[0,1,2,3]])
                print(data_write)

                now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.dat")
                disk = str(DISK_ADDRESS) + "\data\\" + now # for windows os
                head="%s \n%.2f \n%s \n%s \n0 \n1" % (now, dt_distance, mode, len(data_base.T[2]))
                foot="0 \n0 \n0 \n0 \n0"
                with open(disk,"wb") as f:
                    np.savetxt(f, data_write.T, fmt="%.3f", delimiter="\t", header=head, footer=foot, comments="")
                toast("Sucessfully save data to The Dongle")
            except:
                try:
                    now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.dat")
                    disk = os.getcwd() + "\data\\" + now #for windows os
                    head="%s \n%.2f \n%s \n%s \n0 \n1" % (now, dt_distance, mode, len(data_base.T[2]))
                    foot="0 \n0 \n0 \n0 \n0"
                    with open(disk,"wb") as f:
                        np.savetxt(f, data_write.T, fmt="%.3f", delimiter="\t", header=head, footer=foot, comments="")
                    # print("sucessfully save data to Default Directory")
                    toast("Sucessfully save data to The Default Directory")
                except:
                    print("Error save data")
                    # toast("Error saving data")
                
        else:
            toast("Cannot save data while measuring")

    def autosave_data(self):
        global data_base
        global data_electrode

        try:
            data_save = np.vstack((data_electrode, data_base))
            # print(data_save.T)

            now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.raw")
            disk = str(DISK_ADDRESS) + "\data\\" + now # for windows os
            with open(disk,"wb") as f:
                np.savetxt(f, data_save.T, fmt="%.3f",delimiter="\t",header="C1  \t P1  \t P2  \t C2  \t Volt [V] \t Curr [mA] \t Res [kOhm] \t StdDev \t IP [R decay]")
            # print("sucessfully auto save data to Dongle")
            toast("Sucessfully auto save data to The Dongle")
        except:
            try:
                now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.raw")
                cwd = os.getcwd()
                disk = cwd + "\data\\" + now #for windows os
                with open(disk,"wb") as f:
                    np.savetxt(f, data_save.T, fmt="%.3f",delimiter="\t",header="C1  \t P1  \t P2  \t C2  \t Volt [V] \t Curr [mA] \t Res [kOhm] \t StdDev \t IP [R decay]")
                # print("sucessfully auto save data to Default Directory")
                toast("Sucessfully save data to The Default Directory")
            except:
                print("Error auto save data")
                # toast("Error auto saving data")

    def measure(self):
        global flag_run
        global serial_obj
        if(flag_run):
            flag_run = False
        else:
            flag_run = True

    def screen_setting(self):
        self.screen_manager.current = 'screen_setting'

    def screen_data(self):
        self.screen_manager.current = 'screen_data'

    def screen_graph(self):
        self.screen_manager.current = 'screen_graph'

    def exec_shutdown(self):
        global flag_run

        if(not flag_run):        
            toast("Shutting down system")
            os.system("shutdown /s /t 1") #for windows os
            # os.system("shutdown -h now") #for linux os
        else:
            toast("Cannot shutting down while measuring")

class ScreenGraph(BoxLayout):
    screen_manager = ObjectProperty(None)
    global flag_run
    global serial_obj

    def __init__(self, **kwargs):
        super(ScreenGraph, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init, DELAY_INITIAL)

    def delayed_init(self, dt):
        Clock.schedule_interval(self.regular_check_event, UPDATE_INTERVAL_GRAPH)

        self.ids.bt_shutdown.md_bg_color = "#A50000"
        self.fig, self.ax = plt.subplots()
        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        l, b, w, h = self.ax.get_position().bounds
        self.ax.set_position(pos=[l, b + 0.3*h, w, h*0.7])
        
        self.ax.set_xlabel("distance [m]", fontsize=10)
        self.ax.set_ylabel("n", fontsize=10)

        self.ids.layout_graph.add_widget(FigureCanvasKivyAgg(self.fig))        

    def regular_check_event(self, dt):
        # print("this is regular check event at graph screen")
        global flag_run
        global flag_dongle
        global count_mounting
        global dt_time
        global data_base
        global flag_autosave_graph
        global graph_state
        global serial_obj

        if(graph_state > GRAPH_STATE_COUNT):
            graph_state = 0

        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"
            flag_autosave_graph = True
            if(graph_state == 0):
                self.update_graph()
            
        else:
            self.ids.bt_measure.text = "RUN MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#196BA5"
            if(flag_autosave_graph):
                self.autosave_graph()
                flag_autosave_graph = False

        graph_state += 1

        if not DISK_ADDRESS.exists() and flag_dongle:
            try:
                print("try mounting")
                serial_file = str(DISK_ADDRESS) + "\serial.key" #for windows os
                #  serial_file = str(DISK_ADDRESS) + "/serial.key" #for linux os 
                # print(serial_file)
                with open(serial_file,"r") as f:
                    serial_number = f.readline()
                    if serial_number == SERIAL_NUMBER:
                        toast("Success mounting The Dongle, the Serial number is valid")
                        self.ids.bt_save_graph.disabled = False
                    else:
                        toast("Failed mounting The Dongle, the Serial number is invalid")
                        self.ids.bt_save_graph.disabled = True                    
            except:
                toast("The Dongle could not be mounted")
                self.ids.bt_save_graph.disabled = True
                count_mounting += 1
                if(count_mounting > 2):
                    flag_dongle = False 

    def update_graph(self):
        global flag_run
        global x_datum
        global y_datum
        global data_base
        global data_pos

        data_limit = len(data_base[2,:])
        visualized_data_pos = data_pos

        try:
            self.fig.set_facecolor("#eeeeee")
            self.fig.tight_layout()
            
            self.ax.set_xlabel("distance [m]", fontsize=10)
            self.ax.set_ylabel("n", fontsize=10)
            self.ax.set_facecolor("#eeeeee")

            # datum location
            max_data = np.max(data_base[2,:data_limit])
            cmap, norm = mcolors.from_levels_and_colors([0.0, max_data, max_data * 2],['green','red'])
            self.ax.scatter(visualized_data_pos[0,:data_limit], -visualized_data_pos[1,:data_limit], c=data_base[2,:data_limit], cmap=cmap, norm=norm, label=l_electrode[0], marker='o')
            
            # electrode location
            self.ids.layout_graph.clear_widgets()
            self.ids.layout_graph.add_widget(FigureCanvasKivyAgg(self.fig))

            # print("successfully show graphic")
            toast("Successfully show graphic")
        
        except:
            print("Error show graphic")
            # toast("error show graphic")

        if(data_limit >= len(data_pos[0,:])):
            self.measure()

    def measure(self):
        global flag_run
        if(flag_run):
            flag_run = False
        else:
            flag_run = True

    def reset_graph(self):
        global data_base
        global data_pos
        global flag_run

        if(not flag_run):        
            toast("Resetting graph")
            data_base = np.zeros([5, 0])
            data_pos = np.zeros([2, 0])

            try:
                self.ids.layout_illustration.remove_widget(FigureCanvasKivyAgg(self.fig))
                self.ids.layout_graph.clear_widgets()
                self.fig, self.ax = plt.subplots()
                self.fig.set_facecolor("#eeeeee")
                self.fig.tight_layout()
                l, b, w, h = self.ax.get_position().bounds
                self.ax.set_position(pos=[l, b + 0.3*h, w, h*0.7])
                
                self.ax.set_xlabel("distance [m]", fontsize=10)
                self.ax.set_ylabel("n", fontsize=10)

                self.ids.layout_graph.add_widget(FigureCanvasKivyAgg(self.fig))        
                # print("successfully reset graphic")
                toast("Successfully reset graphic")
            
            except:
                # print("error reset graphic")
                toast("Error reset graphic")

        else:
            toast("Cannot reset graph while measuring")


    def save_graph(self):
        if(not flag_run):        
            toast("Saving graph")
            try:
                now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.jpg")
                disk = str(DISK_ADDRESS) + "\data\\" + now
                self.fig.savefig(disk)
                # print("sucessfully save graph to Dongle")
                toast("Sucessfully save graph to The Dongle")
            except:
                try:
                    now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.jpg")
                    disk = os.getcwd() + "\data\\" + now
                    self.fig.savefig(disk)
                    # print("sucessfully save graph to Default Directory")
                    toast("Sucessfully save graph to The Default Directory")
                except:
                    print("Error save graph")
                    # toast("Error save graph")
        else:
            toast("Cannot save graph while measuring")

    def autosave_graph(self):
        try:
            now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.jpg")
            disk = str(DISK_ADDRESS) + "\data\\" + now #for windows os
            self.fig.savefig(disk)
            # print("sucessfully auto save graph to Dongle")
            toast("Sucessfully auto save graph to The Dongle")
        except:
            try:
                now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.jpg")
                disk = os.getcwd() + "\data\\" + now #for windows os
                self.fig.savefig(disk)
                # print("sucessfully auto save graph to Default Directory")
                toast("Sucessfully auto save graph to The Default Directory")
            except:
                print("Error auto save graph")
                # toast("Error auto save graph")
                
    def screen_setting(self):
        self.screen_manager.current = 'screen_setting'

    def screen_data(self):
        self.screen_manager.current = 'screen_data'

    def screen_graph(self):
        self.screen_manager.current = 'screen_graph'

    def exec_shutdown(self):
        global flag_run

        if(not flag_run):        
            toast("Shutting down system")
            os.system("shutdown /s /t 1") #for windows os
            # os.system("shutdown -h now") #for linux os
        else:
            toast("Cannot shutting down while measuring")


class ResistivityMeterApp(MDApp):
    def build(self):
        self.theme_cls.colors = colors
        self.theme_cls.primary_palette = "Blue"
        self.icon = "asset\logo_labtek_p.ico" #for windows os
        Window.fullscreen = 'auto'
        Window.borderless = True
        # Window.size = 1024, 600
        Window.allow_screensaver = True

        screen = Builder.load_file("main.kv")
        return screen

if __name__ == "__main__":
    ResistivityMeterApp().run()
