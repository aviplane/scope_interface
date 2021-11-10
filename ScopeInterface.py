import sys
sys.path.append("X:\\")
import labscript_utils.h5_lock
from labscript_utils.ls_zprocess import ProcessTree
import zprocess

import pyvisa
import numpy as np
import time
from device_server import DeviceServer
import h5py

process_tree = ProcessTree.instance()
process_tree.zlock_client.set_process_name("rigol-scope")

class ScopeInterface:
    def __init__(self, identifying_string):
        self.resource_manager = pyvisa.ResourceManager()
        all_devices = self.resource_manager.list_resources()
        acceptable_devices = [
            i for i in all_devices if identifying_string in i]
        if acceptable_devices == []:
            raise Exception(
                f"Could not find device with identifying string {identifying_string}"
                + "Found devices:\n" + "\n".join(all_devices)
            )
        self.scope = self.resource_manager.open_resource(acceptable_devices[0])
        self.n_channels = self.scope.query_ascii_values(":SYST:RAM?")[0]
        print(f'Connected to scope with {self.n_channels} channels')

    def get_voltage(self, channel):
        """
        Inputs:
            Channel - integer

        Outputs:
            time_relative_trigger - numpy array of time (in seconds) relative to
            the trigger pulse
            data - numpy array of voltage at each time
        """
        if channel > self.n_channels or channel < 1:
            raise Exception(
                f"Channel must be between 1 and {self.n_channels}.")
        self.scope.write(":STOP")
        self.scope.write(f':WAV:SOUR CHAN{channel}')
        self.scope.write(':WAV:MODE norm')
#        self.scope.write(":TRIG:EDGE:SWE NORM")
        self.scope.write(':WAV:FORM byte')
        self.scope.write(":WAV:DATA?")
        data = self.scope.read_raw()
        _, _, wvf_points, _, xinc, xorigin, xref, yinc, yorigin, yref = self.scope.query_ascii_values(
            ":WAV:PRE?")
        data = np.frombuffer(data, dtype="uint8", offset=12)
        data = (data - yref - yorigin) * yinc
        data = data[:-1]
        print(f"yref={yref},yinc={yinc},yorigin={yorigin}")
        self.scope.write(":RUN")
        print(f"wvf_points={wvf_points}")
        print(f"xinc={xinc}")
        #time_relative_trigger = np.arange(0, -wvf_points * xinc, -xinc) - xorigin
        time_relative_trigger = np.linspace(
            0, -(wvf_points - 1) * xinc, int(wvf_points)) - xorigin
        print(f"data shape = {data.shape}")
        return time_relative_trigger, data

    def get_all_voltages(self, channels):
        """
        Get the voltage trace on the screen of every channel

        Outputs:
            time - numpy array of times that data was taken
            datas - list of voltages, corresponding to channel 1..n
        """
        values = [self.get_voltage(i) for i in channels + 1]
        times, datas = zip(*values)
        return times[0][::-1], datas[::-1]

    def set_timestep(self, timestep):
        """
        Set the scope timebase to timestep secs/division

        Input:
            timestep: float, secs/division
        """
        current_timestep = float(
            self.scope.query_ascii_values(":TIM:SCAL?")[0])
        print(f"Setting timestep to {timestep}")
        print(f"Previous value was {current_timestep}")
        if timestep != current_timestep:
            self.scope.write(f":TIM:SCAL {timestep:f}")
            time.sleep(0.1)

    def set_timeoffset(self, offset):
        """
        Set the scope horizontal offset relative to the trigger
        Input:
            offset: float, secs [Needs to be double checked]
        """
        current_offset = float(self.scope.query_ascii_values(":TIM:OFFS?")[0])
        if offset != current_offset:
            self.scope.write(f":TIM:OFFS {offset:f}")
            time.sleep(0.1)
        print("Set time offset")


class ScopeServer(DeviceServer):

    def __init__(self, scope_name):
        super().__init__(port)
        print("Starting Scope Server")
        self.name = scope_name
        self.interface = ScopeInterface(scope_name)
        self.channels = (1)

    def transition_to_buffered(self, h5_filepath):
        """
        Set timebase to correct values
        """
        with h5py.File(h5_filepath, 'r') as f:
            timestep = f['/devices/RigolScope'].attrs['timestep']
            offset = f['/devices/RigolScope'].attrs['offset']
            self.channels = f['/devices/RigolScope'].attrs['channels']
            self.names = f['/devices/RigolScope'].attrs['names']
        self.interface.set_timestep(timestep)
        self.interface.set_timeoffset(offset)
        return True

    def transition_to_static(self, h5_filepath):
        """
        Read scope values, write to h5 file.
        """
        times, voltages = self.interface.get_all_voltages(self.channels)
        # while True:
        #     try:
        with h5py.File(h5_filepath, 'a') as f:
            group = f['data']
            trace_group = f.create_group('ScopeTraces')
            trace_group.create_dataset('times', data=times, dtype='float')
            for name, voltage in zip(self.names, voltages):
                trace_group.create_dataset(name, data=voltage, dtype='float')
            # except OSError:
            #     print("h5 file error")
            #     continue
            # break
    def abort(self):
        """To be overridden by subclasses. Return cameras and any other state
        to one in which transition_to_buffered() can be called again. abort()
        will be called if there was an exception in either
        transition_to_buffered() or transtition_to_static(), and so should
        ideally be written to return things to a sensible state even if those
        methods did not complete. Like any cleanup function, abort() should
        proceed to further cleanups even if earlier cleanups fail. As such it
        should make liberal use of try: except: blocks, so that an exception
        in performing one cleanup operation does not stop it from proceeding
        to subsequent cleanup operations"""
        print("abort")


port = 2625

kserver = ScopeServer("USB0::0x1AB1::0x04CE::DS1ZA205020654::INSTR")
kserver.shutdown_on_interrupt()
