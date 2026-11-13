"""Gera um certificado HTTPS interno para o computador que hospedará o SIRIO."""
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
import socket
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


PASTA = Path(__file__).resolve().parent
DESTINO = PASTA / "certificados"
CHAVE = DESTINO / "sirio-chave-privada.pem"
CERT_PEM = DESTINO / "sirio-certificado.pem"
CERT_PUBLICO = DESTINO / "sirio-certificado.cer"


def ip_local():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conexao:
            conexao.connect(("8.8.8.8", 80))
            return conexao.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main():
    substituir = "--substituir" in sys.argv
    if (CHAVE.exists() or CERT_PEM.exists()) and not substituir:
        raise SystemExit("Já existe um certificado. Use --substituir somente ao trocar de servidor/IP.")
    DESTINO.mkdir(exist_ok=True)
    host, ip = socket.gethostname(), ip_local()
    chave = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    nome = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SIRIO - Uso Interno"),
        x509.NameAttribute(NameOID.COMMON_NAME, host),
    ])
    certificado = (x509.CertificateBuilder()
        .subject_name(nome).issuer_name(nome).public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1095))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"), x509.DNSName(host),
            x509.IPAddress(ip_address("127.0.0.1")), x509.IPAddress(ip_address(ip)),
        ]), critical=False)
        # É uma autoridade interna autoassinada: clientes precisam poder
        # confiá-la (inclusive Firefox, que rejeita certificado de servidor
        # comum importado como autoridade). Continua restrita aos nomes/IPs
        # expressos no SAN acima.
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=True,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .sign(chave, hashes.SHA256()))
    CHAVE.write_bytes(chave.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    CERT_PEM.write_bytes(certificado.public_bytes(serialization.Encoding.PEM))
    CERT_PUBLICO.write_bytes(certificado.public_bytes(serialization.Encoding.DER))
    print(f"Certificado criado para https://{ip}:8377 (válido até {certificado.not_valid_after_utc.date()}).")
    print("Instale somente certificados\\sirio-certificado.cer nos computadores clientes.")


if __name__ == "__main__":
    main()
