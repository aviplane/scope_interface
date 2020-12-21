# -*- coding: utf-8 -*-
"""
Created on Thu Oct 04 17:53:55 2018

@author: Quantum Engineer
"""

import sys
import time
import zprocess
import h5py
import numpy as np
import matplotlib.pyplot as plt
import os


class DeviceServer(zprocess.ZMQServer):
    def __init__(self, port):
        zprocess.ZMQServer.__init__(self, port, type="string")
        self._h5_filepath = None
        return

    def handler(self, request_data):
        try:
            print(request_data)
            if request_data == "hello":
                return "hello"
            elif request_data.endswith(".h5"):
                self._h5_filepath = request_data
                self.send("ok")
                self.recv()
                self.transition_to_buffered(self._h5_filepath)
                return "done"
            elif request_data == "done":
                self.send("ok")
                self.recv()
                self.transition_to_static(self._h5_filepath)
                self._h5_filepath = None
                return "done"
            elif request_data == "abort":
                self.abort()
                self._h5_filepath = None
                return "done"
            else:
                raise ValueError("invalid request: %s" % request_data)
        except Exception:
            if self._h5_filepath is not None and request_data != "abort":
                try:
                    self.abort()
                except Exception as e:
                    sys.stderr.write(
                        "Exception in self.abort() while handling another exception:\n{}\n".format(
                            str(e)
                        )
                    )
            self._h5_filepath = None
            raise

    def transition_to_buffered(self, h5_filepath):
        """To be overridden by subclasses. Do any preparatory processing
        before a shot, eg setting exposure times, readying cameras to receive
        triggers etc."""
        print("transition to buffered")

    def transition_to_static(self, h5_filepath):
        """To be overridden by subclasses. Do any post processing after a
        shot, eg computing optical depth, fits, displaying images, saving
        images and results to the h5 file, returning cameras to an idle
        state."""
        print("transition to static")

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
