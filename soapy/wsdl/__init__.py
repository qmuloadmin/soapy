import os
import time

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from soapy import Log
from soapy.wsdl.element import Element,Schema,Namespace
from soapy.wsdl.model import *
from soapy.wsdl.types import *


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
            self.log("Unsupported protocol for WSDL location: {0}".format(wsdl_location), 0)
            raise ValueError("Unsupported protocol for WSDL location: {0}".format(wsdl_location))

        # TODO handle URLs with http/https

    @property
    def wsdl(self) -> Tag:
        try:
            return self.__wsdl
        except AttributeError:
            self.log('Getting root definitions of WSDL', 5)
            self.__wsdl = self.soup("definitions", recursive=False)[0]
            return self.__wsdl

    @property
    def soup(self) -> Tag:
        try:
            return self.__soup
        except AttributeError:
            self.log("Parsing WSDL file and rendering Element Tree", 5)
            with open(self.wsdlFile) as f:
                self.__soup = BeautifulSoup(f, "xml")
            os.remove(self.wsdlFile)
            return self.__soup

    @property
    def wsdlFile(self) -> str:

        """ Create a temporary file, handling overlap in the off chance it already exists """

        try:
            return self.__wsdlFile
        except AttributeError:
            self.log("Initializing wsdl file cache", 5)
            f = str(os.getpid()) + ".temp"

            if os.path.exists(f):
                f = str(time.time()) + f
            self.log("Set wsdlFile for instance to cache: {0}".format(f), 4)
            self.__wsdlFile = f
            return self.__wsdlFile

    @property
    def services(self) -> tuple:

        """ The list of services available. The list will contain soapy.Service objects """

        try:
            return self.__services
        except AttributeError:
            self.log("Initializing list of services with services defined in WSDL", 5)
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
                imports = schema("import",recursive=False)
                for each in imports:
                    try:
                        schemaSoup = self._downloadSchema(each["schemaLocation"])
                        for addSchema in schemaSoup("schema",recursive=False):
                            schemas.append(Schema(addSchema,self))
                    except:
                        """ Assume (for now) that it's a local schema """
                        #TODO update this logic to be more robust
            self.__schemas = tuple(schemas)
            return self.__schemas

    @property
    def namespace(self) -> Namespace:
        try:
            return self.__namespace
        except AttributeError:
            self.__namespace = Namespace(self.wsdl, self.log)
            return self.__namespace

    @staticmethod
    def _downloadWsdl(url):

        """ Downloads a WSDL from a remote location, attempting to account for proxy,
        then saves it to the proper filename for reading """

    def _downloadSchema(self,url) -> Tag:
        
        self.log("Importing schema from url: {0}".format(url),5)
        response = requests.get(url)
        schema = BeautifulSoup(response.text,"xml")
        return schema

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
        elif element.name == "complexContent":
            return ComplexContent(element,self,schema)
        elif element.name == "extension":
            return Extension(element,self,schema)
        elif element.name =="simpleContent":
            return SimpleContent(element,self,schema)
        else:
            raise TypeError("XML Element Type <{0}> not yet implemented".format(element.name))

    def findTypeByName(self, name, targetNs='') -> Element:

        """ Given a name, find the type and schema object
         The name should include the namespace as bs4 provides """

        t = self.wsdl('types', recursive=False)
        try:
            ns, name = name.split(":")
            targetNs = self.namespace.resolveNamespace(ns)
        except ValueError:
            ns = "None"
        self.log("Type resides in namespace of {0}".format(targetNs),5)
        self.log("Searching all types for matching element with name {0}".format(name), 5)
        for schema in self.schemas:
            if schema.name == targetNs:
                self.log("Found schema matching namespace of {0}:{1}".format(ns,schema.name),5)
                tags = schema.bsElement("", {"name": name})
                if len(tags) > 0:
                    return self.typeFactory(tags[0], schema)
        self.log("Unable to find Type based on name {0}".format(name), 2)
        return None
