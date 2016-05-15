from soapy.wsdl.element import Element

""" Types are XML tags the reside inside a schema tag, inside the types tag
 They are significantly different from normal elements, as they represent the elements in
 the SOAP body as opposed to the WSDL itself """

class TypeContainer(Element):
    """ Any <tag> defined in a schema that is not an element. In other words, it contains or
	describes other elements. E.g, <sequence> or <complexType> """

    @property
    def parentAttributes(self) -> tuple:

        """ Returns the attributes defined within this tag, and any non-element children """

        try:
            return self.__parentAttributes
        except:
            attrs = list()
            self._log("In recursive process of consolidating attributes. Current object is '{0}' the {1}"
                      .format(self.name, self.tag), 5)
            attributes = self.bsElement('attribute', recursive=False)
            for attribute in attributes:
                attr = Attribute(attribute, self.parent)
                self._log("Created attribute {0}".format(attr), 5)
                attrs.append(attr)
            for child in self.children:
                try:
                    attrs.extend(child.parentAttributes)
                except AttributeError:
                    """ Do nothing, because this means it's an Element """

            self.__parentAttributes = tuple(attrs)
            return self.__parentAttributes


class TypeElement(Element):
    """ Class containing attributes and properties of an element in a Type definition """

    @property
    def attributes(self) -> tuple:
        try:
            return self.__attributes
        except:
            self._log("Initializing list of attributes for element {0}".format(self.name), 5)
            attributes = self.bsElement('attribute', recursive=False)
            for attribute in attributes:
                attributes.append(Attribute(attribute, self.parent))
            for child in self.children:
                try:
                    attributes.extend(child.parentAttributes)
                except AttributeError:
                    """ Do nothing, because this means it's an Element """

            self.__attributes = tuple(attributes)
            return self.__attributes

    @property
    def nillable(self) -> str:
        return self.bsElement.get("nillable", "false")

    @property
    def maxOccurs(self) -> str:
        return self.bsElement.get("maxOccurs", "1")

    @property
    def minOccurs(self) -> str:
        return self.bsElement.get("minOccurs", "1")

    @property
    def type(self):
        return self.bsElement['type']

    @property
    def children(self):

        """ Augmenting parent method definition to resolve soft children via type declarations """

        try:
            return self.__children
        except AttributeError:
            children = list(super().children)
            if len(children) == 0:
                softChild = self.parent.findTypeByName(self.type)
                if softChild is not None:
                    children.append(softChild)
            self.__children = tuple(children)
            return self.__children


class Attribute(Element):
    """ Class containing properties of element attributes in a SOAP Envelope created from WSDL """

    @property
    def type(self) -> str:
        return self.bsElement['type'].split(":")[1]

    @property
    def ns(self) -> str:
        return self.bsElement['type'].split(":")[0]

    @property
    def default(self) -> str:
        return self.bsElement.get('default', None)


class ComplexType(TypeContainer):
    """ Class representing a dynamic container of simpler types """


class SequenceType(TypeContainer):
    """ Class representing an unnamed sequence of types """

    @property
    def name(self):
        return "anonymous"

