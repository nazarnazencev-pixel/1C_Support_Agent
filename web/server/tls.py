import os
from pathlib import Path


def configure_gigachat_certificates() -> None:
    certificate_path = Path(__file__).resolve().parent / "certs" / "russian_trusted_root_ca.pem"
    os.environ.setdefault("GIGACHAT_CA_BUNDLE_FILE", str(certificate_path))
