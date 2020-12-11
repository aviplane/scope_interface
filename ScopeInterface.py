
import pyvisa
import numpy as np
import time

class ScopeInterface:
    def __init__(self, identifying_string):
        self.resource_manager = pyvisa.ResourceManager()
        all_devices = resource_manager.list_resources()
        acceptable_devices = [i for i in all_devices if identifying_string in i]
        if acceptable_devices == []:
            raise Exception(
            f"Could not find device with identifying string {identifying_string}"
            + "Found devices:\n" + "\n".join(all_devices)
            )
        self.scope = rm.open_resource(acceptable_devices[0])
        self.n_channels = self.scope.query_ascii_values(":SYST:RAM?")[0]

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
            raise Exception(f"Channel must be between 1 and {self.n_channels}.")
        self.scope.write(":STOP")
        self.scope.write(f':WAV:SOUR CHAN{channel}')
        self.scope.write(':WAV:MODE norm')
        self.scope.write(':WAV:FORM byte')
        self.scope.write(":WAV:DATA?")
        data = self.scope.read_raw()
        _, _, wvf_points, _, xinc, xorigin, xref, yinc, yorigin, yref = self.scope.query_ascii_values(":WAV:PRE?")
        data = np.frombuffer(data, dtype = "uint8",offset = 12)
        data = (data - yref) * yinc - yorigin
        self.scope.write(":RUN")
        time_relative_trigger = np.arange(0, -wvf_points * xinc, -xinc) - xorigin
        return time_relative_trigger, data

    def set_timestep(self, timestep):
        """
        Set the scope timebase to timestep secs/division
        Input:
            timestep: float, secs/division
        """
        current_timestep = float(self.scope.query_ascii_values(":TIM:SCAL?")[0])
        if timestep != current_timestep:
            self.scope.write(f":TIM:SCAL {timestep}")
            time.sleep(0.1)

    def set_timeoffset(self, offset):
        """
        Set the scope horizontal offset relative to the trigger
        Input:
            offset: float, secs [Needs to be double checked]
        """
        current_offset = float(self.scope.query_ascii_values(":TIM:OFFS?")[0])
        if offset != current_offset:
            self.scope.write(f":TIM:OFFS {offset}")
            time.sleep(0.1)

class ScopeServer(DeviceServer):

    def __init__(self, scope_name):
        super().__init__(port)
        print("Starting Scope Server")
        self.name = scope_name
        self.interface = ScopeInterface(scope_name)

    def transition_to_buffered(self, h5_filepath):
        """
        Set timebase to correct values
        """
        with h5py.File(h5_filepath, 'r') as f:
            timestep = 0.001
            offset = 0
            self.interface.set_timestep(timestep)
            self.interface.set_timeoffset(offset)

    def transition_to_static(self, h5_filepath):
        """
        Read scope values, write to h5 file.
        """
        times, voltages = self.interface.get_voltage(1)

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
