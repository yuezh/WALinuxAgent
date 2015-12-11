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

from tests.tools import *
from tests.protocol.mockwiredata import *
import uuid
import unittest
import os
import time
from azurelinuxagent.utils.restutil import httpclient
from azurelinuxagent.utils.cryptutil import CryptUtil
from azurelinuxagent.protocol.restapi import *
from azurelinuxagent.protocol.wire import WireClient, WireProtocol, \
                                          TRANSPORT_PRV_FILE_NAME, \
                                          TRANSPORT_CERT_FILE_NAME

data_with_bom = b'\xef\xbb\xbfhehe'

@patch("time.sleep")
@patch("azurelinuxagent.protocol.wire.CryptUtil")
@patch("azurelinuxagent.protocol.wire.restutil")
class TestWireProtocolGetters(AgentTestCase):
    
    def _test_getters(self, test_data, mock_restutil, MockCryptUtil, _):
        mock_restutil.http_get.side_effect = test_data.mock_http_get
        MockCryptUtil.side_effect = test_data.mock_crypt_util

        protocol = WireProtocol("foo.bar")
        protocol.detect()
        protocol.get_vminfo()
        protocol.get_certs()
        ext_handlers = protocol.get_ext_handlers()
        for ext_handler in ext_handlers.extHandlers:
            protocol.get_ext_handler_pkgs(ext_handler)

        crt1 = os.path.join(self.tmp_dir, 
                           '33B0ABCE4673538650971C10F7D7397E71561F35.crt')
        crt2 = os.path.join(self.tmp_dir, 
                            '4037FBF5F1F3014F99B5D6C7799E9B20E6871CB3.crt')
        prv2 = os.path.join(self.tmp_dir,
                            '4037FBF5F1F3014F99B5D6C7799E9B20E6871CB3.prv')

        self.assertTrue(os.path.isfile(crt1))
        self.assertTrue(os.path.isfile(crt2))
        self.assertTrue(os.path.isfile(prv2))
    
    def test_getters(self, *args):
        """Normal case"""
        test_data = WireProtocolData(DATA_FILE)
        self._test_getters(test_data, *args)

    def test_getters_no_ext(self, *args):
        """Provision with agent is not checked"""
        test_data = WireProtocolData(DATA_FILE_NO_EXT)
        self._test_getters(test_data, *args)

    def test_getters_ext_no_settings(self, *args):
        """Provision with agent is not checked"""
        test_data = WireProtocolData(DATA_FILE_EXT_NO_SETTINGS)
        self._test_getters(test_data, *args)
        
    def test_getters_ext_no_public(self, *args):
        """Provision with agent is not checked"""
        test_data = WireProtocolData(DATA_FILE_EXT_NO_PUBLIC)
        self._test_getters(test_data, *args)

if __name__ == '__main__':
    unittest.main()
