# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_messaging.rpc import dispatcher as rpc

from senlin.common import exception
from senlin.engine import environment
from senlin.engine import service
from senlin.tests.common import base
from senlin.tests.common import utils
from senlin.tests import fakes


class ProfileTypeTest(base.SenlinTestCase):

    def setUp(self):
        super(ProfileTypeTest, self).setUp()
        self.ctx = utils.dummy_context(tenant_id='profile_type_test_tenant')
        self.eng = service.EngineService('host-a', 'topic-a')
        self.eng.init_tgm()
        environment.global_env().register_profile('TestProfile',
                                                  fakes.TestProfile)

    def test_profile_type_list(self):
        types = self.eng.profile_type_list(self.ctx)
        self.assertIsInstance(types, list)
        self.assertIn({'name': 'os.heat.stack'}, types)
        self.assertNotIn({'name': 'some-weird-stuff'}, types)

    def test_profile_type_schema(self):
        type_name = 'TestProfile'
        expected = {
            'spec': {
                'INT': {
                    'type': 'Integer',
                    'required': False,
                    'description': 'int property',
                    'default': 0,
                },
                'STR': {
                    'type': 'String',
                    'required': False,
                    'description': 'string property',
                    'default': 'a string',
                },
                'LIST': {
                    'type': 'List',
                    'description': 'list property',
                    'required': False,
                    'schema': {
                        '*': {
                            'type': 'String',
                            'description': 'list item',
                            'required': False,
                        },
                    },
                },

                'MAP': {
                    'type': 'Map',
                    'description': 'map property',
                    'required': False,
                    'schema': {
                        'KEY1': {
                            'type': 'Integer',
                            'description': 'key1',
                            'required': False,
                        },
                        'KEY2': {
                            'type': 'String',
                            'description': 'key2',
                            'required': False,
                        },
                    },
                },
            },
        }

        schema = self.eng.profile_type_schema(self.ctx, type_name=type_name)
        self.assertEqual(expected, schema)

    def test_profile_type_schema_nonexist(self):
        ex = self.assertRaises(rpc.ExpectedException,
                               self.eng.profile_type_schema,
                               self.ctx, type_name='Bogus')
        self.assertEqual(exception.ProfileTypeNotFound, ex.exc_info[0])
