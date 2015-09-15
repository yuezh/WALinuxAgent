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
from tests.tools import AgentTestCase
import uuid
import unittest
import os
import shutil
import time
from azurelinuxagent.protocol.common import *

class SampleDataContract(DataContract):
    def __init__(self):
        self.foo = None
        self.bar = DataContractList(int)

class TestDataContract(AgentTestCase):
    def test_get_properties(self):
        obj = SampleDataContract()
        obj.foo = "foo"
        obj.bar.append(1)
        data = get_properties(obj)
        self.assertEquals("foo", data["foo"])
        self.assertEquals(list, type(data["bar"]))

    def test_set_properties(self):
        obj = SampleDataContract()
        data = {
                'foo' : 1, 
                'baz': 'a'
        }
        set_properties('sample', obj, data)
        self.assertFalse(hasattr(obj, 'baz'))

if __name__ == '__main__':
    unittest.main()
