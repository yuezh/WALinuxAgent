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
# Implements parts of RFC 2131, 1541, 1497 and
# http://msdn.microsoft.com/en-us/library/cc227282%28PROT.10%29.aspx
# http://msdn.microsoft.com/en-us/library/cc227259%28PROT.13%29.aspx

import tests.env
from tests.tools import AgentTestCase, patch, Mock, MagicMock
import uuid
import unittest
import os
import json
import time
import azurelinuxagent.distro.default.update as update
import azurelinuxagent.utils.osutil as osutil
from azurelinuxagent.utils.osutil import OSUTIL
import azurelinuxagent.protocol as prot
from azurelinuxagent.protocol.factory import PROT_FACTORY
from azurelinuxagent.metadata import AGENT_VERSION, PY_VERSION_MAJOR

HANDLERS = Mock()
HANDLERS.worker_handler = Mock()

class TestUpdateHandler(AgentTestCase):

    @patch("azurelinuxagent.utils.osutil")
    def test_run(self, *args):
        pid_file = os.path.join(self.tmp_dir, "waagent.pid")
        OSUTIL.get_agent_pid_file_path =MagicMock(return_value=pid_file)

        update_handler = update.UpdateHandler(HANDLERS)
        update_handler.handle_update = MagicMock()
        update_handler.run()
        update_handler.handle_update.assert_any_call()

    @patch("azurelinuxagent.protocol.v2")
    @patch("azurelinuxagent.protocol.factory")
    def test_no_available_pkgs(self, *args):
        protocol = Mock()
        PROT_FACTORY.get_protocol = MagicMock(return_value=protocol)
        manifests = prot.VMAgentManifestList()
        protocol.get_vmagent_manifests = MagicMock(return_value=manifests)
        pkgs = prot.ExtHandlerPackageList()
        protocol.get_vmagent_pkgs = MagicMock(return_value=pkgs)

        update_handler = update.UpdateHandler(HANDLERS)
        pkgs = update_handler.get_available_pkgs()
        self.assertEquals(0, len(pkgs))
        protocol.get_vmagent_manifests.assert_any_call()
        
    @patch("azurelinuxagent.protocol.v2")
    @patch("azurelinuxagent.protocol.factory")
    def test_get_available_pkgs(self, *args):
        protocol = Mock()
        PROT_FACTORY.get_protocol = MagicMock(return_value=protocol)
        manifest = prot.VMAgentManifest(family="Prod")
        manifests = prot.VMAgentManifestList()
        manifests.vmAgentManifests.append(manifest)
        protocol.get_vmagent_manifests = MagicMock(return_value=manifests)
        pkgs = prot.ExtHandlerPackageList()
        pkg1 = prot.ExtHandlerPackage(version="999.999.999")
        pkg2 = prot.ExtHandlerPackage(version="0.0.0")
        pkgs.versions.extend([pkg1, pkg2])
        protocol.get_vmagent_pkgs = MagicMock(return_value=pkgs)

        update_handler = update.UpdateHandler(HANDLERS)
        pkgs = update_handler.get_available_pkgs()
        self.assertNotEquals(None, pkgs)
        protocol.get_vmagent_manifests.assert_any_call()
        protocol.get_vmagent_pkgs.assert_any_call(manifest)

        #Any pkg that is newer with current version should be returned
        #In reversed order
        self.assertTrue(pkg1 in pkgs)
        self.assertEquals(pkg1, pkgs[0])
        self.assertFalse(pkg2 in pkgs)

    @patch("azurelinuxagent.distro.default.update")
    def test_update(self, *args):
        update_handler = update.UpdateHandler(HANDLERS) 
        old = update.AgentInstance(version="1.0.0")
        old.state = update.AgentInstance.Running
        old.start = MagicMock()
        old.stop = MagicMock()
        old.check_state = MagicMock()
        update_handler.instances.add(old)
        new = update.AgentInstance(version="1.0.1")
        new.start = MagicMock()
        new.stop = MagicMock()
        new.check_state = MagicMock()
        update_handler.instances.add(new)
        update_handler.instances.refresh([])

        update_handler.update()
        #Assert old instance is stopped and new instance started
        old.stop.assert_any_call()
        new.start.assert_any_call()
        new.check_state.assert_any_call()
        if PY_VERSION_MAJOR == 3:
            old.check_state.assert_not_called()
        
        old.state = None
        new.state = update.AgentInstance.Running

        update_handler.update()
        #Assert no update
        new.check_state.assert_any_call()
        if PY_VERSION_MAJOR == 3:
            old.stop.assert_not_called()
            old.check_state.assert_not_called()
            new.start.assert_not_called()

class TestAgentInstanceList(AgentTestCase):
    def test_list(self):
        instances = update.AgentInstanceList()
        instances.add(update.AgentInstance(version="1.0.1", 
                                           state=update.AgentInstance.Running))
        instances.add(update.AgentInstance(version="1.0.0"))
        self.assertTrue(instances.contains("1.0.0"))
        self.assertFalse(instances.contains("1.0.999"))
        self.assertNotEquals(None, instances.get("1.0.0"))
        self.assertEquals("1.0.0", instances.get("1.0.0").version)
        self.assertNotEquals(None, instances.get_latest())
        self.assertEquals("1.0.1", instances.get_latest().version)
        self.assertNotEquals(None, instances.get_running())
        self.assertEquals("1.0.1", instances.get_running().version)

    def test_load_and_save(self):
        instances = update.AgentInstanceList()
        instances.load_all()
        
        instances.add(update.AgentInstance(version="1.0.0"))
        instances.save_all()

        instances = update.AgentInstanceList()
        instances.load_all()
        self.assertEquals(2, len(instances.items))
        self.assertEquals("1.0.0", instances.items[0].version)

    def test_cleanup(self):
        instances = update.AgentInstanceList()
        instances.add(update.AgentInstance(version="1.0.1"))
        #Old pkg, should be removed
        instances.add(update.AgentInstance(version="1.0.0"))

        pkgs = prot.ExtHandlerPackageList()
        pkg1 = prot.ExtHandlerPackage(version="1.0.2")
        pkg2 = prot.ExtHandlerPackage(version="1.0.1")
        pkgs.versions.extend([pkg1, pkg2])

        instances.cleanup(pkgs.versions)

        self.assertEquals(1, len(instances.items))
        self.assertEquals("1.0.1", instances.items[0].version)


    def test_refresh(self):
        now = time.time()
        old = now - 2 * update.AgentInstanceList.retain_interval
        
        instances = update.AgentInstanceList()
        instances.add(update.AgentInstance(version="1.0.2", last_failure=now))
        #Failure happened long ago, should be cleared
        instances.add(update.AgentInstance(version="1.0.1", last_failure=old))

        pkgs = prot.ExtHandlerPackageList()
        pkg1 = prot.ExtHandlerPackage(version="1.0.2")
        pkg2 = prot.ExtHandlerPackage(version="1.0.1")
        pkgs.versions.extend([pkg1, pkg2])

        instances.refresh(pkgs.versions)

        self.assertEquals(2, len(instances.items))
        self.assertEquals("1.0.2", instances.items[0].version)
        self.assertEquals(now, instances.items[0].last_failure)

        self.assertEquals("1.0.1", instances.items[1].version)
        self.assertEquals(0, instances.items[1].last_failure)

if __name__ == '__main__':
    unittest.main()
