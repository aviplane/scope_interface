import labscript_utils.h5_lock
from labscript_utils.ls_zprocess import ProcessTree

process_tree = ProcessTree.instance()
process_tree.zlock_client.set_process_name("probe-error-scope")

from ScopeInterface import ScopeServer

port = 2626

kserver = ScopeServer("DS1ZA205020656", port, "ProbeErrorScope")
kserver.shutdown_on_interrupt()
