import subprocess
import sys
from importlib.metadata import version

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from packaging.version import Version


@pytest.mark.parametrize(
    ("package", "minimum"),
    [
        ("cryptography", "50.0.0"),
        ("pygments", "2.20.0"),
        ("uv", "0.11.15"),
    ],
)
def test_security_sensitive_development_tools_are_patched(package, minimum):
    assert Version(version(package)) >= Version(minimum)


def test_cryptography_preserves_valid_aead_and_rejects_tampering():
    key = AESGCM.generate_key(bit_length=128)
    nonce = b"fixed-nonce!"
    plaintext = b"gitguard release metadata"
    associated_data = b"tsilva/.github"
    cipher = AESGCM(key)
    ciphertext = cipher.encrypt(nonce, plaintext, associated_data)

    assert cipher.decrypt(nonce, ciphertext, associated_data) == plaintext

    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
    with pytest.raises(InvalidTag):
        cipher.decrypt(nonce, tampered, associated_data)


def test_locked_uv_cli_starts_without_loading_external_projects():
    result = subprocess.run(
        [sys.executable, "-m", "uv", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert Version(result.stdout.strip().split()[1]) >= Version("0.11.15")
