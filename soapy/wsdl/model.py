from soapy.wsdl.element import Element

""" Models are pythonic objects representing the XML tags in a WSDL, but outside of the Types tag """

class Service(Element):
    """ Simplified, native Python representation of Service definitions in WSDL
    Provides information on child (port) objects by name and service tag attribute information """

    @property
    def ports(self) -> tuple:
        try:
            return self.__ports
        except AttributeError:
            self.log("Initializing list of ports defined for service {0}".format(self.name), 5)
            ports = list()
            for port in self.bsElement('port', recursive=False):
                ports.append(Port(port, self.parent))
            self.__ports = tuple(ports)
            return self.__ports


class PortType(Element):
    """ Simplified, native Python representation of portType definition in WSDL """

    @property
    def operations(self) -> tuple:
        try:
            return self.__operations
        except AttributeError:
            self.log("Initializing operations for portType {0} from wsdl".format(self.name), 5)
            operations = list()
            for operation in self.bsElement('operation', recursive=False):
                operations.append(Operation(operation, self.parent))
            self.__operations = tuple(operations)
            return self.__operations

    @property
    def methods(self) -> tuple:
        return self.operations


class Binding(Element):
    """ Simplified, native python representation of a binding definition
    Also provides enforcement that the style of the binding is document
    as this library does not (currently) support other styles """

    def __init__(self, bsElement, parent):
        super().__init__(bsElement, parent)
        # Validate that the binding style is 'document'
        soapBinding = bsElement('binding', recursive=False)[0]
        if not soapBinding['style'] == "document":
            self.log("Binding style not set to document. SoaPy can't handle non-document styles", 0)
            raise TypeError("Binding style not set to document. SoaPy can't handle non-document styles")

    @property
    def type(self) -> PortType:
        try:
            return self.__type
        except AttributeError:
            self.log("Initializing portType from binding {0}".format(self.name), 5)
            (ns, name) = self.bsElement['type'].split(":")
            self.__type = PortType.fromName(name, self.parent)
            return self.__type

    def getSoapAction(self, opName) -> str:

        """ Given the name of an operation, return the soap action """

        operations = self.bsElement('operation', recursive=False)
        for operation in operations:
            if operation['name'] == opName:
                soapOp = operation('operation')[0]
                try:
                    return soapOp['soapAction']
                except KeyError:
                    self.log("Binding operation does not contain a soapAction element", 2)
                    return None

        self.log("Could not find matching operation, {0} in binding {1}".format(
            opName, self.name), 2)


class Port(Element):
    """ Simplified, native Python representation of ports as defined within services """

    @property
    def binding(self) -> Binding:
        try:
            return self.__binding
        except AttributeError:
            self.log("Initializing binding attribute for port {0}".format(self.name), 5)
            binding = self.bsElement['binding']
            (ns, name) = binding.split(':')
            self.__binding = Binding.fromName(name, self.parent)
            return self.__binding

    @property
    def location(self) -> str:
        try:
            return self.__location
        except AttributeError:
            self.log("Initializing location of Port based on address element", 5)
            self.__location = self.bsElement('address', recursive=False)[0]['location']
            self.log("Initialized location to {0}".format(self.__location), 4)
            return self.__location

    @location.setter
    def location(self, location):
        self.__location = location


class Message(Element):
    @property
    def parts(self) -> tuple:
        try:
            return self.__parts
        except AttributeError:
            self.log("Initializing parts for message {0}".format(self.name), 5)
            parts = list()
            for part in self.bsElement('part', recursive=False):
                parts.append(Part(part, self.parent))
            self.__parts = tuple(parts)
            return self.__parts


class Part(Element):
    @property
    def type(self) -> Element:
        try:
            return self.__type
        except AttributeError:
            self.__type = self.parent.findTypeByName(self.bsElement['element'])
            return self.__type

    @property
    def element(self) -> Element:
        return self.type

    @property
    def ns(self) -> str:
        return self.bsElement['element'].split(':')[0]

    @property
    def namespace(self) -> str:
        return self.ns


class Operation(Element):
    """ Simplified, native Python representation of an operation definition in portType element group"""

    @property
    def input(self) -> Message:
        try:
            return self.__input
        except AttributeError:
            name = self.bsElement('input')[0].get('message').split(":")[1]
            self.__input = Message.fromName(name, self.parent)
            return self.__input

    @property
    def output(self) -> Message:
        try:
            return self.__output
        except AttributeError:
            name = self.bsElement('output')[0].get('message').split(":")[1]
            self.__output = Message.fromName(name, self.parent)
            return self.__output

    @property
    def fault(self) -> Message:
        try:
            return self.__fault
        except AttributeError:
            searchResults = self.bsElement('fault')
            if len(searchResults) == 1:
                name = searchResults[0].get("message").split(":")[1]
                self.__fault = Message.fromName(name, self.parent)
                return self.__fault
            else:
                self.log("Operation has no fault message specified", 2)
                self.__fault = None
                return self.__fault