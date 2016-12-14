from soapy.wsdl.element import Element

""" Types are XML tags the reside inside a schema tag, inside the types tag
 They are significantly different from normal elements, as they represent the elements in
 the SOAP body as opposed to the WSDL itself, and contain helper methods to assist the Marshaller to render
 correct XML elements"""


class TypeBase(Element):

    def update(self, parent, parent_updates=dict()):

        for child in self.children:
            if child is None:
                continue
            try:
                parent_updates.update(self.update_parent_element(parent))
            except (TypeError, AttributeError):
                pass
            child.update(parent, parent_updates)
        if isinstance(self, TypeElement):
            for key, value in parent_updates:
                self.bs_element[key] = value

    def _process_element_children(self, parents=list()) -> tuple:

        # First, process any child updates specified by TypeContainer Children

        child_updates = dict()
        try:
            c_update = self.update_child_elements()
            if c_update is not None:
                self.log("Found update item(s) for Children: {0}".format(c_update), 4)
                child_updates.update(c_update)
        except AttributeError:
            """ Do nothing, we are in a TypeElement object """

        # Next, Extend the list of children with each child's element children

        children = list()
        for each in self.children:
            if isinstance(each, TypeElement):
                if each.bs_element not in parents:
                    children.append(each)
            elif each is None:
                continue
            else:
                parents.append(self.bs_element)
                children.extend(each._process_element_children(parents))

        # Lastly, apply all child updates to each child element

        if len(child_updates) > 0:
            self.log("Processing all parent-induced updates for all children", 5)
            for child in children:
                for attr, value in child_updates.items():
                    child.bs_element[attr] = value
        self.__element_children = tuple(children)
        self.log("All TypeElement children identified", 5)
        return self.__element_children

    @property
    def element_children(self) -> tuple:
        try:
            return self.__element_children
        except AttributeError:
            self.log("In recursive process of isolating and updating TypeElement children", 5)
            return self._process_element_children([self.bs_element])


class TypeContainer(TypeBase):
    """ Any <tag> defined in a schema that is not an element. In other words, it contains or
    describes other elements. E.g, <sequence> or <complexType> """

    @property
    def parent_attributes(self) -> tuple:

        """ Returns the attributes defined within this tag, and any non-element children """

        try:
            return self.__parent_attributes
        except AttributeError:
            attrs = list()
            self.log("In recursive process of consolidating attributes. Current object is '{0}' the {1}"
                     .format(self.name, self.tag), 5)
            attributes = self.bs_element('attribute', recursive=False)
            for attribute in attributes:
                attr = Attribute(attribute, self.parent)
                self.log("Created attribute {0}".format(attr), 5)
                attrs.append(attr)
            for child in self.children:
                try:
                    attrs.extend(child.parentAttributes)
                except AttributeError:
                    """ Do nothing, because this means it's an Element """

            self.__parent_attributes = tuple(attrs)
            return self.__parent_attributes

    def update_parent_element(self, parent) -> dict:
        
        """ This occurs when update() is called on 
        a TypeElement object, and takes characteristics defined by TypeContainer
        subclasses and merges them with the parent TypeElement.
        :param parent: The TypeElement parent object to be updated """

    def update_child_elements(self) -> dict:
        
        """ Called during elementChildren property construction. A dict of attribute
        changes that should be made to the child bsElement attributes """


class TypeElement(TypeBase):
    """ Class containing attributes and properties of an element in a Type definition """

    @property
    def attributes(self) -> tuple:
        try:
            return self.__attributes
        except:
            self.log("Initializing list of attributes for element {0}".format(self.name), 5)
            attributes = self.bs_element('attribute', recursive=False)
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
        return self.bs_element.get("nillable", "false")

    @property
    def max_occurs(self) -> str:
        return self.bs_element.get("maxOccurs", "1")

    @property
    def min_occurs(self) -> str:
        return self.bs_element.get("minOccurs", "1")

    @property
    def form(self) -> str:
            return self.bs_element.get("form", "qualified")

    @property
    def type(self) -> str:
        try:
            return self.bs_element['type']
        except KeyError:
            return None

    @property
    def children(self) -> tuple:

        """ Augmenting parent method definition to resolve soft children via type declarations """

        try:
            return self.__children
        except AttributeError:
            children = list(super().children)
            if len(children) == 0:
                softChild = self.parent.find_type_by_name(self.type, self.schema.name)
                if softChild is not None:
                    if self.bs_element.counter < 2:
                        children.append(softChild)
            self.__children = tuple(children)
            return self.__children


class Attribute(Element):
    """ Class containing properties of element attributes in a SOAP Envelope created from WSDL """

    @property
    def type(self) -> str:
        return self.bs_element['type'].split(":")[1]

    @property
    def ns(self) -> str:
        return self.bs_element['type'].split(":")[0]

    @property
    def default(self) -> str:
        return self.bs_element.get('default',
                                   self.bs_element.get("fixed", None))

    @property
    def fixed(self) -> bool:
        return self.bs_element.get('fixed', False)


class ComplexType(TypeContainer):
    """ Class representing a dynamic container of simpler types """


class SimpleType(TypeContainer):
    """ Class representing type value enforcement """


class ComplexContent(TypeContainer):
    """ Class representing a dynamic container of other types """


class SimpleContent(TypeContainer):
    """ Class representing a container modifying an element type """


class Extension(TypeContainer):
    """ Class representing a tag extending other types """

    @property
    def children(self) -> tuple:
        children = list(super().children)
        try:
            child = self.parent.find_type_by_name(self.bs_element['base'])
            children.append(child)
        except KeyError:
            pass
        return tuple(children)


class SequenceType(TypeContainer):
    """ Class representing an ordered sequence of types """

    def update_parent_element(self, parent) -> dict:
        return {"type": parent.type}

