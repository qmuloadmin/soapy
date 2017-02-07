""" A class representation of all possible input types """

from os import linesep
from xml.sax.saxutils import quoteattr

from soapy import Log


class Base(Log):

    def __init__(self, name, parent, bs_element, tl, update_parent=True):
        super().__init__(tl)
        self.__parent = parent
        self.__name = name
        self.log("Initializing new {} element with name '{}'".format(self.__class__.__name__, self.name), 4)
        self.__ref = bs_element
        self.__setable = True
        self.__repeatable = False
        if isinstance(self.parent, Container) and update_parent:
            self.parent.append_child(self)

    @property
    def _str_indent(self) -> str:
        if self.depth == 0:
            return ""
        return " |   " * self.depth

    @property
    def parent(self):
        return self.__parent

    @property
    def is_collection(self) -> bool:
        """ A collection is a parent-level element that can be repeated. In other words, and element whose value
        is other elements, but can be duplicated as a set. """
        if not self.setable and self.repeatable:
            return True
        else:
            return False

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
        try:
            return self.__depth
        except AttributeError:
            # Determine the depth
            self.__depth = 0
            working_parent = self.parent
            while working_parent is not None:
                working_parent = working_parent.parent
                self.__depth += 1
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

    def keys(self):
        return tuple([attr.name for attr in self.attributes])

    def __getitem__(self, item):
        """ retrieves the attribute on the element in bs4-style"""
        for attr in self.attributes:
            if attr.name == item:
                return attr
        raise AttributeError("{} object has no element attribute {}".format(self.__class__.__name__, item))


class Element(Base, AttributableMixin):
    """A base input Element is capable of being assigned a value ('setable') and is not repeatable"""

    def __init__(self, name, parent, bs_element, tl, update_parent=True):
        super().__init__(name, parent, bs_element, tl, update_parent)
        self.__value = None
        AttributableMixin.__init__(self)

    def __str__(self):
        return "{0}<{1} {2}>{3}</{1}>".format(self._str_indent, self.name, " ".join(self.attributes), self.value)

    @classmethod
    def from_sibling(cls, sib):
        sib.log("Creating new {} Element from sibling, {}".format(sib.__class__.__name__, sib.name), 4)
        return cls(sib.name, sib.parent, sib.ref, sib.tl, False)

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


class Container(Base, AttributableMixin):
    """ Container elements only contain other elements, and possibly attributes. The can not be set themselves, or
    repeated more than once. They contain attributes that map to other input Elements. """

    def __init__(self, name, parent, bs_element, tl, update_parent=True):
        super().__init__(name, parent, bs_element, tl, update_parent)
        AttributableMixin.__init__(self)
        self.__setable = False
        self.__children = list()

    def __str__(self):
        return "{4}<{0} {1}>{3}{2}{3}{4}</{0}>".format(self.name, " ".join(self.attributes),
                                                       "{}".format(linesep).join(str(child) for child in self.children),
                                                       linesep,
                                                       self._str_indent)

    @classmethod
    def from_sibling(cls, sib):
        sib.log("Creating new {} Element from sibling, {}".format(sib.__class__.__name__, sib.name), 4)
        new = cls(sib.name, sib.parent, sib.ref, sib.tl, False)
        # Duplicate this process for each child element
        for child in sib.children:
            sib.log("Appending child {} to new {}".format(child.name, sib.__class__.__name__), 5)
            new.append_child(child.from_sibling(child))
        return new

    @property
    def setable(self):
        return self.__setable

    @property
    def children(self):
        return self.__children

    def append_child(self, child: Element):
        self.log("Appending child with name {} to {}".format(child.name, self.name), 5)
        name = child.name
        if child.name in dir(self):
            name = "_"+child.name
        setattr(self, name, child)
        self.children.append(child)


class Repeatable(Base):
    """ Repeatable Elements are like normal elements, except their values are left as iterables, not scalars """

    def __init__(self, name, parent, bs_element, tl, update_parent=True):
        super().__init__(name, parent, bs_element, tl, update_parent)
        self.__repeatable = True
        # We need to initialize the zeroth element in our array to be an Element with the same name
        self.__elements = list()
        self.append()

    def __getitem__(self, item: int) -> Element:
        return self.__elements[item]

    def __str__(self):
        return "{1}<!--- Repeatable: {0} --->{3}{2}".format(self.name,
                                                            self._str_indent,
                                                            "{0}".format(linesep).join(str(el) for el in self.elements),
                                                            linesep)

    def __len__(self):
        return len(self.elements)

    @property
    def elements(self) -> list:
        return self.__elements

    @property
    def values(self) -> tuple:
        """ A helper method to consolidate the element children's values into one parent-level list.
        This is currently used by the quick-and-dirty marshalling process as a stop gap. However, it
        prevents individual list elements from having different attributes. So, once the marshaller
        classes can be updated to iterate through children elements properly, we can remove this method """
        try:
            return self.__values
        except AttributeError:
            values = list()
            for child in self.elements:
                if child.value is not None:
                    values.append(child.value)
            self.__values = tuple(values)
            return self.__values

    @property
    def value(self):
        """ A temporary hack to integrate with outdated marshaller. Will need to fix this in the future. Do not rely on
        this method being available on Repeatable elements in the future. """
        if len(self.values):
            return self.values
        else:
            return None

    @property
    def repeatable(self):
        return self.__repeatable

    @classmethod
    def from_sibling(cls, sib):
        sib.log("Creating new {} Element from sibling, {}".format(sib.__class__.__name__, sib.name), 4)
        new = cls(sib.name, sib.parent, sib.ref, sib.tl, False)
        return new

    def append(self, value=None) -> None:
        """ Append a new child to the list, providing an optional value. If value is not provided, then an empty new
        element will be created (which could be set using .value later) """
        element = Element.from_sibling(self)
        self.log("Appending new Element to Repeatable {}".format(self.name), 5)
        element.value = value
        self.log("Set new Element {} value to '{}'".format(self.name, value), 5)
        self.__elements.append(element)

    def extend(self, *args) -> None:
        """ Extend the list of elements with new elements based on an iterable of values """
        self.log("Extending new set of values to {}".format(self.name), 4)
        for value in args:
            self.log("Creating new Element with value '{}' in '{}'".format(value, self.name), 5)
            element = Element.from_sibling(self)
            element.value = value
            self.__elements.append(element)


class Collection(Repeatable, Container):
    """ Collections hold a list of repeatable Containers
    The Collection interface is defined by being repeatable but not setable."""

    def __init__(self, name, parent, bs_element, tl, update_parent=True):
        super().__init__(name, parent, bs_element, tl, update_parent)
        self.__repeatable = True
        self.__collection = {}

    def append(self, value=dict()):
        """ Append a new child Container to the list of elements for this Collection. Values may be provided as a
        dictionary, with keys matching the child element names. If not provided, then an empty container will be
        created. """
        self.log("Appending new child Container to '{}'".format(self.name), 4)
        container = Container.from_sibling(self)
        self.elements.append(container)

    def append_child(self, child: Element):
        super().append_child(child)
        self.log("Appending new child {1} to elements in Collection {0}".format(self.name, child.name), 5)
        for element in self.elements:
            if isinstance(element, Container):
                element.append_child(child)

    def __getitem__(self, item):
        """ Return the indicated index of child elements """
        return self.elements[item]

    def __str__(self):
        return "{1}<!--- Repeatable: {0} --->{2}".format(self.name, self._str_indent, linesep) \
               + "{0}".format(linesep).join(str(el) for el in self.elements)

    @property
    def collection(self) -> dict:
        """ A helper method to consolidate the element children's values into one parent-level dict.
        This is currently used by the quick-and-dirty marshalling process as a stop gap. However, it
        prevents individual collection children from having different attributes. So, once the marshaller
        classes can be updated to iterate through children elements properly, we can remove this method
        """

        for container in self.elements:
            for child in container.children:


        return self.__collection

    def _extract_elements(self, parent: Container):
        for child in parent.children:



class Attribute:
    """ An individual attribute of an input Element. A further abstraction of the
    Attribute object in soapy.wsdl.types """

    def __init__(self, name, value):
        self.__name = name
        self.value = quoteattr(value)

    @property
    def name(self):
        return self.__name

    def __str__(self):
        return "['" + self.name + "'] = " + str(self.value)


class Factory(Log):
    """ Create this class, to handle the shortcomings in both notation and functionality introduced by the
    convenient, but overly-simple InputOptions class. InputFactory will maintain parent/child heirarchy, but will
    probably require a different Marshaller class to handle (one that relies on the Factory-generated class for
    structure instead of the WSDL representation)
    """

    def __init__(self, root_element, tl):
        super().__init__(tl)
        self.log("Initializing new Factory instance for root element '{}'".format(root_element), 3)
        elements = list()
        inputs = list()
        self.log("Building list of all elements for this Part", 4)
        Factory._recursive_extract_elements(elements, root_element)
        for element in elements:
            name = element[0].name
            self.log("Processing WSDL element {}".format(name), 5)
            # Find the parent InputElement to pass to the child if there is a parent
            if element[1] is not None:
                for input in inputs:
                    if element[1] is input.ref:
                        self.log("Setting parent element for {} to '{}'".format(name, input.name), 5)
                        inputs.append(self._select_class(element)(name, input, element[0], tl))
            else:
                self.root_element = self._select_class(element)(name, None, element[0], tl)
                inputs.append(self.root_element)
        self.items = inputs

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
        self.log("Creating {} type for input message element {}".format(
                  switch[setable, repeatable].__name__,
                  element[0].name), 4)
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
