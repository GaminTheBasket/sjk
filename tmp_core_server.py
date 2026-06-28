import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class CoreHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(length).decode('utf-8')
        print('CORE RECEIVED', self.path, data)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, format, *args):
        return

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8001), CoreHandler)
    print('Core mock listening on http://127.0.0.1:8001')
    server.serve_forever()
