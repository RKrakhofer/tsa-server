"""Verify a DER-encoded timestamp reply (ContentInfo SignedData) against a TSA cert."""
import sys
from pathlib import Path
from asn1crypto import cms
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography import x509 as crypto_x509
from cryptography.hazmat.primitives.serialization import load_pem_public_key


def verify(reply_path: Path, cert_path: Path):
    data = reply_path.read_bytes()
    ci = cms.ContentInfo.load(data)
    sd = ci['content']
    signer_info = sd['signer_infos'][0]
    signed_attrs = signer_info['signed_attrs']
    sig = signer_info['signature'].native

    # signed attributes DER (must be the DER encoding of the SET OF attributes)
    signed_attrs_der = signed_attrs.dump()
    # Per RFC 5652: replace context-specific tag 0xA0 with SET tag 0x31 for verification
    if signed_attrs_der[0:1] == b'\xa0':
        signed_attrs_ver = b'\x31' + signed_attrs_der[1:]
    else:
        signed_attrs_ver = signed_attrs_der

    # load cert (PEM or DER)
    cert_bytes = cert_path.read_bytes()
    try:
        cert = crypto_x509.load_pem_x509_certificate(cert_bytes)
    except Exception:
        cert = crypto_x509.load_der_x509_certificate(cert_bytes)

    pubkey = cert.public_key()

    try:
        pubkey.verify(sig, signed_attrs_ver, padding.PKCS1v15(), hashes.SHA256())
        print('Signature OK')
    except Exception as e:
        print('Signature INVALID:', e)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: verify_tsr.py <reply.der> <tsa_cert.pem>')
        raise SystemExit(2)
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
