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
import os
import json
import time
import subprocess
import signal
import sys
import zipfile
from azurelinuxagent.exception import UpdateError
import azurelinuxagent.logger as logger
import azurelinuxagent.conf as conf
from azurelinuxagent.event import add_event
from azurelinuxagent.future import text
import azurelinuxagent.utils.fileutil as fileutil
import azurelinuxagent.utils.restutil as restutil
from azurelinuxagent.utils.osutil import OSUTIL
import azurelinuxagent.protocol as prot
from azurelinuxagent.metadata import AGENT_VERSION
from azurelinuxagent.utils.textutil import Version

CHECK_UPDATE_INTERVAL = 25 #Interval between checking update

"""
Handles self update logic
"""
class UpdateHandler(object):

    def __init__(self, handlers):
        self.handlers = handlers
        self.instances = AgentInstanceList()

    def run(self):
        """
        - If self-update is enabled, check for new version and fork 
          a new process to run new version.
        - Otherwise, call worker_handler.run dirrectly
        """
        fileutil.write_file(OSUTIL.get_agent_pid_file_path(), text(os.getpid()))
        self.handlers.worker_handler.probe_env()

        if conf.get_switch("AutoUpdate.Enabled", True):
            self.handle_update()
        else:
            self.handlers.worker_handler.run()

    def handle_update(self):
        while True:
            try:
                self.instances.load_all()
                pkgs = self.get_available_pkgs()
                self.instances.refresh(pkgs)
                self.update()
                self.instances.cleanup(pkgs)
                self.instances.save_all()
            except UpdateError as e:
                add_event("WALA", is_success=False, message=text(e))
            time.sleep(CHECK_UPDATE_INTERVAL)

    def update(self):
        target = self.instances.get_latest()
        current = self.instances.get_running()
       
        if current is not None and target.version > current.version:
            logger.info("Stop current agent: {0}", current.version)
            current.stop()

        if current is None or target.version > current.version:
            logger.info("Start new agent: {0}", target.version)
            target.start()
            current = target

        current.check_state()

    def get_available_pkgs(self):
        try:
            protocol = prot.FACTORY.get_default_protocol()
            manifest_list = protocol.get_vmagent_manifests()
        except prot.ProtocolError as e:
            add_event("WALA", is_success=False, message=text(e))
            return []

        family = conf.get("AutoUpdate.GAFamily", "PROD")
        manifests = [manifest for manifest in manifest_list.vmAgentManifests \
                     if manifest.family == family]
        if len(manifests) == 0:
            logger.warn("GAFamily not found:{0}", family)
            return []

        try:
            pkg_list = protocol.get_vmagent_pkgs(manifests[0])
        except prot.ProtocolError as e:
            add_event("WALA", is_success=False, message=text(e))
            return []
        
        #Only considering versions that is larger than current
        pkgs = [pkg for pkg in pkg_list.versions \
                if Version(pkg.version) > Version(AGENT_VERSION)]
        
        return pkgs

AGENT_INSTANCES_DIR = 'agent' #file name for agent instance state
MAX_FAILURE = 3 # Max failure allowed for agent

"""
Maintain a list of agent instance
"""
class AgentInstanceList(object):

    retain_interval = 24 * 60 * 60
    
    def __init__(self):
        self.items = []

    def _get_first(self, select):
        result = [item for item in self.items if select(item)]
        return result[0] if len(result) > 0 else None

    def get(self, version):
        return self._get_first(lambda item: item.version == version)

    def add(self, item):
        self.items.append(item)

    def contains(self, version):
        return self.get(version) is not None

    def get_latest(self):
        return self._get_first(lambda item: not item.is_blacklisted())

    def get_running(self):
        return self._get_first(lambda item: item.is_running())
    
    def refresh(self, agent_pkgs):
        """
        Rebuild the list
        1. Update agent instances list according to the latest agent versions
        2. Clear failure_count and last_failure for those exceeds retaining time
        3. Add default agent instance, if necessary
        4. Sort item by version
        """
        
        #Create new instance for new version if neccesaary
        for pkg in agent_pkgs:
            item = self.get(pkg.version)
            if item is None:
                item = AgentInstance(version=pkg.version)
                self.add(item)
            item.pkg = pkg

        threshold = time.time() - self.__class__.retain_interval
        for item in self.items:
            if item.last_failure < threshold:
                item.clear_failure()
       
        self.items = sorted(self.items, key=lambda item: Version(item.version),
                            reverse=True)

        if not self.contains(AGENT_VERSION):
            self.add(DefaultAgentInstance())


    def cleanup(self, agent_pkgs) :
        """
        Clean up old agent versions that are no longer available. 
        Should not clean the agent version if it is running
        """
        versions_to_keep = set([pkg.version for pkg in agent_pkgs])
        versions_to_keep.add(AGENT_VERSION)

        for item in self.items:
            if not item.version in versions_to_keep and \
                    item.state is not AgentInstance.Running:
                item.cleanup()
                self.items.remove(item)

    def load_all(self):
        instances_dir = os.path.join(OSUTIL.get_lib_dir(), AGENT_INSTANCES_DIR)
        fileutil.mkdir(instances_dir)
        for data_file in os.listdir(instances_dir):
            try: 
                instance = AgentInstance()
                instance.load(data_file)
                self.add(instance)
            except UpdateError as e:
                add_event(name=u"WALA", is_success=False, message=text(e))

    def save_all(self):
        for item in self.items:
            try:
                item.save()
            except UpdateError as e:
                add_event(name=u"WALA", is_success=False, message=text(e))


"""
Agent instance properties, including:
    1. Version
    2. Agent pid, if agent is running
    3. Agent failure count
    4. Agent last failure time
    5. State: Starting, Running, Stopped
"""
class AgentInstance(object):
    
    Downloaded = "Downloaded"
    Running = "Running"

    def __init__(self, version=None, last_failure=0, failure_count=0, pid=None,
                 state=None, pkg=None):
        self.version = version
        self.last_failure = last_failure
        self.failure_count = failure_count
        self.pid = pid
        self.state = state
        self.pkg = pkg

    def get_state_file(self):
        return os.path.join(OSUTIL.get_lib_dir(), AGENT_INSTANCES_DIR, 
                            self.version)

    def get_base_dir(self):
        return os.path.join(OSUTIL.get_update_path(), self.version)
    
    def get_egg_file(self):
        file_name = "WAAgent-{0}.egg".format(self.version)
        return os.path.join(self.get_base_dir(), file_name)
    

    def load(self, file_name):
        file_name =  os.path.join(OSUTIL.get_lib_dir(), AGENT_INSTANCES_DIR, 
                                  file_name)
        try:
            data = json.loads(fileutil.read_file(file_name))
            self.version = data.get(u"version")
            self.last_failure = data.get(u"last_failure", 0)
            self.failure_count = data.get(u"failure_count", 0)
            self.pid = data.get(u"pid")
            self.state = data.get(u"state")
        except (IOError, ValueError) as e:
            err = u"Failed to load agent state file: {0}".format(e)
            raise UpdateError(err)

    def save(self):
        data = {
            u"version": self.version,
            u"last_failure": self.last_failure,
            u"failure_count": self.failure_count,
            u"pid": self.pid,
            u"state": self.state
        }
            
        try:
            fileutil.write_file(self.get_state_file(), json.dumps(data)) 
        except (IOError, ValueError) as e:
            err = u"Failed to save agent state file: {0}".format(e)
            raise UpdateError(err)

    def mark_failure(self):
        self.state = None
        self.pid = None
        self.last_failure = time.time()
        self.failure_count += 1

    def clear_failure(self):
        self.last_failure = 0
        self.failure_count = 0

    def is_blacklisted(self):
        return self.last_failure >= MAX_FAILURE

    def is_running(self):
        return self.state == AgentInstance.Running

    def download(self):
        logger.info("Download agent package")
        package = None
        for uri in self.pkg.uris:
            try:
                resp = restutil.http_get(uri.uri, chk_proxy=True)
                if resp.status == restutil.httpclient.OK:
                    package = resp.read()
                    break
            except restutil.HttpError as e:
                logger.warn("Failed download agent from: {0}", uri.uri)

        if package is None:
            raise UpdateError("Failed to download agent package")
        
        fileutil.mkdir(OSUTIL.get_update_path(), 0o700)

        logger.info("Unpack agent package")
        pkg_file = os.path.join(OSUTIL.get_lib_dir(), 
                                "WAAgent-{0}.zip".format(self.version))
        fileutil.write_file(pkg_file, bytearray(package), asbin=True)
        zipfile.ZipFile(pkg_file).extractall(self.get_base_dir())

        add_event(name="WALA", message="Download succeeded")
        self.state = AgentInstance.Downloaded
        self.save()

    def launch_agent(self, args):
        logger.info("Launch agent")
        try:
            devnull = open(os.devnull, 'w')
            child = subprocess.Popen(args, stdout=devnull)
            self.pid = child.pid
            self.state = AgentInstance.Running
            self.save()
        except (ValueError, OSError, IOError) as e:
            self.mark_failure()
            self.save()
            raise UpdateError("Failed to launch agent:{0}".format(e))

    def start(self):
        if self.state == AgentInstance.Running:
            raise UpdateError("Shouldn't start a running agent")

        if self.start == AgentInstance.Downloaded:
            if os.path.isfile(self.get_egg_file()):
                logger.info("Egg file not found, reset state to None")
                self.state = None

        if self.start != AgentInstance.Downloaded:
            self.download()

        args = [self.get_egg_file(), "-worker"]
        self.launch_agent(args)

    def stop(self):
        if self.pid is None or self.state != AgentInstance.Running:
            raise UpdateError("Shouldn't stop agent that is not running")

        try:
            os.kill(self.pid, signal.SIGKILL)
        except (ValueError, OSError) as e:
            raise UpdateError("Failed to stop agent:{0}".format(e))

        self.pid = None
        self.state = AgentInstance.Downloaded
        self.save()

    def cleanup(self):
        if self.state == AgentInstance.Running:
            raise UpdateError("Shouldn't cleanup agent that is running")
        
        try:
            fileutil.rm_dirs(self.get_base_dir())
            fileutil.rm_files(self.get_state_file())
        except IOError as e:
            raise UpdateError("Failed to cleanup agent dir: {0}".format(e))

    def check_state(self):
        if self.pid is None or self.state != AgentInstance.Running:
            raise UpdateError("Shouldn't check state of a agent not running")
        
        if OSUTIL.pid_exits(self.pid):
            logger.verb("Agent is running, pid: {0}", self.pid)
        else:
            logger.error("Agent failed to run: pid: {0}", self.pid)
            self.mark_failure()
            self.save()

"""
Default agent instance that will be always available.
"""
class DefaultAgentInstance(AgentInstance):
    def __init__(self, *args, **kwargs):
        kwargs["version"] = AGENT_VERSION
        super(DefaultAgentInstance, self).__init__(*args, **kwargs)

    def is_blacklisted(self):
        """
        The default agent will not be blacklisted.
        """
        return False

    def start(self):
        """
        Launch default agent. No need to download
        """
        if self.state == AgentInstance.Running:
            raise UpdateError("Shouldn't start a running agent")

        args = [sys.argv[0], "-worker"]
        self.launch_agent(args)

    def cleanup(self):
        pass #Do nothing

