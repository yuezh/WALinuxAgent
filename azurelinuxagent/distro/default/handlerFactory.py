# Windows Azure Linux Agent
#
# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.4+ and Openssl 1.0+
#
from azurelinuxagent.distro.default.init import InitHandler
from azurelinuxagent.distro.default.worker import WorkerHandler
from azurelinuxagent.distro.default.update import UpdateHandler
from azurelinuxagent.distro.default.scvmm import ScvmmHandler
from azurelinuxagent.distro.default.dhcp import DhcpHandler
from azurelinuxagent.distro.default.env import EnvHandler
from azurelinuxagent.distro.default.provision import ProvisionHandler
from azurelinuxagent.distro.default.resourceDisk import ResourceDiskHandler
from azurelinuxagent.distro.default.extension import ExtHandlersHandler
from azurelinuxagent.distro.default.deprovision import DeprovisionHandler

class DefaultHandlerFactory(object):
    def __init__(self):
        self.init_handler = InitHandler()
        self.worker_handler = WorkerHandler(self)
        self.update_handler = UpdateHandler(self)
        self.scvmm_handler = ScvmmHandler()
        self.dhcp_handler = DhcpHandler()
        self.env_handler = EnvHandler(self)
        self.provision_handler = ProvisionHandler()
        self.resource_disk_handler = ResourceDiskHandler()
        self.ext_handlers_handler = ExtHandlersHandler()
        self.deprovision_handler = DeprovisionHandler()

