import logging
from abc import ABCMeta, abstractmethod, abstractproperty
from xml.sax.saxutils import escape

from soapy.inputs import Repeatable, Element as InputElement

# Initialize logger for this module
logger = logging.getLogger(__name__)


class Marshaller(metaclass=ABCMeta):

    """ Base class for marshalling data from Wsdl class to SOAP envelope """
    
    @abstractproperty
    def xml(self):
        
        """ Return the XML content as str """

    @abstractmethod
    def render(self):
        
        """ Resolve dependencies, namespaces, and populate xml string """


class Envelope(Marshaller):

    """ Class to build the envelope from InputOptions class instance from soapy.client """

    def __init__(self, client):
        self.__parts = client.operation.input.parts
        self.__schema = self.parts[0].type.schema
        self.__version = client.wsdl.version
        logger.info("Initializing new Envelope")
        self.used_ns = dict()
        self.used_ns["tns"] = self.schema.name
        self.__targetNs = "tns"
        self.__tns_map = {}
        self.__ns_counter = 1
        self.__xml = """<{0}:Envelope """.format(self.soap_ns)
        self.__inputs = client.inputs
        self.__body = Body(self)
        self.__header = Header(self)

    def register_namespace(self, definition, object):

        """  When an element is not in the same schema (and thus NS) as the Body/Envelope,
        we need to define and declare it, as well as be able to tell the element what its
        namespace is. This function adds a new namespace when provided a location definition
        after ensuring the same namespace hasn't already been added
        :param definition: The url of the schema, e.g. http://test/commonTypes/schema
        :param object: The object reference to be used in tnsMap so the object can tell which ns to use
        :return: None
        """

        for name, value in self.used_ns.items():
            if value == definition:
                self.__tns_map[object] = name
                return
        name = self.target_ns + str(self.__ns_counter)
        self.used_ns[name] = definition
        self.__tns_map[object] = name
        logger.debug("Registered new namespace of {0}".format(name))
        self.__ns_counter += 1

    def render(self):
        self.header.render()
        logger.debug("Header rendered successfully")
        self.body.render()
        logger.debug("Body rendered successfully")
        for key, item in self.used_ns.items():
            self.__xml += """xmlns:{0}="{1}" """.format(key, item)
        self.__xml += ">\n"
        self.__xml += self.header.xml
        self.__xml += self.body.xml
        self.__xml += "</{0}:Envelope>".format(self.soap_ns)
        logger.info("Envelope rendered successfully")

    @property
    def parts(self):
        return self.__parts

    @property
    def inputs(self):
        """ The InputOptions from the client instance specifying values to be rendered in this envelope """
        return self.__inputs

    @property
    def tns_map(self):
        return self.__tns_map

    @property
    def xml(self) -> str:
        """ The full XML SOAP envelope, as a string """
        return self.__xml

    @xml.setter
    def xml(self, xml):
        self.__xml = xml

    @property
    def body(self):
        return self.__body

    @property
    def version(self):
        return self.__version

    @property
    def header(self):
        return self.__header

    @property
    def schema(self):
        return self.__schema

    @property
    def soap_ns(self):
        if self.version == 1.1:
            self.used_ns["soapenv"] = "http://schemas.xmlsoap.org/soap/envelope/"
        elif self.version == 1.2:
            self.used_ns["soapenv"] = "http://www.w3.org/2003/05/soap-envelope"
        return "soapenv"

    @property
    def xml_ns(self):
        self.used_ns["xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
        return "xsi"

    @property
    def target_ns(self):
        return self.__targetNs

    def __str__(self):
        return self.xml


class Header(Marshaller):

    """ Class to build and represent the header of the XML request """

    def __init__(self, envelope: Envelope):

        self.__parent = envelope
        logger.debug("Initializing new Header")
        self.__xml = "<{0}:Header/>\n".format(envelope.soap_ns)

    @property
    def parent(self):
        return self.__parent

    @property
    def xml(self):
        return self.__xml

    def render(self):

        """ Header does nothing as it has no dependencies.
        Place holder for possible future functionality and
        satisfies the abstract implementation """


class Body(Marshaller):

    """ Class to build the Body of the SOAP envelope based on InputOptions or InputFactory class from soapy.client
     InputFactory functionality currently not implemented """

    def __init__(self, envelope: Envelope):

        self.__xml = "<{0}:Body>\n".format(envelope.soap_ns)
        self.__parent = envelope
        logger.debug("Initializing new Body")
        self.__elements = tuple([Element(envelope, part.type, i)
                                 for i, part in enumerate(self.parent.parts)])
        logger.debug("All Elements initialized successfully")

    @property
    def parent(self):
        return self.__parent

    @property
    def elements(self) -> tuple:
        return self.__elements

    @property
    def xml(self):
        return self.__xml

    def render(self):
        logger.debug("Starting process of rendering all children Elements")
        for element in self.elements:
            element.render()
        logger.debug("All child Elements rendered successfully")
        for element in self.elements:
            self.__xml += element.xml
        self.__xml += "</{0}:Body>\n".format(self.parent.soap_ns)


class Element(Marshaller):

    """ Class for representing an Element's properties in terms of SOAP request rendering. Heavily relies on interface
     from InputOptions to build properly. Can't be used with InputFactory class inputs. """

    def __init__(self, envelope: Envelope, element, part: int, top_level=True, input_obj=None):

        """
        :param envelope: The instance of the parent Envelope class for this element
        :param element: The instance of the TypeElement class defining this element
        :param part: The part index (from soapy.client.Client.inputs tuple)
        :param top_level: Indicates if the element is the first in the Body. This is used for
        namespace qualification when elementForm is unqualified
        :return: None
        """

        self.__top_level = top_level
        self.__parent = envelope
        logger.debug("Initializing new Element based on {0}".format(element.name))
        self.__part = part
        self.__definition = element
        self.__children = tuple(
            [Element(self.parent, child, self.part, False)
             for child in self.definition.element_children]
        )
        self.children_have_values = False
        self.__xml = ""
        self.__open_tag = ""
        self.__close_tag = ""
        self.__inner_xml = ""
        self.should_be_rendered = True

        # Check to see if the schema of the element is the same as the body/envelope default tns.
        # If not, then we need to update the Envelope with a new xmlns definition and use a different
        # ns in our tags

        if self.definition.schema.name is not self.parent.schema.name:
            self.parent.register_namespace(self.definition.schema.name,
                                           self)
            self.tns = self.parent.tns_map[self]
        else:
            self.tns = self.parent.target_ns

        # Associate input obj from client with this Element rendering

        self.__input_obj = None
        if input_obj is None:
            for obj in self.parent.inputs[self.part].items:
                if obj.ref is self.definition:
                    self.__input_obj = obj
                    break
        else:
            self.__input_obj = input_obj

        # Repeatable types shouldn't be rendered under any circumstances, so immediately set to false
        # And we need to add duplicate children with separate values for each child input.Element so they can
        # be rendered individually
        if isinstance(self.input_obj, Repeatable):
            self.should_be_rendered = False
            children = list()
            for item in self.input_obj:
                children.append(
                    Element(
                        self.parent,
                        self.definition,
                        self.part,
                        False,
                        item
                    )
                )
            children.extend(self.children)
            self.__children = tuple(children)

        # Render the open tag for this element before anything else is done if should be rendered
        if self.should_be_rendered:
            self.render_open_tag()

    @property
    def part(self) -> int:
        return self.__part

    @property
    def definition(self):
        return self.__definition

    @property
    def input_obj(self):
        return self.__input_obj

    @property
    def parent(self) -> Envelope:
        return self.__parent

    @property
    def xml(self) -> str:
        return self.__xml

    @property
    def open_tag(self) -> str:
        return self.__open_tag

    @property
    def close_tag(self) -> str:
        return self.__close_tag

    @property
    def inner_xml(self) -> str:
        return self.__inner_xml

    @property
    def children(self) -> tuple:
        return self.__children

    def children_significant(self) -> bool:

        """
        Recursively inspects self and children to determine if children need rendered.
        Requirements for needing rendered are determined based on whether a value is assigned
        :return: bool
        """

        if isinstance(self.input_obj, InputElement) \
                and (self.input_obj.value is not None or not self.input_obj.all_attributes_empty):
            return True
        for each in self.children:
            if each.children_significant() is True:
                self.children_have_values = True
        return self.children_have_values

    def _process_null_values(self) -> bool:

        """ Sets the XML content of the tag to the appropriate form of Null, if the element should be empty,
        otherwise, return False and do nothing
        :return: bool """

        if self.input_obj.setable and self.input_obj.value is None:
            if self.definition.min_occurs == "0" and self.input_obj.all_attributes_empty:
                self.__open_tag = ""
            elif self.definition.nillable == "true" and self.input_obj.all_attributes_empty:
                self.__open_tag = self.open_tag.replace('>', ' {0}:nil="true" />\n'.format(self.parent.xml_ns))
            else:
                self.__open_tag = self.open_tag.replace('>', '/>\n')
            self.__xml = self.open_tag
            logger.debug("Processed null value for element {0}".format(self.definition.name))
            return True
        return False

    def _process_single_value(self, value) -> None:

        """ Render inner xml appropriately for containing a single (non-Array) value """

        logger.debug("Setting value of element {0} to '{1}'".format(self.definition.name, value))
        self.__inner_xml = escape(str(value))
        self.__xml = self.open_tag + self.inner_xml + self.close_tag

    def render_open_tag(self):
        # If elementForm for the schema and element is qualified, we need to print ns,
        # otherwise, only if it's the first element
        if (self.parent.schema.element_form == "qualified" and self.definition.form == "qualified") or self.__top_level:
            self.__open_tag = "<{0}:{1}".format(self.tns, self.definition.name.strip())
        else:
            self.__open_tag = "<{0}".format(self.definition.name.strip())
        # Call update to perform parent update consolidation from non-Element children
        self.definition.update(self)
        # Render attributes, and then the close brace '>'
        for attr in self.definition.attributes:
            if self.input_obj[attr.name].value is not None:
                self.__open_tag += ' {0}={1}'.format(attr.name, self.input_obj[attr.name].value)
        self.__open_tag += ">"

    def render(self) -> None:
        """
        render performs numerous checks on the definition of the request element, which is defined in the WSDL,
        combined with the provided input object from the Client which called the Marshaller. For an Element, render
        will do tests to determine if the element is empty, and if so, render the correct representation of the tag
        as empty, otherwise it will render all children (using this same method on the child instance) and insert each
        child's xml as this element's inner_xml. For elements which contain multiple values, and which support such
        (i.e. have the maxOccurs set to larger than 1), render will appropriately handle them. 
        :return:
        """

        # Top level short circuit for input elements that aren't rendered -- like Repeatables and Collections
        if not self.should_be_rendered:
            for each in self.children:
                each.render()
                self.__xml += each.xml
            return

        # Short circuit if element is empty and optional or nillable, and has no children

        if self.input_obj.setable and self.input_obj.inner_xml is None:
            if self._process_null_values():
                return

        # Build the close tag

        if (self.parent.schema.element_form == "qualified" and self.definition.form == "qualified") or self.__top_level:
            self.__close_tag = "</{0}:{1}>\n".format(self.tns, self.definition.name.strip())
        else:
            self.__close_tag = "</{0}>\n".format(self.definition.name.strip())

        # Render each child element to make sure parent/child updates are propagated
        # before we actually render the static XML
        # Then, check to see if all children are empty.
        # If this is a collection element, then use alternative render for children to the entire collection can be
        # rendered appropriately

        for each in self.children:
            each.render()
            if each.children_significant() is True:
                self.children_have_values = True

        # If all children are empty and aren't required, process null values to render element correctly, short circuit

        if not self.children_have_values and int(self.definition.min_occurs) == 0:
            if self._process_null_values():
                return

        # Update inner xml, either using child xml values, innerXml from inputObj, or the value from inputObj

        if self.input_obj.inner_xml is not None:
            self.__inner_xml = self.input_obj.inner_xml
            self.__xml = self.open_tag + self.inner_xml + self.close_tag
        elif isinstance(self.input_obj, InputElement):
            # Only a single value should have been provided (will get type-casted to string)
            self._process_single_value(self.input_obj.value)
        else:  # if this is only a container for child elements
            self.__inner_xml += "\n"
            for each in self.children:
                self.__inner_xml += each.xml
            self.__xml += self.open_tag + self.inner_xml + self.close_tag
