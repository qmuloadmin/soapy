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
            for port in self.bs_element('port', recursive=False):
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
            for operation in self.bs_element('operation', recursive=False):
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
        self.__ns = soapBinding.namespace
        if not soapBinding.get('style', "document") == "document":
            self.log("Binding style not set to document. Soapy can't handle non-document styles", 0)
            raise TypeError("Binding style not set to document. Soapy can't handle non-document styles")

    @property
    def type(self) -> PortType:
        try:
            return self.__type
        except AttributeError:
            self.log("Initializing portType from binding {0}".format(self.name), 5)
            (ns, name) = self.bs_element['type'].split(":")
            self.__type = PortType.from_name(name, self.parent)
            return self.__type

    @property
    def ns(self) -> str:
        return self.__ns

    def get_soap_action(self, op_name) -> str:

        """ Given the name of an operation, return the soap action """

        operations = self.bs_element('operation', recursive=False)
        for operation in operations:
            if operation['name'] == op_name:
                soap_op = operation('operation')[0]
                try:
                    return soap_op['soapAction']
                except KeyError:
                    self.log("Binding operation does not contain a soapAction element", 2)
                    return None

        self.log("Could not find matching operation, {0} in binding {1}".format(
            op_name, self.name), 2)


class Port(Element):
    """ Simplified, native Python representation of ports as defined within services """

    @property
    def binding(self) -> Binding:
        try:
            return self.__binding
        except AttributeError:
            self.log("Initializing binding attribute for port {0}".format(self.name), 5)
            binding = self.bs_element['binding']
            (ns, name) = binding.split(':')
            self.__binding = Binding.from_name(name, self.parent)
            return self.__binding

    @property
    def location(self) -> str:
        try:
            return self.__location
        except AttributeError:
            self.log("Initializing location of Port based on address element", 5)
            self.__location = self.bs_element('address', recursive=False)[0]['location']
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
            for part in self.bs_element('part', recursive=False):
                parts.append(Part(part, self.parent))
            self.__parts = tuple(parts)
            return self.__parts


class Part(Element):
    @property
    def type(self) -> Element:
        try:
            return self.__type
        except AttributeError:
            self.__type = self.parent.find_type_by_name(self.bs_element['element'])
            return self.__type

    @property
    def element(self) -> Element:
        return self.type

    @property
    def ns(self) -> str:
        return self.bs_element['element'].split(':')[0]


class Operation(Element):
    """ Simplified, native Python representation of an operation definition in portType element group"""

    @property
    def input(self) -> Message:
        try:
            return self.__input
        except AttributeError:
            name = self.bs_element('input')[0].get('message').split(":")[1]
            self.__input = Message.from_name(name, self.parent)
            return self.__input

    @property
    def output(self) -> Message:
        try:
            return self.__output
        except AttributeError:
            name = self.bs_element('output')[0].get('message').split(":")[1]
            self.__output = Message.from_name(name, self.parent)
            return self.__output

    @property
    def faults(self) -> tuple:
        try:
            return self.__faults
        except AttributeError:
            search_results = self.bs_element('fault')
            if len(search_results) > 0:
                faults = list()
                for each in search_results:
                    faults.append(Message.from_name(each.get("message").split(":")[1], self.parent))
                self.__faults = tuple(faults)
                return self.__faults
            else:
                self.log("Operation has no fault message specified", 2)
                self.__faults = tuple()
                return self.__faults
