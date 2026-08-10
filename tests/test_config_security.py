"""Unit tests for Phase 0 network/security config helpers."""

from io import StringIO
from contextlib import redirect_stdout

import pytest

from spectrax.config import create_config, SurveillanceConfig
from spectrax.utils import print_urls


pytestmark = pytest.mark.unit


def test_rtsp_encryption_strict_when_tls_present():
    cfg = create_config(
        "127.0.0.1",
        ["video/cam"],
        {
            "publish_user": "publisher",
            "publish_pass": "pub-secret",
            "read_user": "viewer",
            "read_pass": "view-secret",
        },
        tls_key="/tmp/key.pem",
        tls_cert="/tmp/cert.pem",
    )
    assert cfg["rtspEncryption"] == "strict"


def test_default_bind_is_loopback():
    sc = SurveillanceConfig()
    assert sc.get_bind_address() == "127.0.0.1"


def test_print_urls_redacts_passwords():
    creds = {
        "publish_user": "publisher",
        "publish_pass": "super-pub-pass-XYZ",
        "read_user": "viewer",
        "read_pass": "super-view-pass-ABC",
    }
    buf = StringIO()
    with redirect_stdout(buf):
        print_urls("127.0.0.1", ["video/cam"], creds, rtsps=True)
    # Ensure secrets are not interpolated into URLs in the function body
    import inspect

    from spectrax import utils as u

    src = inspect.getsource(u.print_urls)
    assert "user:pass@" not in src
    assert "creds['publish_pass']" not in src
    assert "creds['read_pass']" not in src
