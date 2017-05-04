""" Models are pythonic objects representing the XML tags in a WSDL, but outside of the Types tag """

import logging

from soapy.wsdl.element import Element

# Initialize logger for this module
logger = logging.getLogger(__name__)


class Service(Element):
    """ Simplified, native Python representation of Service definitions in WSDL
    Provides information on child (port) objects by name and service tag attribute information """

    def __init__(self, bs_element, wsdl):
        super().__init__(bs_element, wsdl)
        self.__ports = None

    @property
    def ports(self) -> tuple:
        if self.__ports is None:
            logger.debug("Initializing list of ports defined for service {0}".format(self.name))
            ports = list()
            for port in self.bs_element('port', recursive=False):
                ports.append(Port(port, self.parent))
            self.__ports = tuple(ports)
        return self.__ports


class PortType(Element):
    """ Simplified, native Python representation of portType definition in WSDL """

    def __init__(self, bs_element, wsdl):
        super().__init__(bs_element, wsdl)
        self.__operations = None

    @property
    def operations(self) -> tuple:
        if self.__operations is None:
            logger.debug("Initializing operations for portType {0} from wsdl".format(self.name))
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

    def __init__(self, bs_element, parent):
        super().__init__(bs_element, parent)
        # Validate that the binding style is 'document'
        soapBinding = bs_element('binding', recursive=False)[0]
        self.__ns = soapBinding.namespace
        if not soapBinding.get('style', "document") == "document":
            logger.critical("Binding style not set to document. Soapy can't handle non-document styles")
            raise TypeError("Binding style not set to document. Soapy can't handle non-document styles")

        # Attributes to be evaluated lazy
        self.__type = None

    @property
    def type(self) -> PortType:
        if self.__type is None:
            logger.debug("Initializing portType from binding {0}".format(self.name))
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
                    logger.warning("Binding operation does not contain a soapAction element")
                    return None

        logger.warning("Could not find matching operation, {0} in binding {1}".format(op_name, self.name), 2)


class Port(Element):
    """ Simplified, native Python representation of ports as defined within services """

    def __init__(self, bs_element, wsdl):
        super().__init__(bs_element, wsdl)
        self.__binding = None
        self.__location = None

    @property
    def binding(self) -> Binding:
        if self.__binding is None:
            logger.debug("Initializing binding attribute for port {0}".format(self.name))
            binding = self.bs_element['binding']
            (ns, name) = binding.split(':')
            self.__binding = Binding.from_name(name, self.parent)
        return self.__binding

    @property
    def location(self) -> str:
        if self.__location is None:
            logger.debug("Initializing location of Port based on address element")
            self.__location = self.bs_element('address', recursive=False)[0]['location']
            logger.info("Initialized location to {0}".format(self.__location))
        return self.__location

    @location.setter
    def location(self, location):
        self.__location = location


class Message(Element):

    def __init__(self, bs_element, wsdl):
        super().__init__(bs_element, wsdl)
        self.__parts = None

    @property
    def parts(self) -> tuple:
        if self.__parts is None:
            logger.debug("Initializing parts for message {0}".format(self.name))
            parts = list()
            for part in self.bs_element('part', recursive=False):
                parts.append(Part(part, self.parent))
            self.__parts = tuple(parts)
        return self.__parts


class Part(Element):

    def __init__(self, bs_element, wsdl):
        super().__init__(bs_element, wsdl)
        self.__type = None

    @property
    def type(self) -> Element:
        if self.__type is None:
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

    def __init__(self, bs_element, wsdl):
        super().__init__(bs_element, wsdl)
        self.__input = None
        self.__output = None
        self.__faults = None

    @property
    def input(self) -> Message:
        if self.__input is None:
            name = self.bs_element('input')[0].get('message').split(":")[1]
            self.__input = Message.from_name(name, self.parent)
        return self.__input

    @property
    def output(self) -> Message:
        if self.__output is None:
            name = self.bs_element('output')[0].get('message').split(":")[1]
            self.__output = Message.from_name(name, self.parent)
        return self.__output

    @property
    def faults(self) -> tuple:
        if self.__faults is None:
            search_results = self.bs_element('fault')
            if len(search_results) > 0:
                faults = list()
                for each in search_results:
                    faults.append(Message.from_name(each.get("message").split(":")[1], self.parent))
                self.__faults = tuple(faults)
            else:
                logger.warning("Operation has no fault message specified")
                self.__faults = tuple()
        return self.__faults
