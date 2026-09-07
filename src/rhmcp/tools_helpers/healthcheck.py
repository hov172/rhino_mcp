"""Container liveness probe with certificate and hostname verification."""
import os
import socket
import ssl


def main() -> int:
    cert = os.environ.get('RHINO_MCP_HTTP_TLS_CERT')
    hostname = os.environ.get('RHINO_MCP_HTTP_TLS_SERVER_NAME', 'localhost')
    with socket.create_connection(('127.0.0.1', 8000), timeout=3) as connection:
        stream = connection
        if cert:
            context = ssl.create_default_context(cafile=os.environ.get('RHINO_MCP_HTTP_TLS_CA') or cert)
            stream = context.wrap_socket(connection, server_hostname=hostname)
        try:
            stream.sendall(f'GET /health HTTP/1.1\r\nHost: {hostname}\r\nConnection: close\r\n\r\n'.encode('ascii'))
            status = stream.makefile('rb').readline(1024).split()
            return 0 if len(status) > 1 and status[1] == b'200' else 1
        finally:
            if stream is not connection:
                stream.close()


if __name__ == '__main__':
    raise SystemExit(main())
