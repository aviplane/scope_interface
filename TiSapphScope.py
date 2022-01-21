import labscript_utils.h5_lock
from labscript_utils.ls_zprocess import ProcessTree

import h5py
process_tree = ProcessTree.instance()
process_tree.zlock_client.set_process_name("tisapph-scope")

from ScopeInterface import ScopeServer

class TiSapphScope(ScopeServer):

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
        self.interface.run()
        return True

    def transition_to_static(self, h5_filepath):
        """
        Read scope values, write to h5 file.
        """
        times, voltages = self.interface.get_all_voltages(self.channels, stop = False)
        # while True:
        #     try:
        with h5py.File(h5_filepath, 'a') as f:
            group = f['data']
            try:
                trace_group = f.create_group('ScopeTraces')
            except ValueError:
                trace_group = f['ScopeTraces']
                print("Group Already existed")
            for name, voltage in zip(self.names, voltages):
                trace_group.create_dataset('times' + name, data=times, dtype='float')
                trace_group.create_dataset(name, data=voltage, dtype='float')
port = 2627

if __name__ == '__main__':
    port = 2627
    kserver = TiSapphScope("DS1ZA203514731", port, "TiSapphScope")
    kserver.shutdown_on_interrupt()
