from soapy import Log
from soapy.wsdl.types import *
from soapy.wsdl.model import *
from soapy.wsdl.element import Element,Schema,Namespace
import time
import os
from bs4 import BeautifulSoup
from bs4.element import Tag

class Wsdl(Log):
    """ Class reads in WSDL and forms various child objects held together by this parent class
	Which essentially converts wsdl objects inside 'definitions' into Python native objects """

    def __init__(self, wsdl_location, tracelevel=1, **kArgs):

        """ wsdl_location is FQDN and URL of WSDL, must include protocol, e.g. http/file
		If caching behavior is desired (to load native python objects instead of parsing
		the XML each time, then provide keyword args of cache=FH where FH is a file handle """

        super().__init__(tracelevel)

        # Determine how to load the WSDL, is it a web resource, or a local file?

        if wsdl_location.startswith("file://"):
            wsdl_location = wsdl_location.replace("file://", "")
            with open(wsdl_location) as in_file:
                with open(self.wsdlFile, "w") as out_file:
                    for line in in_file:
                        out_file.write(line)
        else:
            self._log("Unsupported protocol for WSDL location: {0}".format(wsdl_location), 0)
            raise ValueError("Unsupported protocol for WSDL location: {0}".format(wsdl_location))

        # TODO handle URLs with http/https

    @property
    def wsdl(self) -> Tag:
        try:
            return self.__wsdl
        except AttributeError:
            self._log('Getting root definitions of WSDL', 5)
            self.__wsdl = self.soup("definitions", recursive=False)[0]
            return self.__wsdl

    @property
    def soup(self) -> Tag:
        try:
            return self.__soup
        except AttributeError:
            self._log("Parsing WSDL file and rendering Element Tree", 5)
            with open(self.wsdlFile) as f:
                self.__soup = BeautifulSoup(f, "xml")
            os.remove(self.wsdlFile)
            return self.__soup

    @property
    def wsdlFile(self):

        """ Create a temporary file, handling overlap in the off chance it already exists """

        try:
            return self.__wsdlFile
        except AttributeError:
            self._log("Initializing wsdl file cache", 5)
            f = str(os.getpid()) + ".temp"

            if os.path.exists(f):
                f = str(time.time()) + f
            self._log("Set wsdlFile for instance to cache: {0}".format(f), 4)
            self.__wsdlFile = f
            return self.__wsdlFile

    @property
    def services(self) -> tuple:

        """ The list of services available. The list will contain soapy.Service objects """

        try:
            return self.__services
        except AttributeError:
            self._log("Initializing list of services with services defined in WSDL", 5)
            services = list()
            for service in self.wsdl('service', recursive=False):
                services.append(Service(service, self))
            self.__services = tuple(services)
            return self.__services

    @property
    def schemas(self) -> tuple:
        try:
            return self.__schemas
        except AttributeError:
            types = self.wsdl('types', recursive=False)[0]
            schemas = list()
            for schema in types('schema', recursive=False):
                schemas.append(Schema(schema, self))
            self.__schemas = tuple(schemas)
            return self.__schemas

    @property
    def namespace(self) -> Namespace:
        try:
            return self.__namespace
        except AttributeError:
            self.__namespace = Namespace(self.wsdl, self._log)
            return self.__namespace

    @staticmethod
    def __downloadWsdl(url):

        """ Downloads a WSDL from a remote location, attempting to account for proxy,
		then saves it to the proper filename for reading """

    def __str__(self):
        return self.wsdl.prettify()

    def typeFactory(self, element, schema) -> Element:

        """ Factory that creates the appropriate EnvClass based on bsElement tag """

        if element.name == "element":
            return TypeElement(element, self, schema)
        elif element.name == "complexType":
            return ComplexType(element, self, schema)
        elif element.name == "sequence":
            return SequenceType(element, self, schema)
        elif element.name == "attribute":
            return None
        else:
            raise TypeError("XML Element Type <{0}> not yet implemented".format(element.name))

    def findTypeByName(self, name) -> Element:

        """ Given a name, find the type and schema object """

        t = self.wsdl('types', recursive=False)
        ns, name = name.split(":")
        self._log("Searching all types for matching element with name {0}".format(name), 5)
        for schema in self.schemas:
            if schema.name == self.namespace.resolveNamespace(ns):
                self._log("Found schema matching namespace of {0}:{1}".format(ns,schema.name),5)
                tags = schema.bsElement("", {"name": name})
                if len(tags) > 0:
                    return self.typeFactory(tags[0], schema)
        self._log("Unable to find Type based on name {0}".format(name), 1)
        return None