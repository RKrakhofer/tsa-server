"""
Minimal RFC3161-like TSA server using Flask.

This server accepts POST requests with raw data and returns a minimal timestamp token.
This is for demonstration and testing only and not production-grade.
"""
import argparse
import hashlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, Response

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from asn1crypto import cms, tsp, algos, core, x509 as asn1_x509, pem


app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok', 'service': 'tsa-server', 'version': '1.0.0'}, 200


def load_private_key(path: Path):
    with path.open('rb') as f:
        return load_pem_private_key(f.read(), password=None)


def load_asn1_cert(path: Path):
    data = path.read_bytes()
    if pem.detect(data):
        _, _, der_bytes = pem.unarmor(data)
    else:
        der_bytes = data
    return asn1_x509.Certificate.load(der_bytes)


def build_timestamp_token(data: bytes, tsa_key_p: Path, tsa_cert_p: Path, policy_oid: str = '1.3.6.1.4.1.0') -> bytes:
    # message imprint
    digest = hashlib.sha256(data).digest()
    mi = tsp.MessageImprint({
        'hash_algorithm': algos.DigestAlgorithm({'algorithm': 'sha256'}),
        'hashed_message': digest,
    })

    # TSTInfo
    serial = int.from_bytes(os.urandom(8), 'big') >> 1
    gen_time = datetime.now(timezone.utc)
    tst_info = tsp.TSTInfo({
        'version': 'v1',
        'policy': core.ObjectIdentifier(policy_oid),
        'message_imprint': mi,
        'serial_number': serial,
        'gen_time': core.GeneralizedTime(gen_time),
    })

    # Encapsulate TSTInfo: put the TSTInfo value directly (asn1crypto expects tsp.TSTInfo)
    eci = cms.EncapsulatedContentInfo({
        'content_type': 'tst_info',
        'content': tst_info,
    })

    # Load cert and key
    tsa_cert = load_asn1_cert(tsa_cert_p)
    key = load_private_key(tsa_key_p)

    # Build SignedAttributes per RFC3161: content-type, message-digest (of TSTInfo), signing-time
    tstinfo_der = tst_info.dump()
    md_tstinfo = hashlib.sha256(tstinfo_der).digest()

    signing_time = core.GeneralizedTime(gen_time)

    signed_attrs = cms.CMSAttributes([
        cms.CMSAttribute({'type': 'content_type', 'values': ['1.2.840.113549.1.9.16.1.4']}),
        cms.CMSAttribute({'type': 'message_digest', 'values': [md_tstinfo]}),
        cms.CMSAttribute({'type': 'signing_time', 'values': [signing_time]}),
    ])

    # Sign the DER encoding of the SignedAttributes (the SET OF attributes, in DER)
    # Per RFC 5652: SignedAttributes are DER-encoded as [0] IMPLICIT but signature
    # is computed over the bytes with the tag changed to SET (0x31)
    signed_attrs_der = signed_attrs.dump()
    
    # Replace context-specific tag 0xA0 with SET tag 0x31 for signing
    if signed_attrs_der[0:1] == b'\xa0':
        to_sign = b'\x31' + signed_attrs_der[1:]
    else:
        to_sign = signed_attrs_der
    
    signature = key.sign(to_sign, padding.PKCS1v15(), hashes.SHA256())

    # Build SignerInfo
    issuer = tsa_cert.issuer
    serial_number = tsa_cert.serial_number
    signer_id = cms.SignerIdentifier({'issuer_and_serial_number': cms.IssuerAndSerialNumber({'issuer': issuer, 'serial_number': serial_number})})

    signer_info = cms.SignerInfo({
        'version': 'v1',
        'sid': signer_id,
        'digest_algorithm': algos.DigestAlgorithm({'algorithm': 'sha256'}),
        'signature_algorithm': algos.SignedDigestAlgorithm({'algorithm': 'sha256_rsa'}),
        'signed_attrs': signed_attrs,
        'signature': signature,
    })

    # Certificates
    certs = [tsa_cert]

    signed_data = cms.SignedData({
        'version': 'v3',
        'digest_algorithms': [algos.DigestAlgorithm({'algorithm': 'sha256'})],
        'encap_content_info': eci,
        'certificates': certs,
        'signer_infos': [signer_info],
    })

    content_info = cms.ContentInfo({'content_type': 'signed_data', 'content': signed_data})

    return content_info.dump()


@app.route('/tsa', methods=['POST'])
def tsa():
    data = request.get_data()
    if not data:
        return Response('No data', status=400)

    # Paths (expecting certs in ./certs)
    tsa_key_path = Path('./certs/tsa_key.pem')
    tsa_cert_path = Path('./certs/tsa_cert.pem')
    if not tsa_key_path.exists() or not tsa_cert_path.exists():
        return Response('TSA key/cert not found on server', status=500)

    # Support JSON output for human-readable tokens if requested
    want_json = False
    if request.args.get('format') == 'json':
        want_json = True
    accept = request.headers.get('Accept', '')
    if 'application/json' in accept:
        want_json = True

    token_der = build_timestamp_token(data, tsa_key_path, tsa_cert_path)

    if want_json:
        # Parse the DER to extract TSTInfo fields for a readable JSON response
        from asn1crypto import cms
        ci = cms.ContentInfo.load(token_der)
        sd = ci['content']
        encap = sd['encap_content_info']['content']
        try:
            # encap may be ParsableOctetString
            tst = encap.parsed
        except Exception:
            # fallback: load directly
            from asn1crypto import tsp as _tsp
            tst = _tsp.TSTInfo.load(bytes(encap))

        # Extract useful fields from TSTInfo
        mi = tst['message_imprint']
        hash_algo = None
        try:
            hash_algo = mi['hash_algorithm']['algorithm'].native
        except Exception:
            hash_algo = str(mi['hash_algorithm'])
        digest = mi['hashed_message'].native.hex()

        gen_time = None
        try:
            gen_time = tst['gen_time'].native.isoformat()
        except Exception:
            gen_time = str(tst['gen_time'])

        serial = None
        try:
            serial = int(tst['serial_number'].native)
        except Exception:
            serial = str(tst['serial_number'])

        # Optional fields
        accuracy = None
        try:
            acc = tst['accuracy']
            if acc is not None:
                accuracy = {}
                if getattr(acc, 'native', None) is not None:
                    if acc['seconds'] is not None:
                        accuracy['seconds'] = int(acc['seconds'].native)
                    if acc['millis'] is not None:
                        accuracy['millis'] = int(acc['millis'].native)
                    if acc['micros'] is not None:
                        accuracy['micros'] = int(acc['micros'].native)
        except Exception:
            accuracy = None

        ordering = None
        try:
            ordering = bool(tst['ordering'].native) if tst['ordering'] is not None else None
        except Exception:
            ordering = None

        nonce = None
        try:
            nonce = int(tst['nonce'].native) if tst['nonce'] is not None else None
        except Exception:
            try:
                nonce = str(tst['nonce'].native)
            except Exception:
                nonce = None

        tsa_name = None
        try:
            if tst['tsa'] is not None:
                tsa_name = str(tst['tsa'])
        except Exception:
            tsa_name = None

        extensions = None
        try:
            if tst['extensions'] is not None:
                extensions = []
                for ext in tst['extensions']:
                    try:
                        extensions.append({
                            'oid': ext['extn_id'].dotted,
                            'critical': bool(ext['critical'].native),
                            'value': str(ext['extn_value'].parsed) if ext['extn_value'] is not None else None,
                        })
                    except Exception:
                        extensions.append({'oid': str(ext['extn_id']), 'critical': bool(ext['critical'].native)})
        except Exception:
            extensions = None

        # Extract signature from signerInfo
        signer_info = sd['signer_infos'][0]
        signature = signer_info['signature'].native.hex()

        payload = {
            'version': tst['version'].native if tst['version'] is not None else 'v1',
            'policy': tst['policy'].dotted if tst['policy'] is not None else None,
            'message_imprint': {
                'hash_algorithm': hash_algo,
                'hashed_message': digest,
            },
            'serial_number': serial,
            'gen_time': gen_time,
            'accuracy': accuracy,
            'ordering': ordering,
            'nonce': nonce,
            'tsa': tsa_name,
            'extensions': extensions,
            'signature': signature,
        }
        import json
        return Response(json.dumps(payload, indent=2), mimetype='application/json')

    # Default: return DER timestamp reply with appropriate headers
    resp = Response(token_der, mimetype='application/timestamp-reply')
    resp.headers['Content-Disposition'] = 'attachment; filename="timestamp.tsr"'
    return resp


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', default=5000, type=int)
    args = p.parse_args()
    app.run(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
