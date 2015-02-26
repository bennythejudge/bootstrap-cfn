import tempfile
import unittest
import mock
import yaml
import boto.cloudformation
import boto.ec2.autoscale
from awsutils import cloudformation
from awsutils import ec2
import os


class CfnTestCase(unittest.TestCase):

    def setUp(self):
        self.work_dir = tempfile.mkdtemp()

        self.env = mock.Mock()
        self.env.aws = 'dev'
        self.env.environment = 'dev'
        self.env.application = 'unittest-app'
        self.env.config = os.path.join(self.work_dir, 'test_config.yaml')

        config = {'dev': {'ec2': {'auto_scaling': {'desired': 1, 'max': 3,
                                                   'min': 0},
                                  'block_devices': [{'DeviceName': '/dev/sda1',
                                                     'VolumeSize': 10},
                                                    {'DeviceName': '/dev/sdf',
                                                     'VolumeSize': 10}],
                                  'parameters': {'InstanceType': 't2.micro',
                                                 'KeyName': 'default'},
                                  'security_groups': [{'CidrIp': '0.0.0.0/0',
                                                       'FromPort': 22,
                                                       'IpProtocol': 'tcp',
                                                       'ToPort': 22},
                                                      {'CidrIp': '0.0.0.0/0',
                                                       'FromPort': 80,
                                                       'IpProtocol': 'tcp',
                                                       'ToPort': 80}],
                                  'tags': {'Apps': 'test', 'Env': 'dev',
                                           'Role': 'docker'}},
                          'elb': [{'hosted_zone': 'kyrtest.pf.dsd.io.',
                                   'listeners': [{'InstancePort': 80,
                                                  'LoadBalancerPort': 80,
                                                  'Protocol': 'TCP'},
                                                 {'InstancePort': 443,
                                                  'LoadBalancerPort': 443,
                                                  'Protocol': 'TCP'}],
                                   'name': 'test-dev-external',
                                   'scheme': 'internet-facing'},
                                  {'hosted_zone': 'kyrtest.pf.dsd.io.',
                                   'listeners': [{'InstancePort': 80,
                                                  'LoadBalancerPort': 80,
                                                  'Protocol': 'TCP'}],
                                   'name': 'test-dev-internal',
                                   'scheme': 'internet-facing'}],
                          'rds': {'backup-retention-period': 1,
                                  'db-engine': 'postgres',
                                  'db-engine-version': '9.3.5',
                                  'db-master-password': 'testpassword',
                                  'db-master-username': 'testuser',
                                  'db-name': 'test',
                                  'identifier': 'test-dev',
                                  'instance-class': 'db.t2.micro',
                                  'multi-az': False,
                                  'storage': 5,
                                  'storage-type': 'gp2'},
                          's3': {'static-bucket-name': 'moj-test-dev-static'}}}
        yaml.dump(config, open(self.env.config, 'w'))

        self.aws_config = mock.Mock()
        self.aws_config.aws_access = 'aws_access_key'
        self.aws_config.aws_secret = 'aws_secret_key'
        self.aws_config.region = 'aws_region'

        self.stack_name = '{0}-{1}'.format(self.env.application,
                                           self.env.environment)
        self.cf = cloudformation.Cloudformation(self.aws_config)

    def test_cf_create(self):
        cf_mock = mock.Mock()
        cf_connect_result = mock.Mock(name='cf_connect')
        cf_mock.return_value = cf_connect_result
        mock_config = {'create_stack.return_value': self.stack_name}
        cf_connect_result.configure_mock(**mock_config)
        boto.cloudformation.connect_to_region = cf_mock
        cf = cloudformation.Cloudformation(self.aws_config)
        x = cf.create(self.stack_name, '{}')
        self.assertEqual(x, self.stack_name)

    def test_stack_done(self):
        stack_evt_mock = mock.Mock()
        rt = mock.PropertyMock(return_value='AWS::CloudFormation::Stack')
        rs = mock.PropertyMock(return_value='CREATE_COMPLETE')
        type(stack_evt_mock).resource_type = rt
        type(stack_evt_mock).resource_status = rs
        mock_config = {'describe_stack_events.return_value': [stack_evt_mock]}

        cf_mock = mock.Mock()
        cf_connect_result = mock.Mock(name='cf_connect')
        cf_mock.return_value = cf_connect_result
        cf_connect_result.configure_mock(**mock_config)

        boto.cloudformation.connect_to_region = cf_mock

        self.assertTrue(cloudformation.Cloudformation(
            self.aws_config).stack_done(self.stack_name))

    def test_stack_not_done(self):
        stack_evt_mock = mock.Mock()
        rt = mock.PropertyMock(return_value='AWS::CloudFormation::Stack')
        rs = mock.PropertyMock(return_value='CREATE_COMPLETE_FAKE')
        type(stack_evt_mock).resource_type = rt
        type(stack_evt_mock).resource_status = rs

        cf_mock = mock.Mock()
        cf_connect_result = mock.Mock(name='cf_connect')
        cf_mock.return_value = cf_connect_result
        mock_config = {'describe_stack_events.return_value': [stack_evt_mock]}
        cf_connect_result.configure_mock(**mock_config)
        boto.cloudformation.connect_to_region = cf_mock

        self.assertFalse(cloudformation.Cloudformation(
            self.aws_config).stack_done(self.stack_name))

    def test_get_stack_instance_ids(self):
        scaling_group = mock.Mock()
        rt = mock.PropertyMock(
            return_value='AWS::AutoScaling::AutoScalingGroup')
        sgi = mock.PropertyMock(
            return_value='some-resource-id')
        type(scaling_group).resource_type = rt
        type(scaling_group).physical_resource_id = sgi

        stack_mock = mock.Mock()
        mock_config = {'list_resources.return_value': [scaling_group]}
        stack_mock.configure_mock(**mock_config)

        cf_mock = mock.Mock()
        cf_connect_result = mock.Mock(name='cf_connect')
        cf_mock.return_value = cf_connect_result
        mock_config = {'describe_stacks.return_value': [stack_mock]}
        cf_connect_result.configure_mock(**mock_config)
        boto.cloudformation.connect_to_region = cf_mock

        instance_mock = mock.Mock()
        instance_id = mock.PropertyMock(return_value='i-12345')
        type(instance_mock).instance_id = instance_id

        scaling_group_mock = mock.Mock()
        instances = mock.PropertyMock(return_value=[instance_mock])
        type(scaling_group_mock).instances = instances

        as_mock = mock.Mock()
        as_connect_result = mock.Mock(name='as_connect')
        as_mock.return_value = as_connect_result
        mock_config = {'get_all_groups.return_value': [scaling_group_mock]}
        as_connect_result.configure_mock(**mock_config)
        boto.ec2.autoscale.connect_to_region = as_mock

        cf = cloudformation.Cloudformation(self.aws_config)
        x = cf.get_stack_instance_ids(self.stack_name)
        self.assertEqual(x, ['i-12345'])

    def test_get_instance_id_list_empty(self):
        x = ec2.EC2(self.aws_config).get_instance_public_ips([])
        self.assertEqual(x, [])

    def test_get_instance_id_list(self):
        instance_mock = mock.Mock()
        ip_address = mock.PropertyMock(return_value='1.1.1.1')
        type(instance_mock).ip_address = ip_address

        ec2_mock = mock.Mock()
        ec2_connect_result = mock.Mock(name='cf_connect')
        ec2_mock.return_value = ec2_connect_result
        mock_config = {'get_only_instances.return_value': [instance_mock]}
        ec2_connect_result.configure_mock(**mock_config)
        boto.ec2.connect_to_region = ec2_mock

        ec = ec2.EC2(self.aws_config)
        ips = ec.get_instance_public_ips(['i-12345'])
        self.assertEqual(ips, ['1.1.1.1'])

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()