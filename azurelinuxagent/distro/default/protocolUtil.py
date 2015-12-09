# Microsoft Azure Linux Agent
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
import re
import shutil
import time
import threading
import azurelinuxagent.conf as conf
import azurelinuxagent.logger as logger
from azurelinuxagent.exception import ProtocolError, OSUtilError, \
                                      ProtocolNotFoundError
from azurelinuxagent.future import text
import azurelinuxagent.utils.fileutil as fileutil
from azurelinuxagent.protocol.ovfenv import OvfEnv
from azurelinuxagent.protocol.wire import WireProtocol
from azurelinuxagent.protocol.metadata import MetadataProtocol

OVF_FILE_NAME = "ovf-env.xml"

#Tag file to indicate usage of metadata protocol
TAG_FILE_NAME = "useMetadataEndpoint.tag" 

PROTOCOL_FILE_NAME = "Protocol"

#MAX retry times for protocol probing
MAX_RETRY = 60

PROBE_INTERVAL = 10

ENDPOINT_FILE_NAME = "WireServerEndpoint"

class ProtocolUtil(object):
    """
    ProtocolUtil handles initialization for protocol instance. 2 protocol types 
    are invoked, wire protocol and metadata protocols.
    """
    def __init__(self, distro):
        self.distro = distro
        self.protocol = None
        self.lock = threading.Lock()

    def copy_ovf_env(self):
        """
        Copy ovf env file from dvd to hard disk.
        Remove password before save it to the disk
        """
        dvd_mount_point = self.distro.osutil.get_dvd_mount_point()
        ovf_file_path_on_dvd = self.distro.osutil.get_ovf_env_file_path_on_dvd()
        tag_file_path_on_dvd = os.path.join(dvd_mount_point, TAG_FILE_NAME)
        try:
            self.distro.osutil.mount_dvd()
            ovfxml = fileutil.read_file(ovf_file_path_on_dvd, remove_bom=True)
            ovfenv = OvfEnv(ovfxml)
            ovfxml = re.sub("<UserPassword>.*?<", "<UserPassword>*<", ovfxml)
            ovf_file_path = os.path.join(conf.get_lib_dir(), OVF_FILE_NAME)
            fileutil.write_file(ovf_file_path, ovfxml)
            
            if os.path.isfile(tag_file_path_on_dvd):
                logger.info("Found {0} in provisioning ISO", TAG_FILE_NAME)
                tag_file_path = os.path.join(conf.get_lib_dir(), TAG_FILE_NAME)
                shutil.copyfile(tag_file_path_on_dvd, tag_file_path) 

        except (OSUtilError, IOError) as e:
            raise ProtocolError(text(e))

        try:
            self.distro.osutil.umount_dvd()
            self.distro.osutil.eject_dvd()
        except OSUtilError as e:
            logger.warn(text(e))

        return ovfenv

    def get_ovf_env(self):
        """
        Load saved ovf-env.xml
        """
        ovf_file_path = os.path.join(conf.get_lib_dir(), OVF_FILE_NAME)
        if os.path.isfile(ovf_file_path):
            xml_text = fileutil.read_file(ovf_file_path)
            return OvfEnv(xml_text)
        else:
            raise ProtocolError("ovf-env.xml is missing.")

    def _get_wireserver_endpoint(self):
        try:
            file_path = os.path.join(conf.get_lib_dir(), ENDPOINT_FILE_NAME)
            return fileutil.read_file(file_path)
        except IOError as e:
            raise OSUtilError(text(e))

    def _set_wireserver_endpoint(self, endpoint):
        try:
            file_path = os.path.join(conf.get_lib_dir(), ENDPOINT_FILE_NAME)
            fileutil.write_file(file_path, endpoint)
        except IOError as e:
            raise OSUtilError(text(e))
   
    def _detect_wire_protocol(self):
        endpoint = self.distro.dhcp_handler.endpoint
        if endpoint is None:
            logger.info("WireServer endpoint is not found. Rerun dhcp handler")
            self.distro.dhcp_handler.run()
            endpoint = self.distro.dhcp_handler.endpoint
        
        try:
            protocol = WireProtocol(self.distro.osutil, endpoint)
            protocol.detect()
            self._set_wireserver_endpoint(endpoint)
            return protocol
        except ProtocolError as e:
            logger.info("WireServer is not responding. Rerun dhcp handler")
            self.distro.dhcp_handler.run()
            raise e

    def _detect_metadata_protocol(self):
        protocol = MetadataProtocol(self.distro.osutil)
        protocol.detect()
        return protocol
            
    def _detect_protocol(self, protocols):
        """
        Probe protocol endpoints in turn.
        """
        protocol_file_path = os.path.join(conf.get_lib_dir(), PROTOCOL_FILE_NAME)
        if os.path.isfile(protocol_file_path):
            os.remove(protocol_file_path)
        for retry in range(0, MAX_RETRY):
            for protocol in protocols:
                try:
                    if protocol == WireProtocol.__name__:
                        return self._detect_wire_protocol()

                    if protocol == MetadataProtocol.__name__:
                        return self._detect_metadata_protocol

                except ProtocolError as e:
                    logger.info("Protocol endpoint not found: {0}, {1}", 
                                protocol, e)

            if retry < MAX_RETRY -1:
                logger.info("Retry detect protocols: retry={0}", retry)
                time.sleep(PROBE_INTERVAL)
        raise ProtocolNotFoundError("No protocol found.")

    def _get_protocol(self):
        """
        Get protocol instance based on previous detecting result.
        """
        protocol_file_path = os.path.join(conf.get_lib_dir(), 
                                          PROTOCOL_FILE_NAME)
        if not os.path.isfile(protocol_file_path):
            raise ProtocolError("No protocl found")

        protocol_name = fileutil.read_file(protocol_file_path)
        if protocol_name == WireProtocol.__name__:
            endpoint = self._get_wireserver_endpoint()
            return WireProtocol(self.distro.osutil, endpoint)
        elif protocol_name == MetadataProtocol.__name__:
            return MetadataProtocol(self.distro.osutil)
        else:
            raise ProtocolNotFoundError(("Unknown protocol: {0}"
                                         "").format(protocol_name))

    def detect_protocol(self):
        """
        Detect protocol by endpoints

        :returns: protocol instance
        """
        logger.info("Detect protocol endpoints")
        protocols = [WireProtocol.__name__, MetadataProtocol.__name__]
        self.lock.acquire()
        try:
            if self.protocol is None:
                self.protocol = self._detect_protocol(protocols)
            return self.protocol
        finally:
            self.lock.release()

    def detect_protocol_by_file(self):
        """
        Detect protocol by tag file. 

        If a file "useMetadataEndpoint.tag" is found on provision iso, 
        metedata protocol will be used. No need to probe for wire protocol

        :returns: protocol instance
        """
        logger.info("Detect protocol by file")
        self.lock.acquire()
        try:
            tag_file_path = os.path.join(self.distro.conf.get_lib_dir(), 
                                         TAG_FILE_NAME)
            if self.protocol is None:
                protocols = []
                if os.path.isfile(tag_file_path):
                    protocols.append(MetadataProtocol.__name__)
                else:
                    protocols.append(WireProtocol.__name__)
                self.protocol = self._detect_protocol(protocols)
        finally:
            self.lock.release()
        return self.protocol

    def get_protocol(self):
        """
        Get protocol instance based on previous detecting result.

        :returns protocol instance
        """
        self.lock.acquire()
        try:
            if self.protocol is None:
                self.protocol = self._get_protocol()        
            return self.protocol
        finally:
            self.lock.release()
        return self.protocol

