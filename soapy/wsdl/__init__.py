import os
import time
from re import sub

import requests
from bs4 import BeautifulSoup

from soapy import Log
from soapy.wsdl.element import *
from soapy.wsdl.model import *
from soapy.wsdl.types import *


class Wsdl(Log):
    """ Class reads in WSDL and forms various child objects held together by this parent class
    Which essentially converts wsdl objects inside 'definitions' into Python native objects """

    constructor_kwargs = ("proxy_url", "proxy_user", "proxy_pass", "secure", "version")
    supported_versions = (1.1, 1.2)

    def __init__(self, wsdl_location, tracelevel=1, **kwargs):

        """ wsdl_location is FQDN and URL of WSDL, must include protocol, e.g. http/file
        If caching behavior is desired (to load native python objects instead of parsing
        the XML each time, then provide keyword args of cache=FH where FH is a file handle

        :keyword proxyUrl: The URL of the proxy to use, including port, if needed to retrieve WSDL
        :keyword proxyUser: The username, if any, to authenticate to the proxy with
        :keyword proxyPass: The password paired with the username for proxy authentication
        :keyword secure: A boolean flag, defaults to True, if SSL verification should be performed
        :keyword version: An integer representing the SOAP version (1.1 or 1.2) of the request. Default 1.1
        """

        super().__init__(tracelevel)
        self.secure = True
        self.__version = 1.1
        self.__proxy_url = ""
        self.__proxy_user = ""
        self.__proxy_pass = ""
        for each in kwargs:
            if each in self.constructor_kwargs:
                setattr(self, each, kwargs[each])
            else:
                raise ValueError("Unexpected keyword argument for {} initializer, {}".format(self.__name__, each))

        # Determine how to load the WSDL, is it a web resource, or a local file?

        if wsdl_location.startswith("file://"):
            wsdl_location = wsdl_location.replace("file://", "")
            with open(wsdl_location) as in_file:
                with open(self.wsdlFile, "w") as out_file:
                    for line in in_file:
                        out_file.write(line)
        elif wsdl_location.startswith("http://"):
            self._download_wsdl(wsdl_location)
        elif wsdl_location.startswith("https://"):
            self._download_wsdl(wsdl_location)
        else:
            self.log("Unsupported protocol for WSDL location: {0}".format(wsdl_location), 0)
            raise ValueError("Unsupported protocol for WSDL location: {0}".format(wsdl_location))

    @property
    def version(self) -> int:
        return self.__version

    @version.setter
    def version(self, ver):
        if float(ver) not in self.supported_versions:
            raise ValueError("Supported versions include only {}. Invalid version specified: {}"
                             .format(self.supported_versions, ver))
        self.__version = float(ver)

    @property
    def proxy_url(self) -> str:
        return self.__proxy_url

    @proxy_url.setter
    def proxy_url(self, url: str):
        self.__proxy_url = url
        if not url.startswith("http"):
            # If http/https not specified, assume http
            self.__proxy_url = "http://" + url
        if self.__proxy_pass != "" and self.__proxy_user != "":
            self._replace_pxy()

    @property
    def proxy_user(self) -> str:
        return self.__proxy_user

    @proxy_user.setter
    def proxy_user(self, user: str):
        self.log("Setting the proxy user to '{}'".format(user), 5)
        self.__proxy_user = user
        if self.__proxy_pass != "" and self.__proxy_url != "":
            self._replace_pxy()

    @property
    def proxy_pass(self) -> str:
        return self.__proxy_pass

    @proxy_pass.setter
    def proxy_pass(self, p: str):
        self.log("Setting the proxy password with provided value".format(p), 5)
        self.__proxy_pass = p
        if self.__proxy_user != "" and self.__proxy_url != "":
            self._replace_pxy()

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
            def import_schemas(schema):
                imports = schema("import", recursive=False)
                for each in imports:
                    try:
                        schema_soup = self._download_schema(each["schemaLocation"])
                        for addSchema in schema_soup("schema", recursive=False):
                            schemas.append(Schema(addSchema, self, None, False))
                            import_schemas(addSchema)
                    except KeyError:
                        """ Assume (for now) that it's a local schema being imported into this one """
                        # TODO update this logic to be more robust

            types = self.wsdl('types', recursive=False)[0]
            schemas = list()
            for schema in types('schema', recursive=False):
                schemas.append(Schema(schema, self))
                import_schemas(schema)

            self.__schemas = tuple(schemas)
            return self.__schemas

    @property
    def namespace(self) -> Namespace:
        try:
            return self.__namespace
        except AttributeError:
            self.__namespace = Namespace(self.wsdl, self.log)
            return self.__namespace

    def _replace_pxy(self):
        self.log("Building proxy URL with credentials", 5)
        self.__proxy_url = sub(r"(https?://)(\w)",
                               r"\1{}:{}@\2".format(self.__proxy_user, self.__proxy_pass),
                               self.__proxy_url)

    def _download_wsdl(self, url):

        """ Downloads a WSDL from a remote location, attempting to account for proxy,
        then saves it to the proper filename for reading """
        proxies = {}
        if self.proxy_url != "":
            self.log("Setting proxy to {}".format(self.proxy_url.replace(self.__proxy_pass, "***")), 5)
            proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }
        self.log("Downloading WSDL file from {}".format(url), 4)
        wsdlText = requests.get(url, verify=self.secure, proxies=proxies).text
        with open(self.wsdlFile, "w") as f:
            f.write(wsdlText)

    def _download_schema(self, url) -> Tag:

        self.log("Importing schema from url: {0}".format(url), 5)
        response = requests.get(url, verify=self.secure)
        schema = BeautifulSoup(response.text, "xml")
        return schema

    def __str__(self):
        return self.wsdl.prettify()

    def type_factory(self, element, schema) -> Element:

        """ Factory that creates the appropriate EnvClass based on bsElement tag """

        try:
            is_local = schema.is_local
        except AttributeError:
            is_local = True

        if element.name == "element":
            return TypeElement(element, self, schema, is_local)
        elif element.name == "complexType":
            return ComplexType(element, self, schema, is_local)
        elif element.name == "sequence":
            return SequenceType(element, self, schema, is_local)
        elif element.name == "attribute" or element.name == "enumeration":
            return None
        elif element.name == "complexContent":
            return ComplexContent(element, self, schema, is_local)
        elif element.name == "extension" or element.name == "restriction":
            return Extension(element, self, schema, is_local)
        elif element.name == "simpleContent":
            return SimpleContent(element, self, schema, is_local)
        elif element.name == "simpleType":
            return SimpleType(element, self, schema, is_local)
        else:
            raise NotImplementedError("XML Element Type <{0}> not yet implemented".format(element.name))

    def _find_namespace(self, ns) -> str:
        self.log("Searching for namespace with id '{0}' in all locations".format(ns), 5)
        try:
            target_ns = self.namespace.resolve_namespace(ns)
            self.log("Found namespace defined in Definitions: {0}".format(target_ns), 5)
        except KeyError:
            for schema in self.schemas:
                try:
                    target_ns = schema.namespace.resolve_namespace(ns)
                    self.log("Found namespace defined in schema: {0}".format(target_ns), 5)
                    break
                except KeyError:
                    pass
        try:
            return target_ns
        except UnboundLocalError:
            """ There is a bug with bs4, where XML namespaces get consolidated, but ns: components of
            attributes do not get updated with the consolidated value. As a result, we actually can't
            identify -exactly- where this element belongs, as we can't resolve the ns tag. So, we just
            return empty string here and all schemas will be searched, using the first match. """
            return ""

    def find_type_by_name(self, name, target_ns='') -> Element:

        """ Given a name, find the type and schema object
         The name should include the namespace as bs4 provides """

        # With XSD imports, things can get confusing. Lxml consolidates namespaces from schemas defined
        # in the physical wsdl file into the definitions, but imported schemas do not get consolidated.
        # As a result, we need to take care where we search for ns identifiers versus definitions.

        # If no identifier is provided, then we know it must be in the targetNs provided. If targetNs is not
        # provided, then it's defined within the Wsdl definitions, or in a local schema not in the imported schemas.

        self.log("Searching for type with name {0} in namespace {1}".format(name, target_ns), 5)
        try:
            ns, name = name.split(":")
        except ValueError:
            ns = None

        if (not target_ns) and ns is not None:
            target_ns = self._find_namespace(ns)

        # If targetNs and an identifier are provided, then we need to resolve the ns using the schema with the targetNs
        # and see if the identifier equals the targetNs. If not, or if the schema does not contain the definition,
        # we need to look elsewhere.

        elif target_ns and ns is not None:
            for schema in self.schemas:
                if schema.name == target_ns:
                    if not schema.is_local:
                        if schema.namespace.resolve_namespace(ns) == target_ns:
                            self.log("Remote type with ns of '{0}' confirmed to be defined in parent schema"
                                     .format(ns), 5)
                        else:
                            target_ns = self._find_namespace(ns)
                    else:
                        target_ns = self._find_namespace(ns)
                    break

        self.log("Type resides in namespace of {0}".format(target_ns), 5)
        for schema in self.schemas:
            if schema.name == target_ns:
                self.log("Found schema matching namespace of {0}:{1}".format(ns, schema.name), 5)
                tags = schema.bs_element("", {"name": name}, recursive=False)
                if len(tags) > 0:
                    return self.type_factory(tags[0], schema)
            elif not target_ns:
                self.log("Unable to identify target namepsace! This is probably due to a bug in underlying modules. "
                         + "First global match will be used", 1)
                tags = schema.bs_element("", {"name": name}, recursive=False)
                if len(tags) > 0:
                    return self.type_factory(tags[0], schema)

        self.log("Unable to find Type based on name {0}".format(name), 2)
        return None
