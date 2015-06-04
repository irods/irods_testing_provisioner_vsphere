from __future__ import print_function

import sys
import time

import pyVim
import pyVim.connect
import pyVmomi
from pyVmomi import vim

import requests
requests.packages.urllib3.disable_warnings()

class VSphereError(RuntimeError):
    pass

class HandlerServiceInstance(object):
    def __init__(self, service_instance):
        self.service_instance = service_instance
    def __enter__(self):
        return self.service_instance
    def __exit__(self, exc_type, exc_val, exc_tb):
        pyVim.connect.Disconnect(self.service_instance)

class HandlerVmDestroyOnException(object):
    def __init__(self, vm):
        self.vm = vm
    def __enter__(self):
        return self.vm
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type is None:
            destroy_vm(self.vm)

def poweroff_vm(vm):
    if vm.summary.runtime.powerState == pyVmomi.vim.VirtualMachine.PowerState.poweredOn:
        vm.ShutdownGuest() # This is non-blocking
        start_ts = time.time()
        max_wait = 180
        while time.time() < start_ts + max_wait:
            if vm.summary.runtime.powerState != pyVmomi.vim.VirtualMachine.PowerState.poweredOn:
                break
            time.sleep(5)

    if vm.summary.runtime.powerState != pyVmomi.vim.VirtualMachine.PowerState.poweredOff:
        task_off = vm.PowerOff()
        wait_for_task(task_off, raise_on_fail=True, msg='Failed to power off VM')


def destroy_vm(vm):
    poweroff_vm(vm)
    task_destroy = vm.Destroy()
    wait_for_task(task_destroy, raise_on_fail=True, msg='Failed to destroy VM')

def wait_for_task(task, poll_period=2, raise_on_fail=False, msg=''):
    while True:
        task_state = task.info.state
        if task_state in [vim.TaskInfo.State.running, vim.TaskInfo.State.queued]:
            time.sleep(poll_period)
        else:
            break

    if raise_on_fail:
        if task_state != vim.TaskInfo.State.success:
            error_lines = []
            error_lines.append(msg)
            error_lines.append(task_state)
            error_lines.append(task.info.descriptionId)
            try:
                error_lines.append(task.info.description.message)
            except AttributeError:
                error_lines.append('task.info.description.message does not exist')
            try:
                error_lines.append(task.info.error.localizedMessage)
            except AttributeError:
                error_lines.append('task.info.error.localizedMessage does not exist')
            try:
                error_lines.append(task.info.error.fault)
            except AttributeError:
                error_lines.append('task.info.error.fault does not exist')

            error_str = '\n'.join(error_lines)
            raise VSphereError(error_str)
    return task_state == vim.TaskInfo.State.success

def get_obj(content, vimtype, name):
    obj = None
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj
