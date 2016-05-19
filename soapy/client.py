from soapy import Log
from soapy.wsdl import Wsdl
from soapy.wsdl.model import *
from soapy.wsdl.types import TypeElement


class Client(Log):
    
    """ Class abstracts Wsdl data model and provides a simple API for providing input
    values for a given operation, and sending request. Works with Marshaller to 
    generate SOAP envelope for request """

    def __init__(self, wsdl_location, tl=0, operation=None, service=None, **kwargs):
        
        """ Provide a wsdl file location url, e.g. http://my.domain.com/some/service?wsdl or
        file:///full/path/to.wsdl, a tracelevel for logging (0-5), and optionally pass in
        a Service name, and an Operation.

        If service is not provided, but operation is, the first operation in any service
        matching the name will be user. If service is provided, then only that service will
        be searched for a matching operation. You can also select a service or operation later
        by setting self.service and/or self.operation. This allows you to explore the wsdl
        and get a list of possible services and operations within each service """

        # Initialize instance of Log using provided trace level

        super().__init__(tl)

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
    def wsdl(self):
        return self.__wsdl

    @property
    def operation(self):
        try:
            return self.__operation
        except AttributeError:
            return None

    @operation.setter
    def operation(self, operationName):
        def ops(service):
            for port in service.ports:
                for operation in port.binding.type.operations:
                    yield operation
        found = False
        if self.service is None:
            for service in self.wsdl.services:
                for operation in ops(service):
                    if operation.name == operationName:
                        found = True
                        self.__operation = operation
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
            raise RuntimeError("Must set operation before schema can be determined")

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

    def _buildEnvelope(self):
        pass


class InputBase:

    """ Defines and enables key/index duality where a keyword can be used to find or set a value, as
    can an index number. This is because some inputs could have the same name in rare cases """

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
        

class InputOptions(InputBase):
    
    """ Describes possible inputs to the web service in a pythonic fashion """

    def __init__(self, element):
        
        """ Walks the object tree to find all elements and creates  """

        elements = list()
        inputs = list()
        InputOptions._recursiveExtractElements(elements, element)
        for element in elements:
            name = element.name
            attributes = element.attributes
            setable = False
            if len(element.elementChildren) == 0:
                setable = True
            inputs.append(InputElement(name, attributes, setable, element))
        self.__elements = tuple(inputs)

    @property
    def items(self):
        return self.__elements

    @staticmethod
    def _recursiveExtractElements(l: list, element):
        
        """ Recursively iterates over soapy.wsdl.types Objects and extracts the 
        TypeElement objects, as they are what actually represent input options """

        if element is None: return
        if isinstance(element, TypeElement):
            l.append(element)
        for child in element.children:
            InputOptions._recursiveExtractElements(l, child)

    def __str__(self):
        s = ""
        i = 0
        for each in self.__elements:
            s += "[{0}]: {1}".format(i, each)
            i += 1
        s += '}'
        return s

class InputElement(InputBase):

    """ An individual element of input, has a name, value and attributes. A further 
    abstraction of the TypeElement object in soapy.wsdl.types """

    def __init__(self, name, attributes, setable, ref):
        self.__name = name
        self.__setable = setable
        self.__ref = ref
        attrs = list()
        for attr in attributes:
            attrs.append(InputAttribute(attr.name, attr.default))
        self.__attrs = tuple(attrs)


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
    def items(self):
        return self.attributes

    @property
    def attributes(self):
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


class InputAttribute():
    
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

