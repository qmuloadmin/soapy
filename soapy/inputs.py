""" A class representation of all possible input types """

import logging
from os import linesep
from xml.sax.saxutils import quoteattr

# Initialize logger for this module
logger = logging.getLogger(__name__)


class Base:

    def __init__(self, name, parent, wsdl_type, update_parent=True):
        self.__parent = parent
        self.__name = name
        self.__depth = None
        logger.info("Initializing new {} element with name '{}'".format(self.__class__.__name__, self.name))
        self.__ref = wsdl_type
        # Run the update method here, so we see any type hints that were provided, or any other needed updates
        # See wsdl.types.Base.update() for more information
        self.ref.update()
        self.__setable = True
        self.__repeatable = False
        self.__empty = True
        if isinstance(self.parent, Container) and update_parent:
            self.parent.append_child(self)

    def __str__(self):
        doc = self.ref.bs_element.get("docstring", "")
        if doc:
            return "{}<!--- {} -->{}".format(self._str_indent, doc, linesep)
        return ""

    @property
    def _str_indent(self) -> str:
        if self.depth == 0:
            return ""
        return " |   " * self.depth

    @property
    def parent(self):
        return self.__parent

    @property
    def is_empty(self):
        """ Tracks the state of whether or not the element (and all child elements) is empty. """
        return self.__empty

    @is_empty.setter
    def is_empty(self, state):
        # Set the parents to not empty
        if self.parent is not None:
            self.parent.is_empty = state
        self.__empty = state

    @property
    def inner_xml(self) -> str:
        """ Represents the xml of the element, including all children, values, etc. If set, then the value of the
        input will be ignored, as well as any child objects defined in the WSDL. Instead, the value of
        inner_xml will be used verbatim, in place. """

        try:
            return self.__inner_xml
        except AttributeError:
            return None

    @inner_xml.setter
    def inner_xml(self, xml: str):
        self.__inner_xml = xml

    @property
    def name(self) -> str:
        return self.__name

    @property
    def depth(self) -> int:
        if self.__depth is not None:
            return self.__depth
        else:
            # Determine the depth
            self.__depth = 0

            def inc(_):
                self.__depth += 1
                return self.__depth
            self._map_parents(inc)
            return self.__depth

    @property
    def setable(self) -> bool:
        """ Indicates whether the object can contain a value, or just contains other elements. If the object can have
        a value, then you can set it with:
            InputElement.value = "foo"
        """

        return self.__setable

    @property
    def repeatable(self):
        """ Indicates whether the element should only appear (at most) once in the rendered document (single value)
        or whether it can accept an iterable value, and will thus be (possibly) repeated in the rendered document """

        return self.__repeatable

    @property
    def ref(self):
        return self.__ref

    def _map_parents(self, func):
        """ Map a function to take action on every parent, recursively, until None is found
        Provided function will be passed the current parent """

        working_parent = self.parent
        result = None
        while working_parent is not None:
            result = func(working_parent)
            working_parent = working_parent.parent
        return result


class RenderOptionsMixin:
    """ Mixing for applying methods that alter render behavior beyond simple values, etc """

    def render_empty(self):
        """ Configures the element to be included in the rendered envelope even when empty and min_occurs = 0"""
        logger.info("Setting Element {} to be rendered even when empty".format(self.name))
        self.ref.min_occurs = "1"
        if isinstance(self.parent, RenderOptionsMixin):
            self.parent.render_empty()


class AttributableMixin:
    """ Mixin supplying attribute retrieval and setting to input elements that support attributes """

    def __init__(self):
        attrs = list()
        attributes = self.ref.attributes
        for attr in attributes:
            attrs.append(Attribute(attr.name, attr.default))
        self.__attrs = tuple(attrs)

    @property
    def attributes(self) -> tuple:
        return self.__attrs

    @property
    def all_attributes_empty(self) -> bool:
        for attr in self.attributes:
            if attr.value is not None:
                return False
        return True

    def keys(self):
        return tuple([attr.name for attr in self.attributes])

    def __getitem__(self, item):
        """ retrieves the attribute on the element in bs4-style """
        for attr in self.attributes:
            if attr.name == item:
                return attr
        raise AttributeError("{} object has no element attribute {}".format(self.__class__.__name__, item))


class Element(Base, AttributableMixin, RenderOptionsMixin):
    """ A base input Element is capable of being assigned a value ('setable') and is not repeatable """

    def __init__(self, name, parent, wsdl_type, update_parent=True):
        super().__init__(name, parent, wsdl_type, update_parent)
        self.__value = None
        AttributableMixin.__init__(self)

    def __str__(self):
        prefix = ""
        if self.ref.enums:
            prefix = "{}<!--- Enum hints: {}  -->{}".format(self._str_indent, self.ref.enums, linesep)
        return "{5}{4}{0}<{1} {2}>{3}</{1}>".format(self._str_indent, self.name,
                                                    " ".join(str(attr) for attr in self.attributes),
                                                    self.value,
                                                    prefix, super().__str__())

    @classmethod
    def from_sibling(cls, sib):
        logger.info("Creating new {} Element from sibling, {}".format(sib.__class__.__name__, sib.name))
        return cls(sib.name, sib.parent, sib.ref, False)

    @property
    def value(self) -> str:
        """ The current value (defaults to None-type) of the input Element, and the value that will be used in the
        request envelope """
        return self.__value

    @value.setter
    def value(self, value):
        if value is not None:
            # Some very basic python-to-xml type conversion
            if value is True:
                self.__value = "true"
            elif value is False:
                self.__value = "false"
            else:
                self.__value = value


class Container(Base, AttributableMixin, RenderOptionsMixin):
    """ Container elements only contain other elements, and possibly attributes. The can not be set themselves, or
    repeated more than once. They contain attributes that map to other input Elements. """

    def __init__(self, name, parent, wsdl_type, update_parent=True):
        super().__init__(name, parent, wsdl_type, update_parent)
        AttributableMixin.__init__(self)
        self.__setable = False
        self.__children = list()

    def __setattr__(self, key, value):
        """ implementation allows settings child Element values without having to reference the .value attribute
        on the Element, but can set the Element inside the parent Container and the .value attribute will be set
        """
        if key in self.__dict__:
            if isinstance(self.__dict__[key], Element):
                self.__dict__[key].value = value
            else:
                self.__dict__[key] = value
        else:
            self.__dict__[key] = value

    def __str__(self):
        return "{5}{4}<{0} {1}>{3}{2}{3}{4}</{0}>".format(self.name, " ".join(str(attr) for attr in self.attributes),
                                                          "{}".format(linesep).join(
                                                              str(child) for child in self.children),
                                                          linesep,
                                                          self._str_indent,
                                                          super().__str__())

    @classmethod
    def from_sibling(cls, sib):
        logger.info("Creating new {} Element from sibling, {}".format(sib.__class__.__name__, sib.name))
        new = cls(sib.name, sib.parent, sib.ref, False)
        # Duplicate this process for each child element
        for child in sib.children:
            logger.debug("Appending child {} to new {}".format(child.name, sib.__class__.__name__))
            new.append_child(child.from_sibling(child))
        return new

    @property
    def setable(self):
        return self.__setable

    @property
    def children(self):
        return self.__children

    def append_child(self, child: Element):
        logger.debug("Appending child with name {} to {}".format(child.name, self.name))
        name = child.name
        if child.name in dir(self):
            name = "_"+child.name
        setattr(self, name, child)
        self.children.append(child)


class Repeatable(Base):
    """ Repeatable Elements are like normal elements, except their values are left as iterables, not scalars """

    def __init__(self, name, parent, wsdl_type, update_parent=True):
        super().__init__(name, parent, wsdl_type, update_parent)
        self.__repeatable = True
        # We need to initialize the zeroth element in our array to be an Element with the same name
        self.__elements = list()
        self.append()

    def __getitem__(self, item: int) -> Element:
        return self.__elements[item]

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.__elements[key].value = value
        else:
            raise ValueError("Subscript values for {} object must be integers. Invalid: {}"
                             .format(self.__class__.__name__, value))

    def __str__(self):
        return "{4}{1}<!--- Repeatable: {0} --->{3}{2}".format(self.name,
                                                               self._str_indent,
                                                               "{0}".format(linesep).join(
                                                                   str(el) for el in self.elements),
                                                               linesep,
                                                               super().__str__())

    def __len__(self):
        return len(self.elements)

    @property
    def elements(self) -> list:
        return self.__elements

    @property
    def repeatable(self):
        return self.__repeatable

    @classmethod
    def from_sibling(cls, sib):
        logger.info("Creating new {} Element from sibling, {}".format(sib.__class__.__name__, sib.name), 4)
        new = cls(sib.name, sib.parent, sib.ref, False)
        return new

    def append(self, value=None) -> None:
        """ Append a new child to the list, providing an optional value. If value is not provided, then an empty new
        element will be created (which could be set using .value later) """
        element = Element.from_sibling(self)
        logger.debug("Appending new Element to Repeatable {}".format(self.name))
        element.value = value
        logger.debug("Set new Element {} value to '{}'".format(self.name, value))
        self.__elements.append(element)

    def extend(self, *args) -> None:
        """ Extend the list of elements with new elements based on an iterable of values """
        logger.info("Extending new set of values to {}".format(self.name))
        for value in args:
            logger.debug("Creating new Element with value '{}' in '{}'".format(value, self.name))
            element = Element.from_sibling(self)
            element.value = value
            self.__elements.append(element)


class Collection(Repeatable, Container):
    """ Collections hold a list of repeatable Containers
    The Collection interface is defined by being repeatable but not setable."""

    def __init__(self, name, parent, wsdl_type, update_parent=True):
        super().__init__(name, parent, wsdl_type, update_parent)
        self.__repeatable = True
        self.__collection = {}

    def append(self, value=dict()):
        """ Append a new child Container to the list of elements for this Collection. Values may be provided as a
        dictionary, with keys matching the child element names. If not provided, then an empty container will be
        created. """
        logger.info("Appending new child Container to '{}'".format(self.name))
        container = Container.from_sibling(self)
        self.elements.append(container)

    def append_child(self, child: Element):
        super().append_child(child)
        logger.debug("Appending new child {1} to elements in Collection {0}".format(self.name, child.name))
        for element in self.elements:
            if isinstance(element, Container):
                element.append_child(child)

    def __getitem__(self, item):
        """ Return the indicated index of child elements """
        return self.elements[item]

    def __str__(self):
        return "{1}<!--- Repeatable: {0} --->{2}".format(self.name, self._str_indent, linesep) \
               + "{0}".format(linesep).join(str(el) for el in self.elements)


class Attribute:
    """ An individual attribute of an input Element. A further abstraction of the
    Attribute object in soapy.wsdl.types """

    def __init__(self, name, value):
        self.__name = name
        if value is not None:
            self.__value = quoteattr(value)
        else:
            self.__value = None

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        self.__value = quoteattr(str(value))

    @property
    def name(self):
        return self.__name

    def __str__(self):
        return self.name + "=" + str(self.value)


class Factory:
    """ Factory creates an input object class structure from the WSDL Type elements that represents the possible
    inputs to the provided Message. The Factory.root_element object represents the top-level message, and child
    input elements may be retrieved through normal attribute notation, using the . (dot) operator. You can also
    print() a Factory class to see a pseudo XML representation of the possible inputs, and their current values.
    """

    def __init__(self, root_element):
        logger.info("Initializing new Factory instance for root element '{}'".format(root_element))
        elements = list()
        inputs = list()
        logger.info("Building list of all elements for this Part")
        Factory._recursive_extract_elements(elements, root_element)
        for element in elements:
            name = element[0].name
            logger.debug("Processing WSDL element {}".format(name))
            # Find the parent InputElement to pass to the child if there is a parent
            if element[1] is not None:
                for input in inputs:
                    if element[1] is input.ref:
                        logger.debug("Setting parent element for {} to '{}'".format(name, input.name))
                        inputs.append(self._select_class(element)(name, input, element[0]))
            else:
                self.root_element = self._select_class(element)(name, None, element[0])
                inputs.append(self.root_element)
        self.items = inputs

    def __getattr__(self, item):
        """ Enable attribute references on Factory object itself to return attributes on root_element instead """
        return getattr(self.root_element, item)

    def __str__(self):
        return str(self.root_element)

    def _select_class(self, element):
        """ Return the appropriate input class based on criteria
            Repeatable = setable and repeatable
            Element = setable
            Container = neither setable nor repeatable
            Collection = repeatable
        """
        setable = False
        repeatable = False
        if element[0].max_occurs == "unbounded" or int(element[0].max_occurs) > 1:
            repeatable = True
        if len(element[0].element_children) == 0:
            setable = True
        switch = {
            (True, False): Element,
            (True, True): Repeatable,
            (False, False): Container,
            (False, True): Collection
        }
        logger.info("Creating {} type for input message element {}".format(
                  switch[setable, repeatable].__name__,
                  element[0].name))
        return switch[setable, repeatable]

    @staticmethod
    def _recursive_extract_elements(l: list, element, parent=None):

        """ Recursively iterates over soapy.wsdl.types Objects and extracts the
        TypeElement objects, as they are what actually represent input options """

        if element is None:
            return

        l.append((element, parent))
        for child in element.element_children:
            if child.bs_element is element.bs_element:
                continue
            Factory._recursive_extract_elements(l, child, element)
