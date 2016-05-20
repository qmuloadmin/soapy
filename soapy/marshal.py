from abc import ABCMeta, abstractmethod, abstractproperty


class Marshaller(metaclass=ABCMeta):

    """ Base class for marshalling data from Wsdl class to SOAP envelope """
    
    @abstractproperty
    def xml(self):
        
        """ Return the XML content as str """

    @abstractmethod
    def render(self):
        
        """ Resolve dependencies, namespaces, and populate xml string """

    @abstractmethod
    def log(self, message, tl):

        """ Map to correct logging instance based on instance heredity
        Args:
            message (str): the message to be logged if tracelevel is high enough
            tl (int): The importance of the message, 0 is critical, 5 is debug """
    

class Envelope(Marshaller):

    """ Class to build the envelope """

    def __init__(self, client):
        self.__parts = client.operation.input.parts
        self.__schema = self.parts[0].type.schema
        self.log("Initializing new Envelope", 4)
        self.usedNs = dict()
        self.usedNs["tns"] = self.schema.name
        self.__targetNs = "tns"
        self.__tnsMap = {}
        self.__nsCounter = 1
        self.__xml = """<{0}:Envelope """.format(self.soapNs)
        self.__inputs = client.inputs
        self.__body = Body(self)
        self.__header = Header(self)

    def registerNamespace(self, definition, object):

        """  When an element is not in the same schema (and thus NS) as the Body/Envelope,
        we need to define and declare it, as well as be able to tell the element what its
        namespace is. This function adds a new namespace when provided a location definition
        after ensuring the same namespace hasn't already been added
        :param definition: The url of the schema, e.g. http://test/commonTypes/schema
        :param object: The object reference to be used in tnsMap so the object can tell which ns to use
        :return: None
        """

        for name, value in self.usedNs.items():
            if value == definition:
                self.__tnsMap[object] = name
                return
        name = self.targetNs + str(self.__nsCounter)
        self.usedNs[name] = definition
        self.__tnsMap[object] = name
        self.log("Registered new namespace of {0}".format(name), 5)
        self.__nsCounter += 1

    def render(self):
        self.header.render()
        self.log("Header rendered successfully", 5)
        self.body.render()
        self.log("Body rendered successfully", 5)
        for key, item in self.usedNs.items():
            self.__xml += """xmlns:{0}="{1}" """.format(key, item)
        self.__xml += ">\n"
        self.__xml += self.header.xml
        self.__xml += self.body.xml
        self.__xml += "</{0}:Envelope>".format(self.soapNs)
        self.log("Envelope rendered successfully", 4)

    def log(self, message, tl):
        self.schema.parent.log(message, tl)

    @property
    def parts(self):
        return self.__parts

    @property
    def inputs(self):
        return self.__inputs

    @property
    def tnsMap(self):
        return self.__tnsMap

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
    def soapNs(self):
        self.usedNs["soapenv"] = "http://schemas.xmlsoap.org/soap/envelope/"
        return "soapenv"

    @property
    def targetNs(self):
        return self.__targetNs


class Header(Marshaller):

    """ Class to build the header """

    def __init__(self, envelope: Envelope):

        self.__parent = envelope
        self.log("Initializing new Header", 5)
        self.__xml = "<{0}:Header/>\n".format(envelope.soapNs)

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

    """ Class to build the Body of the SOAP envelope """

    def __init__(self, envelope: Envelope):

        self.__xml = "<{0}:Body>\n".format(envelope.soapNs)
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
        self.__xml += "</{0}:Body>\n".format(self.parent.soapNs)


class Element(Marshaller):

    """ Class for representing an Element's properties in terms of SOAP request rendering """

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

        # Check to see if the schema of the element is the same as the body/envelope default tns.
        # If not, then we need to update the Envelope with a new xmlns definition and use a different
        # ns in our tags

        if self.definition.schema.name is not self.parent.schema.name:
            self.parent.registerNamespace(self.definition.schema.name,
                                          self)
            self.tns = self.parent.tnsMap[self]
        else:
            self.tns = self.parent.targetNs

        # If elementForm for the schema is qualified, we need to print ns, otherwise, only if it's the first element
        if self.definition.schema.elementForm == "qualified" or self.__top_level:
            self.__xml = "<{0}:{1} ".format(self.tns, self.definition.name.strip())
        else:
            self.__xml = "<{0} ".format(self.definition.name.strip())
        self.__children = tuple([Element(envelope, child, self.part, False)
                                for child in self.definition.elementChildren])

    @property
    def part(self) -> int:
        return self.__part

    @property
    def definition(self):
        return self.__definition

    @property
    def parent(self) -> Envelope:
        return self.__parent

    @property
    def xml(self) -> str:
        return self.__xml

    @property
    def children(self) -> tuple:
        return self.__children

    def log(self, message, tl):
        self.parent.log(message, tl)

    def render(self):

        # Pair the WSDL definitions element with the input from client

        inputObj = None
        for obj in self.parent.inputs[self.part]:
            if obj.ref is self.definition:
                inputObj = obj
                break
        # Bail out early if empty and optional

        if inputObj.setable and inputObj.innerXml is None:
            if inputObj.value is None:
                if self.definition.minOccurs == "0":
                    self.__xml = ""
                    return

        # Call update to perform parent update consolidation from non-Element children

        self.definition.update(self)

        # Render each child element to make sure parent/child updates are propagated
        # before we actually render the static XML

        for each in self.children:
            each.render()

        for attr in self.definition.attributes:
            if inputObj[attr.name].value is not None:
                self.__xml += """{0}="{1}" """.format(attr.name, inputObj[attr.name].value)

        self.__xml += ">"

        # Update inner xml, either using child xml values, or innerXml from inputObj

        if inputObj.innerXml is not None:
            self.__xml += inputObj.innerXml
        elif inputObj.setable:
            if inputObj.value is not None:
                self.__xml += inputObj.value
        else:
            self.__xml += "\n"
            for each in self.children:
                self.__xml += each.xml

        if self.parent.schema.elementForm == "qualified" or self.__top_level:
            self.__xml += "</{0}:{1}>\n".format(self.tns, self.definition.name.strip())
        else:
            self.__xml += "</{0}>\n".format(self.definition.name.strip())
