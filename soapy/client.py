import requests
from bs4 import BeautifulSoup, Tag
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError

import soapy.marshal
from soapy import Log
from soapy.inputs import Factory as InputFactory
from soapy.wsdl import Wsdl
from soapy.wsdl.model import *


class Client(Log):
    
    """ Class abstracts Wsdl data model and provides a simple API for providing input
    values for a given operation, and sending request. Works with Marshaller to 
    generate SOAP envelope for request """

    constructor_kwargs = ("location",
                          "username",
                          "password",
                          "proxy_url",
                          "proxy_user",
                          "proxy_pass",
                          "secure",
                          "version"
                          )

    def __init__(self, wsdl_location: str, tl=0, operation=None, service=None, **kwargs):
        
        """ Provide a wsdl file location url, e.g. http://my.domain.com/some/service?wsdl or
        file:///full/path/to.wsdl, a tracelevel for logging (0-5), and optionally pass in
        a Service name, and an Operation.

        :keyword location: The location (URL) of the web service. Overrides the location from the WSDL for the operation
        :keyword username: The username to authenticate to the web service, if needed
        :keyword password: The password to authenticate to the web service, if needed
        :keyword proxy_url: The URL of the proxy to use, including port, if needed to retrieve WSDL
        :keyword proxy_user: The username, if any, to authenticate to the proxy with
        :keyword proxy_pass: The password paired with the username for proxy authentication
        :keyword secure: A boolean flag, defaults to True, if SSL verification should be performed
        :keyword version: A number representing the SOAP version (1.1 or 1.2) of the request. Defaults to 1.1

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

        self.__username = None
        self.__password = None
        self.proxy_url = ""
        self.proxy_user = ""
        self.proxy_pass = ""
        self.__auth = None
        self.headers = {"Content-Type": "text/xml;charset=UTF-8"}

        # Update values with kwargs if provided

        for each in kwargs:
            if each in self.constructor_kwargs:
                setattr(self, each, kwargs[each])
            else:
                raise ValueError("Unexpected keyword argument for {} initializer, {}".format(
                    self.__class__.__name__,
                    each
                ))

        # Initialize instance of Wsdl using provided information
        self.log("Initializing new wsdl object using url: {0}".format(
                                                      wsdl_location), 4)

        # Initialize the Wsdl for this client with any key word args that are valid for that class
        self.__wsdl = Wsdl(
            wsdl_location,
            tl,
            **dict((key, value) for key, value in kwargs.items() if key in Wsdl.constructor_kwargs)
        )

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
        """ The service that the client is interacting with. May be one of a list, or the only service defined"""
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
    def auth(self):
        return self.__auth

    @auth.setter
    def auth(self, obj):
        self.__auth = obj

    @property
    def username(self):
        """ The username for HTTP Basic Auth, if needed """
        return self.__username

    @username.setter
    def username(self, name):
        self.__username = name
        if self.password is not None:
            self.log("Username provided, setting Authentication type to Basic HTTP", 5)
            self.auth = HTTPBasicAuth(self.username, self.password)

    @property
    def password(self):
        return self.__password

    @password.setter
    def password(self, p):
        self.__password = p
        if self.username is not None:
            self.log("Password provided, setting Authentication type to Basic HTTP", 5)
            self.auth = HTTPBasicAuth(self.username, self.password)

    @property
    def wsdl(self) -> Wsdl:
        """
        :return: The WSDL object for this client instance
        """
        return self.__wsdl

    @property
    def port(self) -> Port:
        """
        :return: The currently selected or appropriate Port (from wsdl.Model) for the operation of this Client instance
        """
        return self.__port

    @property
    def operation(self) -> Operation:
        """
        The operation to be used by this client. Selecting an operation also selects the appropriate Port and Service
        If there is more than one operation with the same name in multiple services, Client.service must be set first,
        or the first matching operation will be used

        Operation must be set before the client can be called, or inputs set

        :return: The wsdl.Model.Operation object selected for this client instance, or None if not yet set
        """
        try:
            return self.__operation
        except AttributeError:
            return None

    @operation.setter
    def operation(self, operation_name):
        def ops(service):
            for port in service.ports:
                for operation in port.binding.type.operations:
                    yield (port, operation)
        found = False
        if self.service is None:
            for service in self.wsdl.services:
                for port, operation in ops(service):
                    if operation.name == operation_name:
                        found = True
                        self.__operation = operation
                        self.__port = port
                        self.__service = service
        else:
            for port, operation in ops(self.service):
                if operation.name == operation_name:
                    found = True
                    self.__operation = operation
                    self.__port = port
        if not found:
            self.log("Search for operation matching name {0} failed; No such operation"
                     .format(operation_name), 1)
            raise ValueError("No such operation: {0}".format(operation_name))
        else:
            self.log("Set client operation to {0}".format(self.operation), 3)
            # Clear any input object, as a new operation will have a new input object
            try:
                del self.__inputs
            except AttributeError:
                " Do nothing, as this means inputs were never generated for the previous operation "

    @property
    def schema(self):
        try:
            return self.__schema
        except:
            raise ValueError("Must set operation before schema can be determined")

    @property
    def location(self) -> str:
        """
        :return: The endpoint, or location, or the web service to be called. This should be fully qualified. Unless
        manually set, this is from the WSDL service definition
        """
        if self.operation is None:
            raise ValueError("Must set operation before location can be determined")
        return self.port.location

    @location.setter
    def location(self, new_location):
        if self.operation is None:
            raise ValueError("Must set operation before location can be determined")
        self.port.location = new_location

    @property
    def inputs(self) -> tuple:
        """
        inputs is a tuple of iterable soapy.client.InputOptions objects. In most cases, there is only one possible
        input message for a given operation, in which case the tuple will have only 1 element. To use InputFactory
        as the source of input, please use Client.input_factory instead (currently unimplementented)
        """
        try:
            return self.__inputs
        except AttributeError:
            try:
                inputs = list()
                self.log("Building list of inputs for operation {0}".format(self.operation.name), 4)
                for each in self.operation.input.parts:
                    inputs.append(InputFactory(each.type, self.tl))
                self.__inputs = tuple(inputs)
                return self.__inputs
            except AttributeError:
                raise RuntimeError("Must set operation before inputs can be determined")

    @property
    def request_envelope(self):
        try:
            return self.__requestEnvelope
        except AttributeError:
            self._build_envelope()
            self.log("Rendered request envelope: {0}"
                     .format(self.__requestEnvelope),
                     5)
            return self.__requestEnvelope

    def _build_envelope(self):
        self.log("Initializing marshaller for envelope", 5)
        self.__requestEnvelope = soapy.marshal.Envelope(self)
        self.log("Rendering request envelope", 5)
        self.__requestEnvelope.render()

    def _build_proxy_dict(self) -> dict:
        if self.proxy_url:
            self._build_final_proxy_url()
            return {"http": self.proxy_url,
                    "https": self.proxy_url}
        else:
            return {}

    def _build_final_proxy_url(self):
        self.log("Building proxy Url with provided information", 5)
        if self.proxy_user is not None:
            import re
            self.proxy_url = re.sub(r"^(https?://)([^@]+)$",
                                   r"\1{0}:{1}@\2"
                                    .format(self.proxy_user, self.proxy_pass),
                                    self.proxy_url)
            self.log("Set proxy to '{0}'".format(self.proxy), 4)

    def __call__(self, **kwargs):

        """ Execute the web service operation. Operation must be set at minimum before this is possible
         :keyword location: The URL/Location of the web service. Will override location specified in WSDL
         :keyword username: The username for use in auth with the web service
         :keyword password: The password paired with the username for web service authorization
         :keyword proxy_url: The URL for a HTTP/HTTPS proxy to be used, if any
         :keyword proxy_user: The Username for basic http auth with the web proxy
         :keyword proxy_pass: The password for basic http auth with the web proxy
         :keyword doctors: A list of the plugins to modify (doctor) the client or soap envelope before
         calling the webservice
         :keyword secure: If False, will not attempt to validate SSL certificates. Defaults to True """

        if self.operation is None:
            raise ValueError("Operation must be set before web service can be called")

        doctor_plugins = None
        self.secure = True

        for key in kwargs:
            if key in self.constructor_kwargs:
                setattr(self, key, kwargs[key])
            elif key == "doctors":
                doctor_plugins = kwargs[key]
            else:
                raise ValueError("Unexpected keyword argument '{}' for __call__".format(key))

        self.log("Getting ready to call the web service", 4)

        self.log("Creating necessary HTTP headers", 5)
        self.headers["SOAPAction"] = self.port.binding.get_soap_action(self.operation.name)
        self.log("Set custom headers to {0}".format(self.headers), 5)
        proxies = self._build_proxy_dict()

        if doctor_plugins is not None:
            self.log("Loading doctors for request", 5)
            for doctor in doctor_plugins:
                self.log("Applying doctor plugin {}".format(doctor.__class__.__name__), 3)
                self.request_envelope.xml = doctor(self, self.request_envelope.xml, self.tl)

        try:
            if self.auth is None:
                self.log("Calling web service at {0}".format(self.location), 3)
                self.response = requests.post(self.location,
                                              proxies=proxies,
                                              data=self.request_envelope.xml,
                                              headers=self.headers,
                                              verify=self.secure)
            else:
                self.log("Calling web service at {0} using Authentication".format(self.location), 3)
                self.response = requests.post(self.location,
                                              auth=self.auth,
                                              proxies=proxies,
                                              data=self.request_envelope.xml,
                                              headers=self.headers,
                                              verify=self.secure)
        except ConnectionError as e:
            self.log("Web service connection failed. Check location and try again", 0)
            raise ConnectionError(str(e))

        self.log("Web service call complete, status code is {0}".format(self.response.status_code), 3)
        self.log("Creating new Response object", 5)
        return Response(self.response, self)


class Response:
    """ Object describes the web service response, attempts to provide simple status indication and messages,
        and provides someone intelligent methods for interacting with the response.
        Response encapsulates both "output" messages and "fault" messages. """

    def __init__(self, response, client: Client):
        """
        Intended to be initialized via Client upon receiving response
        :param response: requests Response object
        :param client: the client object which called Response
        """

        self.__response = response
        self.__client = client
        if self.isXml:
            self.__bsResponse = BeautifulSoup(self.text, "xml")
        else:
            self.__bsResponse = BeautifulSoup(self.text, "lxml")
        self.outputs = tuple()
        self.faults = tuple()
        faults = list()
        outputs = list()
        self.__client.log("Initializing list of faults for this operation", 5)
        for fault in self.__client.operation.faults:
            if fault is not None:
                for part in fault.parts:
                    try:
                        faults.append(self.bsResponse(part.type.name)[0])
                    except IndexError:
                        " Do nothing, as the fault message is not present in the response"
        for part in self.__client.operation.output.parts:
            try:
                outputs.append(self.bsResponse(part.type.name)[0])
            except IndexError:
                " Do nothing because there was no valid XML response (probably 500 error, etc) "
        self.outputs = tuple(outputs)
        self.faults = tuple(faults)
        if self:
            self.__client.log("Initialized Successful Response object", 4)
        else:
            self.__client.log("Initialized Unsuccessful Response object with status code {0}"
                              .format(self.status), 4)

    def __bool__(self):
        if not self.__response.ok:
            return False
        if not self.isXml:
            return False
        for each in self.faults:
            if not each.isSelfClosing and not each.is_empty_element:
                return False
        if not len(self.outputs):
            return False
        return True

    def __str__(self):
        return self.text

    @property
    def status(self):
        return self.__response.status_code

    @property
    def isXml(self) -> bool:
        if self.contentType is None:
            self.__client.log("Response is missing Content-Type header", 1)
            return False
        if "xml" in self.contentType:
            return True
        self.__client.log("Response is not XML, or has incorrect Content-Type headers", 1)
        return False

    @property
    def is_xml(self) -> bool:
        return self.isXml

    @property
    def text(self) -> str:
        return self.__response.text

    @property
    def content_type(self) -> str:
        return self.contentType

    @property
    def contentType(self) -> str:
        try:
            return self.__response.headers["Content-Type"]
        except KeyError:
            return None

    @property
    def bsResponse(self):
        return self.__bsResponse

    @property
    def simple_outputs(self) -> dict:
        """
        Dictionary of only significant outputs, without parent-child relationships. Makes some assumptions that could
        result in losing data in rare cases. With more complicated responses, it is recommended to use outputs
        instead of simple_outputs.
        :return: dict
        """
        try:
            return self.__simple_outputs
        except AttributeError:
            self.__client.log("Starting recursive consolidation of outputs", 4)
            simple_outputs = dict()
            for output in self.outputs:
                for child in output.children:
                    self._recursive_extract_significant_children(child, simple_outputs)
            self.__simple_outputs = simple_outputs
            self.__client.log("Significant outputs identified: {0}".format(simple_outputs), 5)
            return self.__simple_outputs

    @property
    def simple_faults(self) -> dict:
        """
        Dictionary of only significant faults, excluding parent-child relationships, structure, etc
        :return: dict
        """

        try:
            return self.__simple_faults
        except AttributeError:
            self.__client.log("Starting recursive consolidation of faults", 4)
            simple_faults = dict()
            for fault in self.faults:
                for child in fault.children:
                    self._recursive_extract_significant_children(child, simple_faults)
            self.__simple_faults = simple_faults
            self.__client.log("Significant faults identified: {}".format(simple_faults), 5)
            return self.__simple_faults

    @staticmethod
    def _recursive_extract_significant_children(bsElement: Tag, d: dict, parent=None) -> None:

        """
        :param bsElement: BeautifulSoup Tag from the response output
        :param d: Dictionary to be updated with values
        :param parent: Parent BeautifulSoup tag, if applicable
        :return:
        """

        if not isinstance(bsElement, Tag):
            return
        if bsElement.string is not None:
            name = bsElement.name
            value = str(bsElement.string).strip()
            if name in d.keys():
                if parent is not None:
                    if d[name]["parent"] != parent.name:
                        # Disambiguate both child keys, rebuild the previous dict item
                        otherParent = d[name]["parent"]
                        otherValue = d[name]["value"]
                        del d[name]
                        d[otherParent + "_" + name] = {"value": otherValue,
                                                       "parent": otherParent}
                        name = parent.name + "_" + name
            if name in d.keys():
                # Assume that its a list of values, and convert to a list or append to existing list
                try:
                    d[name]["value"].append(value)
                except AttributeError:
                    d[name]["value"] = [d[name]["value"], value]
            else:
                try:
                    d.update({name: {"value": value,
                                     "parent": parent.name}})
                except AttributeError:
                    d.update({name: {"value": value,
                                     "parent": None}})

        for each in bsElement.children:
            Response._recursive_extract_significant_children(each, d, bsElement)
