import numpy as np
import kivy
import sys
import os
from kivymd.app import MDApp
from kivymd.uix.datatables import MDDataTable
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.animation import Animation
from kivymd.theming import ThemableBehavior
from kivy.clock import Clock
from kivy.config import Config
from kivy.metrics import dp
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
from matplotlib.ticker import AutoMinorLocator
from kivymd.uix.datatables import MDDataTable

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
}

from kivy.properties import ObjectProperty
import time

STEPS = 51
MAX_POINT = 5000
ELECTRODES_NUM = 48

x_datum = np.zeros(MAX_POINT)
y_datum = np.zeros(MAX_POINT)
x_electrode = np.zeros((4, MAX_POINT))
n_electrode = np.zeros((ELECTRODES_NUM, STEPS))
c_electrode = np.array(["#196BA5","#FF0000","#FFDD00","#00FF00","#00FFDD"])
l_electrode = np.array(["Datum","C1","C2","P1","P2"])

checks_mode = []
checks_config = []
dt_mode = ""
dt_config = ""
dt_distance = 1
dt_constant = 1
dt_time = 500
dt_cycle = 1

dt_measure = np.zeros(6)
flag_run = False

class ScreenSplash(BoxLayout):
# class ScreenSplash(Screen):
    screen_manager = ObjectProperty(None)
    screen_setting = ObjectProperty(None)
    app_window = ObjectProperty(None)
    
    def __init__(self, **kwargs):
        super(ScreenSplash, self).__init__(**kwargs)
        Clock.schedule_interval(self.update_progress_bar, .01)

    def update_progress_bar(self, *args):
        if (self.ids.progress_bar.value + 1) < 100:
            raw_value = self.ids.progress_bar_label.text.split('[')[-1]
            value = raw_value[:-2]
            value = eval(value.strip())
            new_value = value + 1
            self.ids.progress_bar.value = new_value
            self.ids.progress_bar_label.text = 'Loading.. [{:} %]'.format(new_value)
        else:
            self.ids.progress_bar.value = 100
            self.ids.progress_bar_label.text = 'Loading.. [{:} %]'.format(100)
            time.sleep(0.5)
            self.screen_manager.current = 'screen_setting'
            return False

class ScreenSetting(BoxLayout):
    screen_manager = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(ScreenSetting, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init)
        Clock.schedule_interval(self.regular_check, 1)

    def regular_check(self, dt):
        global flag_run
        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"
        else:
            self.ids.bt_measure.text = "RUN MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#196BA5"

    def delayed_init(self, dt):
        self.fig, self.ax = plt.subplots()
        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        l, b, w, h = self.ax.get_position().bounds
        self.ax.set_position(pos=[l, b + 0.3*h, w, h*0.7])
        
        self.ax.set_xlabel("distance (m)", fontsize=10)
        self.ax.set_ylabel("depth (m)", fontsize=10)

        self.ids.layout_illustration.add_widget(FigureCanvasKivyAgg(self.fig))

    def illustrate(self):
        global dt_mode
        global dt_config
        global dt_distance
        global dt_constant
        global dt_time
        global dt_cycle
        global x_datum
        global y_datum

        dt_distance = self.ids.slider_distance.value
        dt_constant = self.ids.slider_constant.value
        dt_time = self.ids.slider_time.value
        dt_cycle = int(self.ids.slider_cycle.value)

        self.fig, self.ax = plt.subplots()
        self.ids.layout_illustration.remove_widget(FigureCanvasKivyAgg(self.fig))
        x_datum = np.zeros(MAX_POINT)
        y_datum = np.zeros(MAX_POINT)

        if("WENNER" in dt_config):
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
                    # print("x:"+ str(x_datum[num_step]) + " y:"+ str(y_datum[num_step]))
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
                    # print("x:"+ str(x_datum[num_step]) + " y:"+ str(y_datum[num_step]))
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
            print(nmax_available)

            num_datum = 0
            count_datum = 0      
            for i in range(nmax_available):
                for j in range(ELECTRODES_NUM - 1 - i * 2):
                    num_datum = num_datum + j
                count_datum = count_datum + num_datum
                num_datum = 0     
            print(count_datum)

            num_step = 0
            num_trial = 0
            for i in range(nmax_available):
                for j in range(ELECTRODES_NUM - 1 - i * 2):
                    for k in range(ELECTRODES_NUM - i * 2 - j):
                        x_electrode[1, num_step] = j
                        x_electrode[0, num_step] = j + 1 + (i - 1)
                        x_electrode[2, num_step] = num_trial + x_electrode[0, num_step]
                        x_electrode[3, num_step] = i + x_electrode[2, num_step]
                        x_datum[num_step] = (x_electrode[0, num_step] + (x_electrode[2, num_step] - x_electrode[0, num_step])/2) * dt_distance
                        y_datum[num_step] = i * dt_distance
                        # print("x:"+ str(x_datum[num_step]) + " y:"+ str(y_datum[num_step]))
                        num_step += 1
                        num_trial += 1
                    num_trial = 0
        else:
            pass

        if("(SP) SELF POTENTIAL" in dt_mode):
            n_electrode[0, dt_cycle] = 0 #none
            n_electrode[1, dt_cycle] = 0 #none
            n_electrode[2, dt_cycle] = 3 #p1
            n_electrode[3, dt_cycle] = 4 #p2

        elif("(IP) INDUCED POLARIZATION" in dt_mode):
            n_electrode[0, dt_cycle] = 1 #c1
            n_electrode[1, dt_cycle] = 2 #c2
            n_electrode[2, dt_cycle] = 3 #p1
            n_electrode[3, dt_cycle] = 4 #p2

        elif("(R) RESISTIVITY" in dt_mode):
            n_electrode[0, dt_cycle] = 1 #c1
            n_electrode[1, dt_cycle] = 2 #c2
            n_electrode[2, dt_cycle] = 3 #p1
            n_electrode[3, dt_cycle] = 4 #p2

        elif("(R+IP) COMBINATION" in dt_mode):
            n_electrode[0, dt_cycle] = 1 #c1
            n_electrode[1, dt_cycle] = 2 #c2
            n_electrode[2, dt_cycle] = 3 #p1
            n_electrode[3, dt_cycle] = 4 #p2
            
        else:
            pass

        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        l, b, w, h = self.ax.get_position().bounds
        self.ax.set_position(pos=[l, b + 0.3*h, w*0.9, h*0.7])
        
        self.ax.set_xlabel("distance (m)", fontsize=10)
        self.ax.set_ylabel("depth (m)", fontsize=10)

        self.ax.set_facecolor("#eeeeee")
        # self.ax.scatter(x_datum, y_datum, c=c_electrode[0], label=l_electrode[0], marker='o')
        x_data = np.trim_zeros(x_datum)
        y_data = np.trim_zeros(y_datum)
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
        # print(n_electrode)

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
        os.system("shutdown /s /t 1")

class ScreenData(BoxLayout):
    screen_manager = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(ScreenData, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init)
        Clock.schedule_interval(self.regular_check, 1)

    def regular_check(self, dt):
        global flag_run
        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"
        else:
            self.ids.bt_measure.text = "RUN MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#196BA5"

    def delayed_init(self, dt):
        print("enter delayed init")
        layout = self.ids.layout_tables
        
        self.data_tables = MDDataTable(
            use_pagination=True,
            column_data=[
                ("No.", dp(30)),
                ("Voltage", dp(30)),
                ("Current", dp(30)),
                ("Resistivity", dp(30)),
                ("Std Dev Voltage", dp(30)),
                ("Std Dev Current", dp(30)),
            ],
            row_data=[(f"{i + 1}", "1", "2", "3", "4", "5") for i in range(5)]
        )
        layout.add_widget(self.data_tables)

    def save_data(self):
        self.data_tables.row_data=[(f"{i + 1}", "1", "2", "3", "4", "5") for i in range(5)]

    def measure(self):
        global flag_run
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
        os.system("shutdown /s /t 1")

class ScreenGraph(BoxLayout):
    screen_manager = ObjectProperty(None)
    global flag_run

    def __init__(self, **kwargs):
        super(ScreenGraph, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init)
        Clock.schedule_interval(self.regular_check, 1)

    def regular_check(self, dt):
        global flag_run
        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"
        else:
            self.ids.bt_measure.text = "RUN MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#196BA5"

    def delayed_init(self, dt):
        print("enter delayed init")
        
        self.fig, self.ax = plt.subplots()
        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        self.ax.grid(False)

        self.data_colormap = np.zeros((10, 100))
        
        clrmesh = self.ax.pcolor(self.data_colormap, cmap='seismic', vmin=-0.1, vmax=0.1)
        self.fig.colorbar(clrmesh, ax=self.ax, format='%f')

        self.ids.layout_graph.add_widget(FigureCanvasKivyAgg(self.fig))

    def measure(self):
        global flag_run
        if(flag_run):
            flag_run = False
        else:
            flag_run = True

    def save_graph(self):
        pass

    def screen_setting(self):
        self.screen_manager.current = 'screen_setting'

    def screen_data(self):
        self.screen_manager.current = 'screen_data'

    def screen_graph(self):
        self.screen_manager.current = 'screen_graph'

    def exec_shutdown(self):
        os.system("shutdown /s /t 1")

class ResistivityMeterApp(MDApp):
    def build(self):
        self.theme_cls.colors = colors
        self.theme_cls.primary_palette = "Blue"
        self.icon = 'asset/logo_labtek_p.ico'
        # Window.fullscreen = 'auto'
        Window.borderless = True
        Window.size = 1024, 600
        Window.allow_screensaver = True

        screen = Builder.load_file('main.kv')

        return screen


if __name__ == '__main__':
    ResistivityMeterApp().run()