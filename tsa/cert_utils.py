"""
Simple certificate helper: generate CA and TSA cert for testing.
"""
import argparse
import datetime
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate(cadir: Path):
    cadir.mkdir(parents=True, exist_ok=True)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test TSA CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    ca_key_p = cadir / "ca_key.pem"
    ca_cert_p = cadir / "ca_cert.pem"
    with ca_key_p.open("wb") as f:
        f.write(ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with ca_cert_p.open("wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    # TSA key and cert
    tsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tsa_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test TSA")])
    tsa_cert = (
        x509.CertificateBuilder()
        .subject_name(tsa_name)
        .issuer_name(ca_cert.subject)
        .public_key(tsa_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    tsa_key_p = cadir / "tsa_key.pem"
    tsa_cert_p = cadir / "tsa_cert.pem"
    with tsa_key_p.open("wb") as f:
        f.write(tsa_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with tsa_cert_p.open("wb") as f:
        f.write(tsa_cert.public_bytes(serialization.Encoding.PEM))

    print(f"Generated CA and TSA certs in {cadir}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="./certs")
    args = p.parse_args()
    generate(Path(args.dir))


if __name__ == "__main__":
    main()
