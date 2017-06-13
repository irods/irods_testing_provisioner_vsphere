from __future__ import print_function

import ssl
import sys
import time

import pyVim
import pyVim.connect
import pyVmomi
from pyVmomi import vim

import requests
requests.packages.urllib3.disable_warnings()

import pyvmomi_helper
import configuration


def deploy_vm_return_ip(vm_name, template_identifier):
    template_name = configuration.template_identifier_dict[template_identifier]

    with open(configuration.vsphere_password_file) as f:
        vsphere_password = f.read().rstrip('\n')

    with pyvmomi_helper.HandlerServiceInstance(pyVim.connect.SmartConnect(host=configuration.vsphere_host,
                                                                       user=configuration.vsphere_username,
                                                                       pwd=vsphere_password,
                                                                       sslContext=ssl._create_unverified_context())) as si:

        content = si.RetrieveContent()

        dest_folder = pyvmomi_helper.get_obj(content, [vim.Folder], configuration.vsphere_deployment_folder)

        reloc_spec = vim.vm.RelocateSpec()
        reloc_spec.datastore = pyvmomi_helper.get_obj(content, [vim.Datastore], configuration.vsphere_datastore)
        cluster = pyvmomi_helper.get_obj(content, [vim.ClusterComputeResource], configuration.vsphere_cluster)
        reloc_spec.pool = cluster.resourcePool

        vm_config = vim.vm.ConfigSpec()
        vm_config.numCPUs = configuration.vm_cpu_count
        vm_config.memoryMB = configuration.vm_memory_MB

        clone_spec = vim.vm.CloneSpec()
        clone_spec.location = reloc_spec
        clone_spec.config = vm_config
        clone_spec.template = False

        template_vm = pyvmomi_helper.get_obj(content, [pyVmomi.vim.VirtualMachine], template_name)
        task_clone = template_vm.Clone(folder=dest_folder, name=vm_name, spec=clone_spec)
        pyvmomi_helper.wait_for_task(task_clone, raise_on_fail=True, msg='Failed to clone VM from template')

        with pyvmomi_helper.HandlerVmDestroyOnException(task_clone.info.result) as new_vm:
            task_on = new_vm.PowerOn()
            pyvmomi_helper.wait_for_task(task_on, raise_on_fail=True, msg='Failed to power on VM')

            ip_address_wait_start = time.time()
            while not new_vm.summary.guest.ipAddress:
                if time.time() > ip_address_wait_start + 300:
                    error_str = 'Guest OS has not reported IP address within 300 seconds. Assuming failure.'
                    print(error_str, file=sys.stderr)
                    raise pyvmomi_helper.VSphereError(error_str)
                time.sleep(2)

            return new_vm.summary.guest.ipAddress

def destroy_vm(vm_name):
    with open(configuration.vsphere_password_file) as f:
        vsphere_password = f.read().rstrip('\n')

    with pyvmomi_helper.HandlerServiceInstance(pyVim.connect.SmartConnect(host=configuration.vsphere_host,
                                                                       user=configuration.vsphere_username,
                                                                       pwd=vsphere_password,
                                                                       sslContext=ssl._create_unverified_context())) as si:

        content = si.RetrieveContent()
        pyvmomi_helper.destroy_vm(pyvmomi_helper.get_obj(content, [pyVmomi.vim.VirtualMachine], vm_name))
