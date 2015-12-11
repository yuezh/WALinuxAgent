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
"""
Defines all exceptions
"""

class AgentError(Exception):
    """
    Base class of agent error.
    """
    def __init__(self, errno, msg):
        msg = "({0}){1}".format(errno, msg)
        super(AgentError, self).__init__(msg)

class AgentConfigError(AgentError):
    """
    When configure file is not found or malformed.
    """
    def __init__(self, msg=None):
        super(AgentConfigError, self).__init__('000001', msg)

class AgentNetworkError(AgentError):
    """
    When network is not avaiable.
    """
    def __init__(self, msg=None):
        super(AgentNetworkError, self).__init__('000002', msg)

class ExtensionError(AgentError):
    """
    When failed to execute an extension
    """
    def __init__(self, msg=None):
        super(ExtensionError, self).__init__('000003', msg)

class ProvisionError(AgentError):
    """
    When provision failed
    """
    def __init__(self, msg=None):
        super(ProvisionError, self).__init__('000004', msg)

class ResourceDiskError(AgentError):
    """
    Mount resource disk failed
    """
    def __init__(self, msg=None):
        super(ResourceDiskError, self).__init__('000005', msg)

class DhcpError(AgentError):
    """
    Failed to handle dhcp response
    """
    def __init__(self, msg=None):
        super(DhcpError, self).__init__('000006', msg)

class OSUtilError(AgentError):
    """
    Failed to perform operation to OS configuration
    """
    def __init__(self, msg=None):
        super(OSUtilError, self).__init__('000007', msg)

class ProtocolError(AgentError):
    """
    Azure protocol error
    """
    def __init__(self, msg=None):
        super(ProtocolError, self).__init__('000008', msg)

class ProtocolNotFoundError(ProtocolError):
    """
    Azure protocol endpoint not found
    """
    def __init__(self, msg=None):
        super(ProtocolNotFoundError, self).__init__(msg)

class HttpError(AgentError):
    """
    Http request failure
    """
    def __init__(self, msg=None):
        super(HttpError, self).__init__('000009', msg)

class EventError(AgentError):
    """
    Event reporting error
    """
    def __init__(self, msg=None):
        super(EventError, self).__init__('000010', msg)

class CryptError(AgentError):
    """
    Encrypt/Decrypt error
    """
    def __init__(self, msg=None):
        super(CryptError, self).__init__('000011', msg)
