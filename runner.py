import http.client, ssl
import os
import json
import threading
import xml.etree.ElementTree as ET
from queue import Queue


BASIC_AUTH = os.getenv('BASIC_AUTH')
CLIENT_ID = os.getenv('CLIENT_ID')

# Объявим namespaces, т.к. мы в основном будем работать с XML
ns = {
    'es': 'http://model.tfido.escrow.sbrf.ru'
}


def receive_response_as_text(connection):
    response = connection.getresponse()
    response_bytes = response.read()
    response_text = response_bytes.decode("utf-8")
    if response.status / 100 == 2:  # 2xx codes only
        hs = response.headers
        remaining = hs.get('x-ratelimit-remaining')
        limit = hs.get('x-ratelimit-limit')
        print(f'Tariff: {remaining}/{limit}')
        return response_text, response.status
    else:
        raise Exception(response_text)


class IndividualTermsStatusThreadedPolling(threading.Thread):

    def __init__(self, queue, api_client_id, api_token, ssl_ctx):
        threading.Thread.__init__(self)
        self.queue = queue
        self.conn = http.client.HTTPSConnection(host="api.sberbank.ru", context=ssl_ctx)
        self.token = api_token
        self.api_client_id = api_client_id

    def run(self):
        while True:
            uuid = self.queue.get()
            self.status(uuid)
            self.queue.task_done()

    def status(self, uuid):
        hs = {
            'x-ibm-client-id': f'{self.api_client_id}',
            'authorization': f'Bearer {self.token}',
            'x-introspect-rquid': '784d2386006a49afa0e6d9e0e4001105',
        }
        location = f'individual-terms/{uuid}'
        self.conn.request("GET", f'/ru/prod/v2/escrow/{location}/status', headers=hs)
        r, s = receive_response_as_text(self.conn)
        print(f'\n{s}\n{r}')


# настройка TLS
ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
ctx.verify_mode = ssl.CERT_NONE

# Загружаем файлы ключа и сертификаты для TLS в формате PEM (текстовый)
ctx.load_cert_chain(
    certfile=f'{CLIENT_ID}.crt',
    keyfile=f'{CLIENT_ID}.key'
)
conn = http.client.HTTPSConnection(host="api.sberbank.ru", context=ctx)

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
token, status = receive_response_as_text(conn)
token = json.loads(token)
token = token['access_token']
print(f'Token id = {token}')

# Получение ЖК
headers = {
    'x-ibm-client-id': f'{CLIENT_ID}',
    'authorization': f'Bearer {token}',
    'x-introspect-rquid': "784d2386006a49afa0e6d9e0e4001101",
    'accept': "application/xml"
}

conn.request("GET", "/ru/prod/v2/escrow/residential-complex", headers=headers)
rc, _ = receive_response_as_text(conn)
print(rc)
root = ET.fromstring(rc)
for base_info in root.findall('es:authorizedRepresentative/es:baseInfo', ns):
    last_name = base_info.find('es:lastName', ns).text
    cert = base_info.find('es:certificateSerial', ns)
    if cert is not None:
        print(f'---> {last_name} -> {cert.text}')

# Получение драфта ИУ
headers = {
    'x-ibm-client-id': f'{CLIENT_ID}',
    'authorization': f'Bearer {token}',
    'x-introspect-rquid': "784d2386006a49afa0e6d9e0e4001103",
    'content-type': "application/x-www-form-urlencoded",
    'accept': "application/xml"
}
payload = "escrowAmount=2000&depositorLastName=Иванов&depositorFirstName=Иван" \
          "&depositorRegistrationAddress=АдрРегистрации&depositorCurrentAddress=АдрРегистрации" \
          "&depositorIdentificationDocumentType=99&depositorIdentificationDocumentNumber=12345678" \
          "&depositorIdentificationDocumentIssuer=ОВД%209911&depositorIdentificationDocumentIssueDate=2000-01-01" \
          "&depositorPhone=900-000-00-00&beneficiaryTaxId=0012345688" \
          "&beneficiaryAuthorizedRepresentativeCertificateSerial=d3KbBnl4fjAG0A==" \
          "&equityParticipationAgreementNumber=Д123&equityParticipationAgreementDate=2020-10-10" \
          "&estateObjectCommisioningObjectCode=0001&estateObjectType=RESIDENTIAL&estateObjectConstructionNumber=513"

conn.request("POST", "/ru/prod/v2/escrow/individual-terms/draft", payload.encode('utf-8'), headers)
rc, status = receive_response_as_text(conn)
print(rc)

# Получение списка счетов
headers = {
    'x-ibm-client-id': f'{CLIENT_ID}',
    'authorization': f'Bearer {token}',
    'x-introspect-rquid': "784d2386006a49afa0e6d9e0e4001102",
    'content-type': "application/x-www-form-urlencoded",
    'accept': "application/xml"
}
payload = "commisioningObjectCode=0001&startReportDate=2020-08-20&endReportDate=2020-08-22&limit=1000&offset=0"
conn.request("POST", "/ru/prod/v2/escrow/account-list", payload, headers)
rc, _ = receive_response_as_text(conn)
print(rc)

# Получение списка операций по счетам
headers = {
    'x-ibm-client-id': f'{CLIENT_ID}',
    'authorization': f'Bearer {token}',
    'x-introspect-rquid': "784d2386006a49afa0e6d9e0e4001102",
    'content-type': "application/x-www-form-urlencoded",
    'accept': "application/xml"
}
payload = "commisioningObjectCode=0001&startReportDate=2020-08-20&endReportDate=2020-09-22&limit=1000&offset=0"
conn.request("POST", "/ru/prod/v2/escrow/account-oper-list", payload, headers)
rc, _ = receive_response_as_text(conn)
print(rc)

# Получение ИУ
headers = {
    'x-ibm-client-id': f'{CLIENT_ID}',
    'authorization': f'Bearer {token}',
    'x-introspect-rquid': '784d2386006a49afa0e6d9e0e4001105',
}
ind_trm_location = 'individual-terms/00000000-0044-ae1b-0000-00000044ae1b'
conn.request("GET", f"/ru/prod/v2/escrow/{ind_trm_location}", headers=headers)
rc, _ = receive_response_as_text(conn)
print(rc)

queue = Queue()

for i in range(5):
    worker = IndividualTermsStatusThreadedPolling(queue, CLIENT_ID, token, ctx)
    worker.setDaemon(True)
    worker.start()

for url in range(10):
    queue.put("00000000-0044-ae1b-0000-00000044ae1b")

queue.join()
