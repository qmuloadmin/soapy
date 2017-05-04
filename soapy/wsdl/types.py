""" Types are XML tags the reside inside a schema tag, inside the types tag
 They are significantly different from normal elements, as they represent the elements in
 the SOAP body as opposed to the WSDL itself, and contain helper methods to assist the Marshaller to render
 correct XML elements"""

import logging

from soapy.wsdl.element import Element

# Initialize logger for this module
logger = logging.getLogger(__name__)


class TypeBase(Element):

    def __init__(self, bs_element, wsdl, schema=None, is_local=True):
        super().__init__(bs_element, wsdl, schema, is_local)
        self.__element_children = None

    def update(self, parent=None, parent_updates=dict()):

        """ Update is recursive, goes through all children and executes the update_parent_element method on each,
        if it exists (if it doesn't, then it is also an Element, and so we don't want to update this Element with
        it's children's properties). These updates apply attributes and properties to the parent element so we
        can properly handle the child properties (like an enum, or an extension's base type).

        parent should be the Element being updated. It will be passed to all children recursively to receive all
        their updates. If not provided, it will assume the element calling update is the parent. """

    def _process_element_children(self, parents=list()) -> tuple:

        # First, process any child updates specified by TypeContainer Children

        child_updates = dict()
        try:
            c_update = self.update_child_elements()
            if c_update:
                logger.info("Found update item(s) for Children: {0}".format(c_update))
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
            logger.debug("Processing all parent-induced updates for all children")
            for child in children:
                for attr, value in child_updates.items():
                    child.bs_element[attr] = value
        self.__element_children = tuple(children)
        logger.debug("All TypeElement children identified")
        return self.__element_children

    @property
    def element_children(self) -> tuple:
        if self.__element_children is None:
            logger.debug("In recursive process of isolating and updating TypeElement children")
            self._process_element_children([self.bs_element])
        return self.__element_children


class TypeContainer(TypeBase):
    """ Any <tag> defined in a schema that is not an element. In other words, it contains or
    describes other elements. E.g, <sequence> or <complexType> """

    def __init__(self, bs_element, wsdl, schema=None, is_local=True):
        super().__init__(bs_element, wsdl, schema, is_local)
        self.__parent_attributes = None

    def update(self, parent=None, parent_updates=dict()):
        parent_updates.update(self.update_parent_element(parent))
        for child in self.children:
            if isinstance(child, TypeContainer):
                child.update(parent, parent_updates)

    @property
    def parent_attributes(self) -> tuple:
        """ Returns the attributes defined within this tag, and any non-element children """
        if self.__parent_attributes is None:
            attrs = list()
            logger.debug("In recursive process of consolidating attributes. Current object is '{0}' the {1}"
                         .format(self.name, self.tag))
            attributes = self.bs_element('attribute', recursive=False)
            for attribute in attributes:
                attr = Attribute(attribute, self.parent)
                logger.debug("Created attribute {0}".format(attr))
                attrs.append(attr)
            for child in self.children:
                try:
                    attrs.extend(child.parent_attributes)
                except AttributeError:
                    """ Do nothing, because this means it's an Element """

            self.__parent_attributes = tuple(attrs)
        return self.__parent_attributes

    def update_parent_element(self, parent) -> dict:
        
        """ This occurs when update() is called on 
        a TypeElement object, and takes characteristics defined by TypeContainer
        subclasses and merges them with the parent TypeElement.
        :param parent: The TypeElement parent object to be updated """

        return {}

    def update_child_elements(self) -> dict:
        
        """ Called during elementChildren property construction. A dict of attribute
        changes that should be made to the child bsElement attributes """

        return {}


class TypeElement(TypeBase):
    """ Class containing attributes and properties of an element in a Type definition """

    def __init__(self, bs_element, wsdl, schema=None, is_local=True):
        super().__init__(bs_element, wsdl, schema, is_local)

        # Attributes that are evaluated lazy
        self.__attributes = None
        self.__children = None

    def update(self, parent=None, updates=dict()):
        """ update for an Element means take the returned, consolidated values of children and apply them to self """
        updates = dict()
        for child in self.children:
            if isinstance(child, TypeContainer):
                child.update(self, updates)
        logger.debug("Updating {} with attributes from child elements: {}".format(self.name, updates))
        for key, value in updates.items():
            try:
                self.bs_element[key].append(value)
            except (AttributeError, KeyError):
                self.bs_element[key] = value

    @property
    def attributes(self) -> tuple:
        if self.__attributes is None:
            logger.debug("Initializing list of attributes for element {0}".format(self.name))
            attributes = self.bs_element('attribute', recursive=False)
            for attribute in attributes:
                attributes.append(Attribute(attribute, self.parent))
            for child in self.children:
                try:
                    attributes.extend(child.parent_attributes)
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
        """ min_occurs reflects the configured minimum number of times an element may appear in the SOAP envelope.
        It is based on the schema type configuration. By default, an element with min_occurs=0 and None value will
        not appear at all in the rendered envelope -- however, some services use self-closing tags to identify which
        elements to return, so you may need an empty tag to appear, even if it's set to min_occurs=0. For this reason,
        you can override the behavior by setting min_occurs to 1 """
        try:
            return self.__min_occurs
        except AttributeError:
            return self.bs_element.get("minOccurs", "1")

    @min_occurs.setter
    def min_occurs(self, value):
        self.__min_occurs = str(value)

    @property
    def form(self) -> str:
        return self.bs_element.get("form", "qualified")

    @property
    def enums(self) -> tuple:
        return tuple(self.bs_element.get("enum_hint", []))

    @property
    def type(self) -> str:
        try:
            return self.bs_element['type']
        except KeyError:
            return None

    @property
    def children(self) -> tuple:
        """ Overriding parent method definition to resolve soft children via type declarations """

        if self.__children is None:
            children = list(super().children)
            if self.type:
                soft_child = self.parent.find_type_by_name(self.type, self.schema.name)
                if soft_child is not None:
                    if self.bs_element.counter < 2:
                        children.append(soft_child)
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


class Union(TypeContainer):
    """ Class representing a combination of SimpleTypes (for type value enforcement) """


class ComplexContent(TypeContainer):
    """ Class representing a dynamic container of other types """


class SimpleContent(TypeContainer):
    """ Class representing a container modifying an element type """


class Extension(TypeContainer):
    """ Class representing a tag extending other types.
    Will need to update to add Attributes defined within to parent """

    @property
    def children(self) -> tuple:
        children = list()
        try:
            # Add children for each element in the base type, specified in the Extension tag
            child = self.parent.find_type_by_name(self.bs_element['base'])
            children.append(child)
        except KeyError:
            pass
        super_children = list(super().children)
        for i, child in enumerate(super_children):
            if child == self:
                break
        # Insert the new children in the place where this element was located
        super_children[i:i] = children
        return tuple(super_children)


class Annotation(TypeContainer):
    """ Class representing a WSDL-comment to provide information to the user or client """


class Documentation(TypeContainer):
    """ Class representing documentation to be presented to the end-user """

    def update_parent_element(self, parent) -> dict:
        return {"docstring": self.bs_element.text}


class Restriction(TypeContainer):
    """ Class representing a tag restricting types. May need updated in the future
    to provide a validate() method on rendering to ensure the value is compatible. This is not a supported or required
    feature at the moment. Restriction types ignore all children, providing the base type instead. """

    @property
    def children(self) -> tuple:
        logger.debug("Adding base child of Restriction type '{}'".format(self.name))
        children = list()
        try:
            child = self.parent.find_type_by_name(self.bs_element['base'])
            children.append(child)
        except KeyError:
            pass
        return tuple(children)


class Choice(TypeContainer):
    """ Class representing a tag containing a choice of Elements. May need to update to provide choice hints to
    children """

    def update_child_elements(self) -> dict:
        return {"minOccurs": "0"}


class Enumeration(TypeContainer):
    """ Class representing an enumeration, or a list of possible values. Provides enum_hint to the parent Element """

    def update_parent_element(self, parent) -> dict:
        return {"enum_hint": [self.bs_element["value"]]}


class SequenceType(TypeContainer):
    """ Class representing an ordered sequence of types """
