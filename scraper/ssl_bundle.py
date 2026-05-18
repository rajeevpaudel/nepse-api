from pathlib import Path
import certifi
import httpx
from cryptography import x509
from cryptography.hazmat.primitives import serialization

INTERMEDIATE_URL = "http://cacerts.geotrust.com/GeoTrustTLSRSACAG1.crt"


async def get_ssl_bundle(cache_dir: str | None = None) -> str:
    import config as _config
    base = Path(cache_dir or _config.CACHE_DIR) / "nepalstock_ssl"
    base.mkdir(parents=True, exist_ok=True)
    intermediate_pem = base / "GeoTrustTLSRSACAG1.pem"
    bundle = base / "cacert_with_geotrust_tls_rsa_ca_g1.pem"

    if not intermediate_pem.exists():
        async with httpx.AsyncClient() as client:
            resp = await client.get(INTERMEDIATE_URL, timeout=30)
            resp.raise_for_status()
        cert = x509.load_der_x509_certificate(resp.content)
        intermediate_pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    if not bundle.exists() or bundle.stat().st_mtime < intermediate_pem.stat().st_mtime:
        bundle.write_bytes(Path(certifi.where()).read_bytes() + b"\n" + intermediate_pem.read_bytes())

    return str(bundle)
