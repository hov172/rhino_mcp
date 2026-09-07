"""Build the locked cryptography for Intel macOS from verified sources.

Upstream no longer publishes Intel wheels. Keep this build separate from the
application's runtime installation and preserve provenance and native notices.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request

OPENSSL_VERSION = '3.6.4'
OPENSSL_OPTIONS = ['no-shared', 'no-module', 'no-tests']
OPENSSL_SHA256 = '9bffaa1ad1e07b354c21bd3324ec02fa15579f45a7d0494b3e74bc449b7333ef'


def run(args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def download(url, digest, target):
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError('Source checksum mismatch')
    target.write_bytes(data)
    with tarfile.open(target) as archive:
        archive.extractall(target.parent, filter='data')


def build(python, wheelhouse):
    root = Path(__file__).resolve().parent.parent
    entry = next(p for p in tomllib.loads((root/'uv.lock').read_text())['package'] if p['name']=='cryptography')
    version = entry['version']
    digest = entry['sdist']['hash'].split(':')[1]
    wheelhouse = Path(wheelhouse).resolve()
    wheelhouse.mkdir(parents=True, exist_ok=True)
    record = wheelhouse/'cryptography-intel-provenance.json'
    if record.exists():
        previous = json.loads(record.read_text())
        wheel = wheelhouse/previous['wheel']
        if (previous['source_sha256']==digest and previous['openssl_sha256']==OPENSSL_SHA256
                and previous.get('openssl_options') == OPENSSL_OPTIONS
                and (wheelhouse/'OPENSSL-LICENSE.txt').is_file()
                and wheel.is_file() and hashlib.sha256(wheel.read_bytes()).hexdigest()==previous['wheel_sha256']):
            print('Verified cached Intel wheel:', wheel.name)
            return wheel
    with tempfile.TemporaryDirectory(prefix='rhmcp-intel-crypto-') as tmp:
        staging = Path(tmp)
        download(entry['sdist']['url'], digest, staging/'cryptography.tar.gz')
        download(f'https://www.openssl.org/source/openssl-{OPENSSL_VERSION}.tar.gz', OPENSSL_SHA256, staging/'openssl.tar.gz')
        openssl = staging/f'openssl-{OPENSSL_VERSION}'
        prefix = staging/'openssl-static'
        run(['./Configure', 'darwin64-x86_64-cc', *OPENSSL_OPTIONS, f'--prefix={prefix}'], cwd=openssl)
        run(['make', '-j8'], cwd=openssl)
        run(['make', 'install_sw'], cwd=openssl)
        run(['rustup', 'target', 'add', 'x86_64-apple-darwin'])
        run([python, '-m', 'venv', str(staging/'venv')])
        build_python = str(staging/'venv/bin/python')
        run([build_python, '-m', 'pip', 'install', 'maturin==1.15.0', 'cffi==2.0.0', 'setuptools==82.0.0'])
        # A signed host Python may require even build-only extensions to have
        # an ad-hoc signature. This touches only the disposable build venv.
        for native in (staging/'venv').rglob('*.so'):
            run(['codesign', '--force', '--sign', '-', str(native)])
        env = dict(os.environ, OPENSSL_DIR=str(prefix), OPENSSL_STATIC='1',
                   CARGO_BUILD_TARGET='x86_64-apple-darwin', MACOSX_DEPLOYMENT_TARGET='13.0',
                   ARCHFLAGS='-arch x86_64', PATH=str(staging/'venv/bin') + os.pathsep + os.environ['PATH'])
        run([build_python, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
             '--config-settings=build-args=--locked', '--wheel-dir', str(wheelhouse),
             str(staging/f'cryptography-{version}')], env=env)
        wheel = next(wheelhouse.glob(f'cryptography-{version}-*x86_64.whl'))
        run([build_python, '-m', 'pip', 'install', '--no-deps', '--force-reinstall', str(wheel)])
        # A relocated installation must not need modules from the build prefix.
        run([build_python, '-Werror', '-c',
             'from cryptography.hazmat.backends.openssl.backend import backend; '
             'from cryptography.hazmat.primitives.ciphers.aead import AESGCM; '
             'a=AESGCM(AESGCM.generate_key(bit_length=128)); '
             'assert a.decrypt(b"0"*12,a.encrypt(b"0"*12,b"portable",None),None)==b"portable"; '
             'print(backend.openssl_version_text())'],
            env=dict(env, OPENSSL_MODULES=str(staging/'missing-modules')))
        (wheelhouse/'OPENSSL-LICENSE.txt').write_bytes((openssl/'LICENSE.txt').read_bytes())
        record.write_text(json.dumps({'version': version, 'source_sha256': digest,
                                      'openssl_version': OPENSSL_VERSION, 'openssl_sha256': OPENSSL_SHA256,
                                      'openssl_options': OPENSSL_OPTIONS,
                                      'wheel': wheel.name, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest()}, indent=2))
        return wheel


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
