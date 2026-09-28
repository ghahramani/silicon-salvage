"""Restore the approved web root password through the router's local ACS interface."""
import json
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

credentials = json.loads(Path(__file__).with_name('credentials.json').read_text())
password = credentials['password']
assert len(password) == 12 and all((any(c.isupper() for c in password),
    any(c.islower() for c in password), any(c.isdigit() for c in password),
    any(not c.isalnum() for c in password)))
phase = 'identify'
namespace = 'urn:dslforum-org:cwmp-1-0'

def local(tag):
    return tag.rsplit('}', 1)[-1]

def soap(body, message_id='root-recovery'):
    return ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:c="' + namespace + '" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:enc="http://schemas.xmlsoap.org/soap/encoding/">'
        '<s:Header><c:ID s:mustUnderstand="1">' + escape(message_id) + '</c:ID></s:Header>'
        '<s:Body>' + body + '</s:Body></s:Envelope>').encode()

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def reply(self, code, body=b''):
        self.send_response(code)
        self.send_header('Content-Type', 'text/xml; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global phase, namespace
        size = int(self.headers.get('Content-Length', '0'))
        if size > 1048576:
            self.reply(413)
            return
        data = self.rfile.read(size)
        if not data.strip():
            if phase == 'identify':
                phase = 'identity_sent'
                self.reply(200, soap('<c:GetParameterValues><ParameterNames enc:arrayType="xsd:string[2]">'
                    '<string>Device.Users.User.1.Username</string><string>Device.Users.User.1.Enable</string>'
                    '</ParameterNames></c:GetParameterValues>'))
            else:
                self.reply(204)
            return
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            self.reply(400)
            return
        inform = next((e for e in root.iter() if local(e.tag) == 'Inform'), None)
        if inform is not None:
            namespace = inform.tag[1:].split('}')[0]
            mid = next((e.text or '' for e in root.iter() if local(e.tag) == 'ID'), '')
            print('Router contacted ACS; verifying root account.', flush=True)
            self.reply(200, soap('<c:InformResponse><MaxEnvelopes>1</MaxEnvelopes></c:InformResponse>', mid))
            return
        if any(local(e.tag) == 'Fault' for e in root.iter()):
            print('Router rejected request; fault codes: ' + ','.join(e.text or '' for e in root.iter()
                  if local(e.tag) == 'FaultCode'), flush=True)
            phase = 'failed'
            self.reply(204)
            return
        if phase == 'identity_sent':
            values = {}
            for item in root.iter():
                if local(item.tag) == 'ParameterValueStruct':
                    fields = {local(c.tag): c.text or '' for c in item}
                    values[fields.get('Name')] = fields.get('Value')
            if values.get('Device.Users.User.1.Username') != 'root' or values.get('Device.Users.User.1.Enable') not in ('1', 'true'):
                print('Unexpected account identity; stopped without changes.', flush=True)
                phase = 'failed'
                self.reply(204)
                return
            phase = 'password_sent'
            print('Confirmed enabled root account; sending approved password change.', flush=True)
            self.reply(200, soap('<c:SetParameterValues><ParameterList enc:arrayType="c:ParameterValueStruct[1]">'
                '<ParameterValueStruct><Name>Device.Users.User.1.Password</Name><Value xsi:type="xsd:string">'
                + escape(password) + '</Value></ParameterValueStruct></ParameterList>'
                '<ParameterKey>local-root-recovery</ParameterKey></c:SetParameterValues>'))
            return
        if phase == 'password_sent' and any(local(e.tag) == 'SetParameterValuesResponse' for e in root.iter()):
            status = next((e.text for e in root.iter() if local(e.tag) == 'Status'), None)
            print('PASSWORD_CHANGE_STATUS=' + str(status), flush=True)
            phase = 'done'
        self.reply(204)

if __name__ == '__main__':
    print('ACS ready; only the verified web root password will be changed.', flush=True)
    HTTPServer(('192.168.77.1', 7547), Handler).serve_forever()
