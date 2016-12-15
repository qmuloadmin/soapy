from abc import ABC, abstractmethod, abstractproperty
from soapy import Log
from soapy.client import Client


class Doctor(ABC, Log):

    def __init__(self, tl=-1):
        super().__init__(tl)

    @abstractmethod
    def __call__(self, client: Client, request_xml: str, tl=-1) -> str:

        """ The doctor is called when provided to the Client.__call__, just before the
        actual web service call is performed. __call__ should return the modified
        xml envelope which will then be sent to the remote service """

        self.tl = tl
