#!/usr/bin/env python3

"""
    A helper tool to deal with HPKP configuration and certificates.
    Usefull if you use Let's Encrypt certificates.

    Luis González Fernández (luisgf@luisgf.es)
    17/02/2016
"""

__VERSION__ = 'v0.2'

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from hashlib import sha256
from base64 import b64encode
from datetime import datetime, timedelta
from optparse import OptionParser

parser = OptionParser()

parser.add_option("-f","--file", dest="file_path", metavar="FILE",
                   help="Certificate file path to calculate HPKP pin.")
parser.add_option("-e","--encoding", dest="encoding", type="choice",
                  choices=['PEM','DER'], default='PEM',
                  help="Certificate format encoding. [PEM|DER]")
parser.add_option("-u","--url", dest="report_uri", default=None,
                  help="The report URI to upload pin check errors")
parser.add_option("-d","--subdomains", dest="subdomains", action="store_true",
                  help="Include Subdomains")
parser.add_option("-s","--show", action="store_true",
                  help="Show the expiration date-time for the pin and duration")

# Configure your root and backups certificates here. Will be added at the end
# of the pin.

ROOT_CERTS = [('letsencrypt_ca/isrgrootx1.pem', Encoding.PEM),
              ('letsencrypt_ca/dst_x3.pem', Encoding.PEM),
              ('letsencrypt_ca/letsencryptauthorityx1.pem', Encoding.PEM),
              ('letsencrypt_ca/letsencryptauthorityx2.pem', Encoding.PEM)]

class HPKPPinGenerator():
    """Class implementing an HPKP Pin generator"""

    def __init__(self, cert_data, cert_type=Encoding.PEM):

        if cert_type is Encoding.PEM:
            self.cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        elif cert_type is Encoding.DER:
            self.cert = x509.load_der_x509_certificate(cert_data, default_backend())
        else:
            raise Exception('Certificate format not implemented yet')

        # Compute the max PIN ttl
        self.pin_ttl = int((self.cert.not_valid_after -
                        datetime.today()).total_seconds())

    def get_pin(self):
        """ HPKP pins are calculated over the public key of a certificate.
        This function return the pin for the current certificate"""

        pub_bytes =  self.cert.public_key().public_bytes(encoding=Encoding.DER,
                                                   format=PublicFormat.SubjectPublicKeyInfo)
        digest = sha256(pub_bytes).digest()

        return b64encode(digest).decode('utf-8')

def apache_directive(pin_ttl, pin_list=[], report_uri=None, subdomains=True):
    """Return the Apache directive needed to add in http.conf to enable
    HPKP"""

    directive = 'Header always set Public-Key-Pins "'

    for pin in pin_list:
        directive += 'pin-sha256=\\"%s\\"; ' % pin

    directive += 'max-age=%d' % pin_ttl

    if subdomains:
        directive += '; includeSubdomains'

    if report_uri:
        directive += '; report-uri=\\"%s\\"' % report_uri

    directive += '"'

    return directive

if __name__ == '__main__':
    """
        Generate HPKP Pins and print at screen the Apache directive
        needed to make it's works.

        CERTS is a list containing tuples (crt_file_path, crt_encoding)

        crt_encoding may be any of the types defined at:

            cryptography.hazmat.primitives.serialization.Encoding

        Be sure to add the root CA and a backup certificate from another CA
    """
    (options, args) = parser.parse_args()

    if not options.file_path:
        raise Exception('Missing leaf certificate')

    if options.encoding == 'PEM':
        leaf_enc = Encoding.PEM
    elif options.encoding == 'DER':
        leaf_enc = Encoding.DER

    pin_list = []

    leaf_cert = options.file_path
    report_uri = options.report_uri
    subdomains = options.subdomains

    # Compute the pin for the leaf certificate
    with open(leaf_cert,'rb') as f:
        cert_data = f.read()
        hpkp = HPKPPinGenerator(cert_data, leaf_enc)
        pin_list.append(hpkp.get_pin())
        pin_ttl = hpkp.pin_ttl

        if options.show:
            print('Pin will expire at %s. Be sure to update it at time' %
              str(hpkp.cert.not_valid_after))

    for (cert_file, cert_encoding) in ROOT_CERTS:
        with open(cert_file,'rb') as f:
            cert_data = f.read()
            hpkp = HPKPPinGenerator(cert_data, cert_encoding)
            pin_list.append(hpkp.get_pin())

    print(apache_directive(pin_ttl, pin_list, report_uri, subdomains))
