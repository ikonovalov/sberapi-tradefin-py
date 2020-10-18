import http.client, ssl
import os
import json
import xml.etree.ElementTree as ET

def receive_response_as_text(connection):
    response = connection.getresponse()
    response_bytes = response.read()
    response_text = response_bytes.decode("utf-8")
    return response_text

BASIC_AUTH = os.getenv('BASIC_AUTH')
CLIENT_ID = os.getenv('CLIENT_ID')

# настройка TLS
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.verify_mode = ssl.CERT_NONE
# Загружаем файлы ключа и сертификаты для TLS в формате PEM (текстовый)
context.load_cert_chain(certfile=f'{CLIENT_ID}.crt', keyfile=f'{CLIENT_ID}.key')
conn = http.client.HTTPSConnection(host="api.sberbank.ru", context=context)

# получение Token
payload = "grant_type=client_credentials&scope=https://api.sberbank.ru/escrow"
headers = {
    'x-ibm-client-id': f'{CLIENT_ID}',
    'authorization': f'Basic {BASIC_AUTH}',
    'rquid': "784d2386006a49afa0e6d9e0e4001100",
    'content-type': "application/x-www-form-urlencoded",
    'accept': "application/json"
}

conn.request("POST", "/ru/prod/tokens/v2/oauth", payload, headers)
token = receive_response_as_text(conn)
token = json.loads(token)
token = token['access_token']
print(f'Token id = {token}')


headers = {
    'x-ibm-client-id':  f'{CLIENT_ID}',
    'authorization': f'Bearer {token}',
    'x-introspect-rquid': "784d2386006a49afa0e6d9e0e4001101",
    'accept': "application/xml"
}

conn.request("GET", "/ru/prod/v2/escrow/residential-complex", headers = headers)
rc = receive_response_as_text(conn)
print(rc)
root = ET.fromstring(rc)
ns = '{http://model.tfido.escrow.sbrf.ru}'
for certs in root.findall(f'{ns}authorizedRepresentative/{ns}baseInfo/{ns}certificateSerial'):
    print(certs.text)
