import os
import time

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from soapy import Log
from soapy.wsdl.element import *
from soapy.wsdl.model import *
from soapy.wsdl.types import *


class Wsdl(Log):
    """ Class reads in WSDL and forms various child objects held together by this parent class
    Which essentially converts wsdl objects inside 'definitions' into Python native objects """

    def __init__(self, wsdl_location, tracelevel=1, **kwargs):

        """ wsdl_location is FQDN and URL of WSDL, must include protocol, e.g. http/file
        If caching behavior is desired (to load native python objects instead of parsing
        the XML each time, then provide keyword args of cache=FH where FH is a file handle """

        super().__init__(tracelevel)

        keys = kwargs.keys()

        if "username" in keys:
            self.username = kwargs["username"]
            self.password = kwargs["password"]
        if "proxyUrl" in keys:
            self.proxyUrl = kwargs["proxyUrl"]
        if "proxyUser" in keys:
            self.proxyUser = kwargs["proxyUser"]
        if "proxyPass" in keys:
            self.proxyPass = kwargs["proxyPass"]

        # Determine how to load the WSDL, is it a web resource, or a local file?

        if wsdl_location.startswith("file://"):
            wsdl_location = wsdl_location.replace("file://", "")
            with open(wsdl_location) as in_file:
                with open(self.wsdlFile, "w") as out_file:
                    for line in in_file:
                        out_file.write(line)
        elif wsdl_location.startswith("http://"):
            self._downloadWsdl(wsdl_location)
        elif wsdl_location.startswith("https://"):
            self._downloadWsdl(wsdl_location)
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
            def importSchemas(schema):
                imports = schema("import", recursive=False)
                for each in imports:
                    try:
                        schemaSoup = self._downloadSchema(each["schemaLocation"])
                        for addSchema in schemaSoup("schema", recursive=False):
                            schemas.append(Schema(addSchema, self, None, False))
                            importSchemas(addSchema)
                    except KeyError:
                        """ Assume (for now) that it's a local schema being imported into this one """
                        # TODO update this logic to be more robust

            types = self.wsdl('types', recursive=False)[0]
            schemas = list()
            for schema in types('schema', recursive=False):
                schemas.append(Schema(schema, self))
                importSchemas(schema)

            self.__schemas = tuple(schemas)
            return self.__schemas

    @property
    def namespace(self) -> Namespace:
        try:
            return self.__namespace
        except AttributeError:
            self.__namespace = Namespace(self.wsdl, self.log)
            return self.__namespace

    def _downloadWsdl(self, url):

        """ Downloads a WSDL from a remote location, attempting to account for proxy,
        then saves it to the proper filename for reading """

        wsdlText = requests.get(url).text
        with open(self.wsdlFile, "w") as f:
            f.write(wsdlText)

    def _downloadSchema(self, url) -> Tag:

        self.log("Importing schema from url: {0}".format(url), 5)
        response = requests.get(url)
        schema = BeautifulSoup(response.text, "xml")
        return schema

    def __str__(self):
        return self.wsdl.prettify()

    def typeFactory(self, element, schema) -> Element:

        """ Factory that creates the appropriate EnvClass based on bsElement tag """

        try:
            isLocal = schema.isLocal
        except AttributeError:
            isLocal = True

        if element.name == "element":
            return TypeElement(element, self, schema, isLocal)
        elif element.name == "complexType":
            return ComplexType(element, self, schema, isLocal)
        elif element.name == "sequence":
            return SequenceType(element, self, schema, isLocal)
        elif element.name == "attribute" or element.name == "enumeration":
            return None
        elif element.name == "complexContent":
            return ComplexContent(element, self, schema, isLocal)
        elif element.name == "extension" or element.name == "restriction":
            return Extension(element, self, schema, isLocal)
        elif element.name == "simpleContent":
            return SimpleContent(element, self, schema, isLocal)
        elif element.name == "simpleType":
            return SimpleType(element, self, schema, isLocal)
        else:
            raise NotImplementedError("XML Element Type <{0}> not yet implemented".format(element.name))

    def _findNamespace(self, ns) -> str:
        self.log("Searching for namespace with id '{0}' in all locations".format(ns), 5)
        try:
            targetNs = self.namespace.resolveNamespace(ns)
            self.log("Found namespace defined in Definitions: {0}".format(targetNs), 5)
        except KeyError:
            for schema in self.schemas:
                try:
                    targetNs = schema.namespace.resolveNamespace(ns)
                    self.log("Found namespace defined in schema: {0}".format(targetNs), 5)
                    break
                except KeyError:
                    pass
        try:
            return targetNs
        except UnboundLocalError:
            """ There is a bug with bs4, where XML namespaces get consolidated, but ns: components of
            attributes do not get updated with the consolidated value. As a result, we actually can't
            identify -exactly- where this element belongs, as we can't resolve the ns tag. So, we just
            return None here and all schemas will be searched, using the first match. """
            return None

    def findTypeByName(self, name, targetNs='') -> Element:

        """ Given a name, find the type and schema object
         The name should include the namespace as bs4 provides """

        # With XSD imports, things can get confusing. Lxml consolidates namespaces from schemas defined
        # in the physical wsdl file into the definitions, but imported schemas do not get consolidated.
        # As a result, we need to take care where we search for ns identifiers versus definitions.

        # If no identifier is provided, then we know it must be in the targetNs provided. If targetNs is not
        # provided, then it's defined within the Wsdl definitions, or in a local schema not in the imported schemas.

        self.log("Searching for type with name {0} in namespace {1}".format(name, targetNs), 5)
        try:
            ns, name = name.split(":")
        except ValueError:
            ns = None

        if (not targetNs) and ns is not None:
            targetNs = self._findNamespace(ns)

        # If targetNs and an identifier are provided, then we need to resolve the ns using the schema with the targetNs
        # and see if the identifier equals the targetNs. If not, or if the schema does not contain the definition,
        # we need to look elsewhere.

        elif targetNs and ns is not None:
            for schema in self.schemas:
                if schema.name == targetNs:
                    if not schema.isLocal:
                        if schema.namespace.resolveNamespace(ns) == targetNs:
                            self.log("Remote type with ns of '{0}' confirmed to be defined in parent schema"
                                     .format(ns), 5)
                        else:
                            targetNs = self._findNamespace(ns)
                    else:
                        targetNs = self._findNamespace(ns)
                    break

        self.log("Type resides in namespace of {0}".format(targetNs), 5)
        for schema in self.schemas:
            if schema.name == targetNs:
                self.log("Found schema matching namespace of {0}:{1}".format(ns, schema.name), 5)
                tags = schema.bsElement("", {"name": name}, recursive=False)
                if len(tags) > 0:
                    return self.typeFactory(tags[0], schema)
            elif targetNs is None:
                self.log("Unable to identify target namepsace! This is probably due to a bug in underlying modules. "
                         + "First global match will be used", 1)
                tags = schema.bsElement("", {"name": name}, recursive=False)
                if len(tags) > 0:
                    return self.typeFactory(tags[0], schema)

        self.log("Unable to find Type based on name {0}".format(name), 2)
        return None
