import sure

from moto.utilities.tagging_service import TaggingService


def test_list_empty():
    svc = TaggingService()
    result = svc.list_tags_for_resource("test")

    {"Tags": []}.should.be.equal(result)


def test_create_tag():
    svc = TaggingService("TheTags", "TagKey", "TagValue")
    tags = [{"TagKey": "key_key", "TagValue": "value_value"}]
    svc.tag_resource("arn", tags)
    actual = svc.list_tags_for_resource("arn")
    expected = {"TheTags": [{"TagKey": "key_key", "TagValue": "value_value"}]}

    expected.should.be.equal(actual)


def test_create_tag_without_value():
    svc = TaggingService()
    tags = [{"Key": "key_key"}]
    svc.tag_resource("arn", tags)
    actual = svc.list_tags_for_resource("arn")
    expected = {"Tags": [{"Key": "key_key", "Value": None}]}

    expected.should.be.equal(actual)


def test_delete_tag_using_names():
    svc = TaggingService()
    tags = [{"Key": "key_key", "Value": "value_value"}]
    svc.tag_resource("arn", tags)
    svc.untag_resource_using_names("arn", ["key_key"])
    result = svc.list_tags_for_resource("arn")

    {"Tags": []}.should.be.equal(result)


def test_delete_all_tags_for_resource():
    svc = TaggingService()
    tags = [{"Key": "key_key", "Value": "value_value"}]
    tags2 = [{"Key": "key_key2", "Value": "value_value2"}]
    svc.tag_resource("arn", tags)
    svc.tag_resource("arn", tags2)
    svc.delete_all_tags_for_resource("arn")
    result = svc.list_tags_for_resource("arn")

    {"Tags": []}.should.be.equal(result)


def test_list_empty_delete():
    svc = TaggingService()
    svc.untag_resource_using_names("arn", ["key_key"])
    result = svc.list_tags_for_resource("arn")

    {"Tags": []}.should.be.equal(result)


def test_delete_tag_using_tags():
    svc = TaggingService()
    tags = [{"Key": "key_key", "Value": "value_value"}]
    svc.tag_resource("arn", tags)
    svc.untag_resource_using_tags("arn", tags)
    result = svc.list_tags_for_resource("arn")

    {"Tags": []}.should.be.equal(result)


def test_extract_tag_names():
    svc = TaggingService()
    tags = [{"Key": "key1", "Value": "value1"}, {"Key": "key2", "Value": "value2"}]
    actual = svc.extract_tag_names(tags)
    expected = ["key1", "key2"]

    expected.should.be.equal(actual)
