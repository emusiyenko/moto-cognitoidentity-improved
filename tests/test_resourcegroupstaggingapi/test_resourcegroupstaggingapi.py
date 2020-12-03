from __future__ import unicode_literals

import boto3
import sure  # noqa
from moto import mock_ec2
from moto import mock_elbv2
from moto import mock_kms
from moto import mock_resourcegroupstaggingapi
from moto import mock_s3


@mock_ec2
@mock_resourcegroupstaggingapi
def test_get_resources_ec2():
    client = boto3.client("ec2", region_name="eu-central-1")

    instances = client.run_instances(
        ImageId="ami-123",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "MY_TAG1", "Value": "MY_VALUE1"},
                    {"Key": "MY_TAG2", "Value": "MY_VALUE2"},
                ],
            },
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "MY_TAG3", "Value": "MY_VALUE3"}],
            },
        ],
    )
    instance_id = instances["Instances"][0]["InstanceId"]
    image_id = client.create_image(Name="testami", InstanceId=instance_id)["ImageId"]

    client.create_tags(Resources=[image_id], Tags=[{"Key": "ami", "Value": "test"}])

    rtapi = boto3.client("resourcegroupstaggingapi", region_name="eu-central-1")
    resp = rtapi.get_resources()
    # Check we have 1 entry for Instance, 1 Entry for AMI
    resp["ResourceTagMappingList"].should.have.length_of(2)

    # 1 Entry for AMI
    resp = rtapi.get_resources(ResourceTypeFilters=["ec2:image"])
    resp["ResourceTagMappingList"].should.have.length_of(1)
    resp["ResourceTagMappingList"][0]["ResourceARN"].should.contain("image/")

    # As were iterating the same data, this rules out that the test above was a fluke
    resp = rtapi.get_resources(ResourceTypeFilters=["ec2:instance"])
    resp["ResourceTagMappingList"].should.have.length_of(1)
    resp["ResourceTagMappingList"][0]["ResourceARN"].should.contain("instance/")

    # Basic test of tag filters
    resp = rtapi.get_resources(
        TagFilters=[{"Key": "MY_TAG1", "Values": ["MY_VALUE1", "some_other_value"]}]
    )
    resp["ResourceTagMappingList"].should.have.length_of(1)
    resp["ResourceTagMappingList"][0]["ResourceARN"].should.contain("instance/")


@mock_ec2
@mock_resourcegroupstaggingapi
def test_get_resources_ec2_vpc():
    ec2 = boto3.resource("ec2", region_name="us-west-1")
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    ec2.create_tags(Resources=[vpc.id], Tags=[{"Key": "test", "Value": "test"}])

    def assert_response(resp):
        results = resp.get("ResourceTagMappingList", [])
        results.should.have.length_of(1)
        vpc.id.should.be.within(results[0]["ResourceARN"])

    rtapi = boto3.client("resourcegroupstaggingapi", region_name="us-west-1")
    resp = rtapi.get_resources(ResourceTypeFilters=["ec2"])
    assert_response(resp)
    resp = rtapi.get_resources(ResourceTypeFilters=["ec2:vpc"])
    assert_response(resp)
    resp = rtapi.get_resources(TagFilters=[{"Key": "test", "Values": ["test"]}])
    assert_response(resp)


@mock_ec2
@mock_resourcegroupstaggingapi
def test_get_tag_keys_ec2():
    client = boto3.client("ec2", region_name="eu-central-1")

    client.run_instances(
        ImageId="ami-123",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "MY_TAG1", "Value": "MY_VALUE1"},
                    {"Key": "MY_TAG2", "Value": "MY_VALUE2"},
                ],
            },
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "MY_TAG3", "Value": "MY_VALUE3"}],
            },
        ],
    )

    rtapi = boto3.client("resourcegroupstaggingapi", region_name="eu-central-1")
    resp = rtapi.get_tag_keys()

    resp["TagKeys"].should.contain("MY_TAG1")
    resp["TagKeys"].should.contain("MY_TAG2")
    resp["TagKeys"].should.contain("MY_TAG3")

    # TODO test pagenation


@mock_ec2
@mock_resourcegroupstaggingapi
def test_get_tag_values_ec2():
    client = boto3.client("ec2", region_name="eu-central-1")

    client.run_instances(
        ImageId="ami-123",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "MY_TAG1", "Value": "MY_VALUE1"},
                    {"Key": "MY_TAG2", "Value": "MY_VALUE2"},
                ],
            },
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "MY_TAG3", "Value": "MY_VALUE3"}],
            },
        ],
    )
    client.run_instances(
        ImageId="ami-123",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "MY_TAG1", "Value": "MY_VALUE4"},
                    {"Key": "MY_TAG2", "Value": "MY_VALUE5"},
                ],
            },
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "MY_TAG3", "Value": "MY_VALUE6"}],
            },
        ],
    )

    rtapi = boto3.client("resourcegroupstaggingapi", region_name="eu-central-1")
    resp = rtapi.get_tag_values(Key="MY_TAG1")

    resp["TagValues"].should.contain("MY_VALUE1")
    resp["TagValues"].should.contain("MY_VALUE4")


@mock_ec2
@mock_elbv2
@mock_kms
@mock_resourcegroupstaggingapi
def test_get_many_resources():
    elbv2 = boto3.client("elbv2", region_name="us-east-1")
    ec2 = boto3.resource("ec2", region_name="us-east-1")
    kms = boto3.client("kms", region_name="us-east-1")

    security_group = ec2.create_security_group(
        GroupName="a-security-group", Description="First One"
    )
    vpc = ec2.create_vpc(CidrBlock="172.28.7.0/24", InstanceTenancy="default")
    subnet1 = ec2.create_subnet(
        VpcId=vpc.id, CidrBlock="172.28.7.192/26", AvailabilityZone="us-east-1a"
    )
    subnet2 = ec2.create_subnet(
        VpcId=vpc.id, CidrBlock="172.28.7.0/26", AvailabilityZone="us-east-1b"
    )

    elbv2.create_load_balancer(
        Name="my-lb",
        Subnets=[subnet1.id, subnet2.id],
        SecurityGroups=[security_group.id],
        Scheme="internal",
        Tags=[
            {"Key": "key_name", "Value": "a_value"},
            {"Key": "key_2", "Value": "val2"},
        ],
    )

    elbv2.create_load_balancer(
        Name="my-other-lb",
        Subnets=[subnet1.id, subnet2.id],
        SecurityGroups=[security_group.id],
        Scheme="internal",
    )

    kms.create_key(
        KeyUsage="ENCRYPT_DECRYPT",
        Tags=[
            {"TagKey": "key_name", "TagValue": "a_value"},
            {"TagKey": "key_2", "TagValue": "val2"},
        ],
    )

    rtapi = boto3.client("resourcegroupstaggingapi", region_name="us-east-1")

    resp = rtapi.get_resources(
        ResourceTypeFilters=["elasticloadbalancing:loadbalancer"]
    )

    resp["ResourceTagMappingList"].should.have.length_of(2)
    resp["ResourceTagMappingList"][0]["ResourceARN"].should.contain("loadbalancer/")
    resp = rtapi.get_resources(
        ResourceTypeFilters=["elasticloadbalancing:loadbalancer"],
        TagFilters=[{"Key": "key_name"}],
    )

    resp["ResourceTagMappingList"].should.have.length_of(1)
    resp["ResourceTagMappingList"][0]["Tags"].should.contain(
        {"Key": "key_name", "Value": "a_value"}
    )

    # TODO test pagination


@mock_ec2
@mock_elbv2
@mock_resourcegroupstaggingapi
def test_get_resources_target_group():
    ec2 = boto3.resource("ec2", region_name="eu-central-1")
    elbv2 = boto3.client("elbv2", region_name="eu-central-1")

    vpc = ec2.create_vpc(CidrBlock="172.28.7.0/24", InstanceTenancy="default")

    # Create two tagged target groups
    for i in range(1, 3):
        i_str = str(i)

        target_group = elbv2.create_target_group(
            Name="test" + i_str,
            Protocol="HTTP",
            Port=8080,
            VpcId=vpc.id,
            TargetType="instance",
        )["TargetGroups"][0]

        elbv2.add_tags(
            ResourceArns=[target_group["TargetGroupArn"]],
            Tags=[{"Key": "Test", "Value": i_str}],
        )

    rtapi = boto3.client("resourcegroupstaggingapi", region_name="eu-central-1")

    # Basic test
    resp = rtapi.get_resources(ResourceTypeFilters=["elasticloadbalancing:targetgroup"])
    resp["ResourceTagMappingList"].should.have.length_of(2)

    # Test tag filtering
    resp = rtapi.get_resources(
        ResourceTypeFilters=["elasticloadbalancing:targetgroup"],
        TagFilters=[{"Key": "Test", "Values": ["1"]}],
    )
    resp["ResourceTagMappingList"].should.have.length_of(1)
    resp["ResourceTagMappingList"][0]["Tags"].should.contain(
        {"Key": "Test", "Value": "1"}
    )


@mock_s3
@mock_resourcegroupstaggingapi
def test_get_resources_s3():
    # Tests pagination
    s3_client = boto3.client("s3", region_name="eu-central-1")

    # Will end up having key1,key2,key3,key4
    response_keys = set()

    # Create 4 buckets
    for i in range(1, 5):
        i_str = str(i)
        s3_client.create_bucket(
            Bucket="test_bucket" + i_str,
            CreateBucketConfiguration={"LocationConstraint": "eu-central-1"},
        )
        s3_client.put_bucket_tagging(
            Bucket="test_bucket" + i_str,
            Tagging={"TagSet": [{"Key": "key" + i_str, "Value": "value" + i_str}]},
        )
        response_keys.add("key" + i_str)

    rtapi = boto3.client("resourcegroupstaggingapi", region_name="eu-central-1")
    resp = rtapi.get_resources(ResourcesPerPage=2)
    for resource in resp["ResourceTagMappingList"]:
        response_keys.remove(resource["Tags"][0]["Key"])

    response_keys.should.have.length_of(2)

    resp = rtapi.get_resources(
        ResourcesPerPage=2, PaginationToken=resp["PaginationToken"]
    )
    for resource in resp["ResourceTagMappingList"]:
        response_keys.remove(resource["Tags"][0]["Key"])

    response_keys.should.have.length_of(0)


@mock_ec2
@mock_resourcegroupstaggingapi
def test_multiple_tag_filters():
    client = boto3.client("ec2", region_name="eu-central-1")

    resp = client.run_instances(
        ImageId="ami-123",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "MY_TAG1", "Value": "MY_UNIQUE_VALUE"},
                    {"Key": "MY_TAG2", "Value": "MY_SHARED_VALUE"},
                ],
            },
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "MY_TAG3", "Value": "MY_VALUE3"}],
            },
        ],
    )
    instance_1_id = resp["Instances"][0]["InstanceId"]

    resp = client.run_instances(
        ImageId="ami-456",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "MY_TAG1", "Value": "MY_ALT_UNIQUE_VALUE"},
                    {"Key": "MY_TAG2", "Value": "MY_SHARED_VALUE"},
                ],
            },
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "MY_ALT_TAG3", "Value": "MY_VALUE3"}],
            },
        ],
    )
    instance_2_id = resp["Instances"][0]["InstanceId"]

    rtapi = boto3.client("resourcegroupstaggingapi", region_name="eu-central-1")
    results = rtapi.get_resources(
        TagFilters=[
            {"Key": "MY_TAG1", "Values": ["MY_UNIQUE_VALUE"]},
            {"Key": "MY_TAG2", "Values": ["MY_SHARED_VALUE"]},
        ]
    ).get("ResourceTagMappingList", [])
    results.should.have.length_of(1)
    instance_1_id.should.be.within(results[0]["ResourceARN"])
    instance_2_id.shouldnt.be.within(results[0]["ResourceARN"])
