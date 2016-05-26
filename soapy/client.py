import requests
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError

import soapy.marshal
from soapy import Log
from soapy.wsdl import Wsdl
from soapy.wsdl.model import *


class Client(Log):
    
    """ Class abstracts Wsdl data model and provides a simple API for providing input
    values for a given operation, and sending request. Works with Marshaller to 
    generate SOAP envelope for request """

    def __init__(self, wsdl_location: str, tl=0, operation=None, service=None, **kwargs):
        
        """ Provide a wsdl file location url, e.g. http://my.domain.com/some/service?wsdl or
        file:///full/path/to.wsdl, a tracelevel for logging (0-5), and optionally pass in
        a Service name, and an Operation.

        Tracelevels:

        -1: (No logging)
        0: (Only critical errors)
        1: (Only errors and critical errors)
        2: (Warnings and more severe)
        3: (Notice)
        4: (Informational)
        5: (Debug information)

        If service is not provided, but operation is, the first operation in any service
        matching the name will be user. If service is provided, then only that service will
        be searched for a matching operation. You can also select a service or operation later
        by setting self.service and/or self.operation. This allows you to explore the wsdl
        and get a list of possible services and operations within each service """

        # Initialize instance of Log using provided trace level

        super().__init__(tl)

        # Initialize some default values

        self.username = None
        self.password = None
        self.proxy = ""
        self.proxyUser = ""
        self.proxyPass = ""
        self.__requestEnvelope = None

        # Initialize instance of Wsdl using provided information
        self.log("Initializing new wsdl object using url: {0}".format(
                                                      wsdl_location), 4)
        self.__wsdl = Wsdl(wsdl_location, tl)

        # If either operation or service is set, initialize them to starting values

        if service is not None:
            self.log("Initializing service with name {0}".format(service), 5)
            self.service = service

        if operation is not None:
            self.log("Initializing operation with name {0}".format(operation), 5)
            self.operation = operation

        self.log("Client successfully initialized", 3)

    @property
    def service(self) -> Service:
        try:
            return self.__service
        except AttributeError:
            return None
    
    @service.setter
    def service(self, service):
        found = False
        self.log("Searching for service with name {0}".format(service), 5)
        for each in self.wsdl.services:
            if each.name == service:
                self.__service = each
                found = True
        if not found:
            self.log("Search for service matching name {0} failed; WDSL does not contain this service"
                     .format(service), 1)
            raise ValueError("WSDL contains no service named {0}".format(service))

    @property
    def wsdl(self) -> Wsdl:
        return self.__wsdl

    @property
    def port(self) -> str:
        return self.__port

    @property
    def operation(self) -> str:
        try:
            return self.__operation
        except AttributeError:
            return None

    @operation.setter
    def operation(self, operationName):
        def ops(service):
            for port in service.ports:
                for operation in port.binding.type.operations:
                    yield (port, operation)
        found = False
        if self.service is None:
            for service in self.wsdl.services:
                for port, operation in ops(service):
                    if operation.name == operationName:
                        found = True
                        self.__operation = operation
                        self.__port = port
                        self.__service = service
        else:
            for operation in ops(self.service):
                if operation.name == operationName:
                    found = True
                    self.__operation = operation
        if not found:
            self.log("Search for operation matching name {0} failed; No such operation"
                     .format(operationName), 1)
            raise ValueError("No such operation: {0}".format(operationName))
        else:
            self.log("Set client operation to {0}".format(self.operation), 3)

    @property
    def schema(self):
        try:
            return self.__schema
        except:
            raise ValueError("Must set operation before schema can be determined")

    @property
    def location(self):
        if self.operation is None:
            raise ValueError("Must set operation before location can be determined")
        return self.port.location

    @location.setter
    def location(self, new_location):
        if self.operation is None:
            raise ValueError("Must set operation before location can be determined")
        self.port.location = new_location

    @property
    def inputs(self):
        try:
            return self.__inputs
        except AttributeError:
            try:
                inputs = list()
                self.log("Building list of inputs for operation {0}".format(self.operation), 4)
                for each in self.operation.input.parts:
                    inputs.append(InputOptions(each.type))
                self.__inputs = tuple(inputs)
                return self.__inputs
            except AttributeError:
                raise RuntimeError("Must set operation before inputs can be determined")

    @property
    def requestEnvelope(self):
        return self.__requestEnvelope

    def _buildEnvelope(self):
        self.log("Initializing marshaller for envelope", 5)
        self.__requestEnvelope = soapy.marshal.Envelope(self)
        self.log("Rendering request envelope", 5)
        self.__requestEnvelope.render()

    def _buildProxyDict(self) -> dict:
        if self.proxy:
            self._buildFinalProxyUrl()
            return {"http": self.proxyUrl,
                    "https": self.proxyUrl}
        else:
            return {}

    def _buildFinalProxyUrl(self):
        self.log("Building proxy Url with provided information", 5)
        if self.proxyUser is not None:
            import re
            self.proxy = re.sub(r"^(https?://)([^@]+)$",
                                   "\1{0}:{1}@\2"
                                   .format(self.proxy, self.proxyPass),
                                   self.proxyUrl)
            self.log("Set proxy to '{0}'".format(self.proxy), 4)

    def __call__(self, **kwargs):

        """ Execute the web service operation. Operation must be set at minimum before this is possible
         :keyword location: The URL/Location of the web service. Will override location specified in WSDL
         :keyword username: The username for use in auth with the web service
         :keyword password: The password paired with the username for web service authorization
         :keyword proxyUrl: The URL for a HTTP/HTTPS proxy to be used, if any
         :keyword proxyUser: The Username for basic http auth with the web proxy
         :keyword proxyPass: The password for basic http auth with the web proxy """

        if self.operation is None:
            raise ValueError("Operation must be set before web service can be called")

        keys = kwargs.keys()
        if "location" in keys:
            self.location = kwargs["location"]
        if "username" in keys:
            self.username = kwargs["username"]
            self.password = kwargs["password"]
        if "proxyUrl" in keys:
            self.proxyUrl = kwargs["proxyUrl"]
        if "proxyUser" in keys:
            self.proxyUser = kwargs["proxyUser"]
        if "proxyPass" in keys:
            self.proxyPass = kwargs["proxyPass"]

        self.log("Getting ready to call the web service", 4)

        self._buildEnvelope()
        self.log("Creating necessary HTTP headers", 5)
        headers = {"SOAPAction": self.port.binding.getSoapAction(self.operation.name),
                   "Content-Type": "text/xml;charset=UTF-8"}
        self.log("Set custom headers to {0}".format(headers), 5)
        proxies = self._buildProxyDict()
        self.log("Calling web service at {0}".format(self.location), 3)
        try:
            if self.username is None:
                self.response = requests.post(self.location,
                                              proxies=proxies,
                                              data=self.requestEnvelope.xml,
                                              headers=headers)
            else:
                self.response = requests.post(self.location,
                                              auth=HTTPBasicAuth(self.username, self.password),
                                              proxies=proxies,
                                              data=self.requestEnvelope.xml,
                                              headers=headers)
        except ConnectionError as e:
            self.log("Web service connection failed. Check location and try again", 0)
            raise ConnectionError(str(e))

        self.log("Web service call complete, status code is {0}".format(self.response.status_code), 3)
        if "xml" in self.response.headers["Content-Type"]:
            self.log("Rendering response XML", 5)
            self.responseXml = BeautifulSoup(self.response.text, "xml")
        else:
            self.log("Response is not XML, or has incorrect Content-Type headers", 1)
            self.responseXml = None

        return self.responseXml


class InputOptions:
    
    """ Describes possible inputs to the web service in a pythonic fashion """

    def __init__(self, element):
        
        """ Walks the object tree to find all elements and creates  """

        elements = list()
        inputs = list()
        InputOptions._recursiveExtractElements(elements, element)
        names = []
        duplicates = False
        for element in elements:
            name = element[0].name
            if name in names:
                duplicates = True
            names.append(name)
            parent = element[1]
            attributes = element[0].attributes
            setable = False
            if len(element[0].elementChildren) == 0:
                setable = True
            inputs.append(InputElement(name, parent, attributes, setable, element[0]))
        self.__elements = tuple(inputs)
        if not duplicates:
            self.simplify()

    def __getattr__(self, item):
        return self.__getitem__(item)

    def __str__(self):
        s = ""
        i = 0
        for each in self.__elements:
            s += "[{0}]: {1}".format(i, each)
            i += 1
        return s

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.items[key]
        for each in self.items:
            if each.name == key:
                return each
        raise KeyError

    @property
    def items(self):
        return self.__elements

    def simplify(self):
        """
        Simplify is called automatically by InputOptions after construction if there are no repeated input key names.
        It can be called manually to force simplification of input names, but this is usually not desirable.
        :return: None
        """
        for each in self.items:
            each.simplify()

    @staticmethod
    def _recursiveExtractElements(l: list, element, parent=None):
        
        """ Recursively iterates over soapy.wsdl.types Objects and extracts the 
        TypeElement objects, as they are what actually represent input options """

        if element is None:
            return

        l.append((element, parent))
        for child in element.elementChildren:
            if child.bsElement is element.bsElement:
                continue
            InputOptions._recursiveExtractElements(l, child, element)


class InputElement:

    """ An individual element of input, has a name, value and attributes. A further 
    abstraction of the TypeElement object in soapy.wsdl.types """

    def __init__(self, name, parent, attributes, setable, ref):
        self.__parent = parent
        if self.parent is not None:
            self.__name = self.parent.name + "_" + name
        else:
            self.__name = name
        self.__setable = setable
        self.__ref = ref
        attrs = list()
        for attr in attributes:
            attrs.append(InputAttribute(attr.name, attr.default))
        self.__attrs = tuple(attrs)

    @property
    def parent(self):
        return self.__parent

    def __str__(self):
        s = "'{0}'".format(self.name)
        if self.innerXml is not None:
            s += " : " + str(self.innerXml)
        elif self.setable:
            s += " = " + str(self.value)
        else:
            s += " (Attributes only)"
        s += "\n"
        for each in self.__attrs:
            s += "    {0}\n".format(each)
        return s

    def keys(self):
        return tuple([attr.name for attr in self.attributes])
    
    @property
    def value(self) -> str:
        try:
            return self.__value
        except AttributeError:
            return None

    @value.setter
    def value(self, value):
        if self.__setable:
            self.__value = value
        else:
            raise TypeError("Can't set value of element {0}".format(self.name))

    @property
    def innerXml(self) -> str:
        try:
            return self.__innerXml
        except AttributeError:
            return None
    
    @innerXml.setter
    def innerXml(self, xml: str):

        """ Setting innerXml will override the marshaller's behavior with rendering the XML
        from the WSDL and input objects and simply include what you specify, replacing all
        children elements (if present) and any text content in 'value' attribute """

        self.__innerXml = xml

    @property
    def attributes(self) -> tuple:
        # Not memo-ized because contents of tuple are mutable
        return self.__attrs

    @property
    def name(self) -> str:
        return self.__name

    @property
    def setable(self) -> bool:
        return self.__setable

    @property
    def ref(self):
        return self.__ref

    def simplify(self):
        """
        Simplify is called automatically by InputOptions after construction if there are no repeated input key names.
        It can be called manually to force simplification of input names, but this is usually not desirable.
        :return: None
        """
        if self.parent is not None:
            self.__name = self.name.replace(self.parent.name+"_", "")

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.items[key].value = value
        else:
            found = False
            for each in self.items:
                if each.name == key:
                    each.value = value
                    found = True
            if not found:
                raise KeyError

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.items[key]
        for each in self.items:
            if each.name == key:
                return each
        raise KeyError


class InputAttribute:
    
    """ An individual attribute of an input Element. A further abstraction of the
    Attribute object in soapy.wsdl.types """

    def __init__(self, name, value):
        self.__name = name
        self.value = value

    @property
    def name(self):
        return self.__name

    def __str__(self):
        return "['"+self.name+"'] = " + str(self.value)