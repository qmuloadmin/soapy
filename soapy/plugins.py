from abc import ABC, abstractmethod

from soapy.client import Client


class Doctor(ABC):

    @abstractmethod
    def __call__(self, client: Client, request_xml: str) -> str:

        """ The doctor is called when provided to the Client.__call__, just before the
        actual web service call is performed. __call__ should return the modified
        xml envelope which will then be sent to the remote service """

