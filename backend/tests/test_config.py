from opslens.config import Settings


def test_region_string_is_normalized() -> None:
    settings = Settings(default_aws_regions="ap-south-1, us-east-1,ap-south-1")
    assert settings.default_aws_regions == ["ap-south-1", "us-east-1", "ap-south-1"]


def test_backend_binds_to_loopback_by_default() -> None:
    settings = Settings()
    assert settings.host == "127.0.0.1"
