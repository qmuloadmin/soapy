import mimetypes
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from soapy.client import Client


class Doctor(ABC):

    @abstractmethod
    def __call__(self, client: Client, request_xml: str) -> str:

        """ The doctor is called when provided to the Client.__call__, just before the
        actual web service call is performed. __call__ should return the modified
        xml envelope which will then be sent to the remote service """


class SOAPAttachmentDoctor(Doctor):
    """
NOTE:  This doctor must be run LAST!

Converts the SOAP XML to a multipart/related HTTP message.

These messages have the following headers:

{'MIME-Version': '1.0', 
        'Content-Type': 'multipart/related; boundary="===============8026600963303495608=="'}

Each related part has it's own Content-Type and is separated by the bounder value in the
multipart/related content type. Notice in the content below, we have an XML and a text 
document


--===============8026600963303495608==
Content-Type: text/xml; charset="utf8"
MIME-Version: 1.0
Content-Transfer-Encoding: base64

<?xml version="1.0"?>
<tables>
        ... omitted for brevity ... 
</tables>

--===============8026600963303495608==
Content-Type: text/plain; charset="utf8"
MIME-Version: 1.0
Content-Transfer-Encoding: base64

This is some plain text! 

--===============8026600963303495608==--
    """

    def __init__(self, attachments: list):
        self.attachments = list(attachments)

    def __call__(self, client: Client, request_xml: str) -> str:

        if len(self.attachments) > 0:
            related = MIMEMultipart('related')
            # add the soap message portion
            xml = MIMEText("text", "xml")
            xml.set_payload(request_xml)
            related.attach(xml)

            for attachment in self.attachments:
                self.__add_related_item(related, attachment)
            body = related.as_string().split('\n\n', 1)[1]
            client.headers.update(dict(related.items()))
            return body
        else:
            return request_xml

    @staticmethod
    def __add_related_item(related: MIMEMultipart, item: dict):
        with open(item['file'], 'rb') as f:
            ct = mimetypes.guess_type(item['file'])[0].split('/')
            toAttach = MIMEText(*ct)
            toAttach.set_payload(f.read())
            related.attach(toAttach)
