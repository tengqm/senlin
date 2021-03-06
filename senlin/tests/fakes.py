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

'''
A module that contains various fake entities
'''

from senlin.common import schema
from senlin.policies import base as policy_base
from senlin.profiles import base as profile_base


class TestProfile(profile_base.Profile):
    spec_schema = {
        'INT': schema.Integer('int property', default=0),
        'STR': schema.String('string property', default='a string'),
        'MAP': schema.Map(
            'map property',
            schema={
                'KEY1': schema.Integer('key1'),
                'KEY2': schema.String('key2')
            }
        ),
        'LIST': schema.List(
            'list property',
            schema=schema.String('list item'),
        ),
    }

    def __init__(self, ctx, name, type_name='TestProfile', **kwargs):
        super(TestProfile, self).__init__(ctx, name, type_name, **kwargs)

    def do_create(self):
        return {}

    def do_delete(self, id):
        return True

    def do_update(self):
        return {}

    def do_check(self, id):
        return True


class TestPolicy(policy_base.Policy):
    spec_schema = {
        'KEY1': schema.String('key1', default='default1'),
        'KEY2': schema.Integer('key2', default=1),
    }

    def __init__(self, type_name, name, **kwargs):
        super(TestPolicy, self).__init__(type_name, name, **kwargs)

    def attach(self, context, cluster, policy_data):
        return

    def detach(self, context, cluster, policy_data):
        return

    def pre_op(self, cluster_id, action, policy_data):
        return policy_data

    def post_op(self, cluster_id, action, policy_data):
        return policy_data
