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
import threading, os

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
        #self.scope.read_termination="\n"
        id = self.scope.query("*IDN?")
        self.n_channels = self.scope.query_ascii_values(":SYST:RAM?")[0]
        print(f'Connected to scope {id} with {self.n_channels} channels')

    def get_voltage(self, channel, stop = True):
        """
        Inputs:
            Channel - integer

        Outputs:
            time_relative_trigger - numpy array of time (in seconds) relative to
            the trigger pulse
            data - numpy array of voltage at each time
        """
        print("Channel", channel)
        if channel > self.n_channels or channel < 1:
            raise Exception(
                f"Channel must be between 1 and {self.n_channels}.")
        if stop:
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
        #time_relative_trigger = np.arange(0, -wvf_points * xinc, -xinc) - xorigin
        time_relative_trigger = np.linspace(
            0, (wvf_points - 1) * xinc, int(wvf_points)) - xorigin

        return time_relative_trigger[:-1], data

    def run(self):
        self.scope.write(":RUN")


    def get_all_voltages(self, channels, stop = True):
        """
        Get the voltage trace on the screen of every channel

        Outputs:
            time - numpy array of times that data was taken
            datas - list of voltages, corresponding to channel 1..n
        """
        channels = np.array(channels)
        values = [self.get_voltage(i, stop) for i in channels + 1]
        times, datas = zip(*values)
        return times[0], datas

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
            offset: float, secs
        """
        current_offset = float(self.scope.query_ascii_values(":TIM:OFFS?")[0])
        print(f"Setting offset to {offset}")
        print(f"Previous value was {current_offset}")
        if offset != current_offset:
            self.scope.write(f":TIM:OFFS {offset:f}")
            time.sleep(0.05)


class ScopeServer(DeviceServer):

    def __init__(self, scope_name, port, device_name):
        print(port)
        super().__init__(port)
        print("Starting Scope Server")
        self.name = scope_name
        self.interface = ScopeInterface(scope_name)
        self.channels = (1)
        self.device_name = device_name

    def transition_to_buffered(self, h5_filepath):
        """
        Set timebase to correct values
        """
        with h5py.File(h5_filepath, 'r') as f:
            dset = f'/devices/{self.device_name}'
            parameters = f[dset].attrs
            timestep = parameters['timestep']
            offset = parameters['offset']
            self.channels = parameters['channels']
            self.names = parameters['names']
        self.interface.set_timestep(timestep)
        self.interface.set_timeoffset(offset)
        self.interface.run()
        return True

    def write_voltages(self, h5_filepath):
        times, voltages = self.interface.get_all_voltages(np.array(self.channels))
        head, tail = os.path.split(labscript_utils.shared_drive.path_to_local(h5_filepath))
        number = tail.split('_')[-1][:-3]
        print(f'{head}')
        for name, voltage in zip(self.names, voltages):
            print(f'{head}/RIGOL{name}_{number}.npy')
            np.save(f'{head}/RIGOL{name}_{number}.npy', voltage)
            np.save(f'{head}/RIGOLtimes{name}_{number}.npy', times)


    def transition_to_static(self, h5_filepath):
        """
        Read scope values, write to h5 file.
        """
        save_thread = threading.Thread(target=self.write_voltages, args=(h5_filepath,))
        save_thread.start()
        print(self.channels, self.names)
        # times, voltages = self.interface.get_all_voltages(np.array(self.channels))
        # print(voltages)
        # # while True:
        # #     try:
        # with h5py.File(h5_filepath, 'a') as f:
        #     group = f['data']
        #     try:
        #         trace_group = f.create_group('ScopeTraces')
        #     except ValueError:
        #         trace_group = f['ScopeTraces']
        #         print("Group Already existed")
        #     for name, voltage in zip(self.names, voltages):
        #         trace_group.create_dataset('times' + name, data=times, dtype='float')
        #         trace_group.create_dataset(name, data=voltage, dtype='float')

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

if __name__ == '__main__':
    port = 2625

    kserver = ScopeServer("USB0::0x1AB1::0x04CE::DS1ZA205020654::INSTR", port, "RigolScope")
    kserver.shutdown_on_interrupt()
