from abc import ABCMeta, abstractmethod, abstractproperty
from copy import deepcopy
from xml.sax.saxutils import escape
from soapy import Log


class Marshaller(Log, metaclass=ABCMeta):

    """ Base class for marshalling data from Wsdl class to SOAP envelope """
    
    @abstractproperty
    def xml(self):
        
        """ Return the XML content as str """

    @abstractmethod
    def render(self):
        
        """ Resolve dependencies, namespaces, and populate xml string """
    

class Envelope(Marshaller):

    """ Class to build the envelope from InputOptions class instance from soapy.client """

    __name__ = "marshaller"

    def __init__(self, client):
        super().__init__(client.tl)
        self.__parts = client.operation.input.parts
        self.__schema = self.parts[0].type.schema
        self.log("Initializing new Envelope", 4)
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
        self.log("Registered new namespace of {0}".format(name), 5)
        self.__ns_counter += 1

    def render(self):
        self.header.render()
        self.log("Header rendered successfully", 5)
        self.body.render()
        self.log("Body rendered successfully", 5)
        for key, item in self.used_ns.items():
            self.__xml += """xmlns:{0}="{1}" """.format(key, item)
        self.__xml += ">\n"
        self.__xml += self.header.xml
        self.__xml += self.body.xml
        self.__xml += "</{0}:Envelope>".format(self.soap_ns)
        self.log("Envelope rendered successfully", 4)

    @property
    def parts(self):
        return self.__parts

    @property
    def inputs(self):
        return self.__inputs

    @property
    def tns_map(self):
        return self.__tns_map

    @property
    def xml(self):
        return self.__xml

    @property
    def body(self):
        return self.__body

    @property
    def header(self):
        return self.__header

    @property
    def schema(self):
        return self.__schema

    @property
    def soap_ns(self):
        self.used_ns["soapenv"] = "http://schemas.xmlsoap.org/soap/envelope/"
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
        self.log("Initializing new Header", 5)
        self.__xml = "<{0}:Header/>\n".format(envelope.soap_ns)

    @property
    def parent(self):
        return self.__parent

    @property
    def xml(self):
        return self.__xml

    def log(self, message, tl):
        self.parent.log(message, tl)

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
        self.log("Initializing new Body", 5)
        self.__elements = tuple([Element(envelope, part.type, i)
                                 for i, part in enumerate(self.parent.parts)])
        self.log("All Elements initialized successfully", 5)

    @property
    def parent(self):
        return self.__parent

    @property
    def elements(self) -> tuple:
        return self.__elements

    @property
    def xml(self):
        return self.__xml

    def log(self, message, tl):
        self.parent.log(message, tl)

    def render(self):
        self.log("Starting process of rendering all children Elements", 5)
        for element in self.elements:
            element.render()
        self.log("All child Elements rendered successfully", 5)
        for element in self.elements:
            self.__xml += element.xml
        self.__xml += "</{0}:Body>\n".format(self.parent.soap_ns)


class Element(Marshaller):

    """ Class for representing an Element's properties in terms of SOAP request rendering. Heavily relies on interface
     from InputOptions to build properly. Can't be used with InputFactory class inputs. """

    def __init__(self, envelope: Envelope, element, part: int, top_level=True):

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
        self.log("Initializing new Element based on {0}".format(element.name), 5)
        self.__part = part
        self.__definition = element
        self.children_have_values = False
        self.__xml = ""
        self.__open_tag = ""
        self.__close_tag = ""
        self.__inner_xml = ""

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

        self.__inputObj = None
        for obj in self.parent.inputs[self.part]:
            if obj.ref is self.definition:
                self.__inputObj = obj
                break
        # Render the open tag for this element before anything else is done
        self.render_open_tag()

    @property
    def part(self) -> int:
        return self.__part

    @property
    def definition(self):
        return self.__definition

    @property
    def inputObj(self):
        return self.__inputObj

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

    def log(self, message, tl):
        self.parent.log(message, tl)

    def children_significant(self) -> bool:

        """
        Recursively inspects self and children to determine if children need rendered.
        Requirements for needing rendered are determined based on whether a value is assigned
        :return: bool
        """

        if self.inputObj.value is not None:
            return True
        for each in self.children:
            if each.children_significant() is True:
                self.children_have_values = True
        return self.children_have_values

    def _process_null_values(self) -> bool:

        """ Sets the XML content of the tag to the appropriate form of Null, if the element should be empty,
        otherwise, return False and do nothing
        :return: bool """

        if self.inputObj.value is None:
            if self.definition.min_occurs == "0":
               self.__open_tag = ""
            elif self.definition.nillable == "true":
                self.__open_tag = self.open_tag.replace('>', ' {0}:nil="true" />\n'.format(self.parent.xml_ns))
            else:
                self.__open_tag = self.open_tag.replace('>', '/>\n')
            self.__xml = self.open_tag
            self.log("Processed null value for element {0}".format(self.definition.name), 5)
            return True
        return False

    def _process_single_value(self, value) -> None:

        """ Render inner xml appropriately for containing a single (non-Array) value """

        self.log("Setting value of element {0} to '{1}'"
                 .format(self.definition.name, value), 5)
        self.__inner_xml = escape(str(value))
        self.__xml = self.open_tag + self.inner_xml + self.close_tag

    def _process_iter_values(self, iter) -> None:

        """
        When an element supports multiple values (maxOccurs > 1) and an iterable (non-string) is provided, we will
         render each item as inner xml in between its own open and close tags
        """

        self.log("Adding values from list {0} to element {1}"
                 .format(iter, self.definition.name), 5)
        for each in iter:
            self.log("Rendering value {0}".format(each), 5)
            self.__xml += self.open_tag + escape(str(each)) + self.close_tag

    def _process_collection_values(self):

        """ Extracts the zeroth element from each collection-key and builds a new, single value collection, then renders
         children based on that collection, iteratively. """

        done = False
        collection = deepcopy(self.inputObj.collection)  # copy collections because we're going to modify it (pop)
        while not done:
            iter_collection = {}
            self.__inner_xml = ""
            try:
                for key in collection.keys():
                    iter_collection[key] = collection[key].pop()
            except IndexError:
                done = True
            if done:
                break
            self.__xml += self.open_tag + "\n"
            for child in self.children:
                child.render(iter_collection)
                self.__inner_xml += child.xml
            self.__xml += self.inner_xml + self.close_tag

    def render_open_tag(self):
        # If elementForm for the schema and element is qualified, we need to print ns,
        # otherwise, only if it's the first element
        if (self.parent.schema.element_form == "qualified" and self.definition.form == "qualified") or self.__top_level:
            self.__open_tag = "<{0}:{1}".format(self.tns, self.definition.name.strip())
        else:
            self.__open_tag = "<{0}".format(self.definition.name.strip())
        self.__children = tuple([Element(self.parent, child, self.part, False)
                                 for child in self.definition.element_children])
        # Call update to perform parent update consolidation from non-Element children
        self.definition.update(self)
        # Render attributes, and then the close brace '>'
        for attr in self.definition.attributes:
            if self.inputObj[attr.name].value is not None:
                self.__open_tag += ' {0}="{1}"'.format(attr.name, self.inputObj[attr.name].value)
        self.__open_tag += ">"

    def render(self, collection=dict()) -> None:
        """
        render performs numerous checks on the definition of the request element, which is defined in the WSDL,
        combined with the provided input object from the Client which called the Marshaller. For an Element, render
        will do tests to determine if the element is empty, and if so, render the correct representation of the tag
        as empty, otherwise it will render all children (using this same method on the child instance) and insert each
        child's xml as this element's inner_xml. For elements which contain multiple values, and which support such
        (i.e. have the maxOccurs set to larger than 1), render will appropriately handle them. The collection optional
        parameter is used by parent elements who support arrays of values, or collection, and defines the values
        children should have as a whole, instead of individually.
        param collection: The dictionary provided by parent objects who contain children elements that may be repeated
        (herein referred to as collections)
        :return:
        """

        # Override input object value from collection if matches current element name.
        try:
            self.inputObj.value = collection[self.inputObj.name]
            self.log("Using supplied collection value {0}".format(self.inputObj.value), 5)
        except KeyError:
            pass

        # Short circuit if element is empty and optional or nillable, and has no children

        if self.inputObj.setable and self.inputObj.inner_xml is None:
            if self._process_null_values():
                return

        # Build the close tag so we can render multiple times if we are an array

        if (self.parent.schema.element_form == "qualified" and self.definition.form == "qualified") or self.__top_level:
            self.__close_tag = "</{0}:{1}>\n".format(self.tns, self.definition.name.strip())
        else:
            self.__close_tag = "</{0}>\n".format(self.definition.name.strip())

        # Render each child element to make sure parent/child updates are propagated
        # before we actually render the static XML
        # Then, check to see if all children are empty.
        # If this is a collection element, then use alternative render for children to the entire collection can be
        # rendered appropriately

        if not self.inputObj.is_collection or len(self.inputObj.collection.keys()) == 0:
            for each in self.children:
                each.render()
                if each.children_significant() is True:
                    self.children_have_values = True
        else:
            self._process_collection_values()
            return

        # If all children are empty and aren't required, process null values to render element correctly, short circuit

        if not self.children_have_values and int(self.definition.min_occurs) == 0:
            if self._process_null_values():
                return

        # Update inner xml, either using child xml values, innerXml from inputObj, or the value from inputObj

        if self.inputObj.inner_xml is not None:
            self.__inner_xml = self.inputObj.inner_xml
        elif self.inputObj.setable:
            if self.definition.max_occurs == "unbounded" or int(self.definition.max_occurs) > 1:
                # Determine if a non-string iterable was passed, otherwise default to processing a single value
                if not isinstance(self.inputObj.value, str):
                    try:
                        self._process_iter_values(self.inputObj.value)
                    except TypeError:
                        self._process_single_value(self.inputObj.value)
                else:
                    self._process_single_value(self.inputObj.value)
            else:
                # Only a single value should have been provided (will get type-casted to string)
                self._process_single_value(self.inputObj.value)
        else:  # if this is only a container for child elements
            self.__inner_xml += "\n"
            for each in self.children:
                self.__inner_xml += each.xml
            self.__xml += self.open_tag + self.inner_xml + self.close_tag
