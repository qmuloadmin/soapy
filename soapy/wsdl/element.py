from bs4 import Tag

import soapy

""" Elements defined in this module are used by both WSDL elements (model) and SOAP elements (types)
 NOTE: The exception is Schema. I do not like its implementation and plan to fix it at some point. For now it's here
 for lack of a better place. """


class Namespace:

    """ Contains mapping to name and definition and allows dictionary-like reference """

    def __init__(self, parent, log):
        self.__parent = parent
        self.log = log
        self.log("Initializing Namespace object for element {0}".format(parent.name), 5)

    @property
    def parent(self) -> Tag:
        return self.__parent

    @property
    def names(self) -> tuple:
        try:
            return self.__names
        except AttributeError:
            self.log("Initializing list of namespaces names for {0} element".format(self.parent.name), 5)
            attrs = list()
            for key in self.parent.attrs.keys():
                if key.startswith('xmlns'):
                    try:
                        attrs.append(key.split(":")[1])
                    except IndexError:
                        pass
            self.__names = tuple(attrs)
            return self.__names

    def resolveNamespace(self, ns) -> str:
        if ns in self.names:
            return self.parent.attrs["xmlns:" + ns]
        else:
            raise KeyError("No namespace defined in this element with name {0}".format(ns))

class Element():

    """ Base class for handling instantiation and name attribute for any WSDL element """

    def __init__(self, bsElement, parent, schema=None):

        """ Constructor: provide the BeautifulSoup tag object instance for the element and
        the soapy.Wsdl parent instance """

        self.__bsElement = bsElement
        self.__parent = parent
        self.__schema = schema
        self.log("Initialized {0} with name of {1}".format(
            self.__bsElement.name, self.name), 4)

    @classmethod
    def fromName(cls, name, parent):

        """ Searches the wsdl for an element with matching name and tag, returns appropriate object """

        tag = cls.__name__
        tag = tag[:1].lower() + tag[1:]  # Lowercase the first letter of the class name
        ports = parent.wsdl(tag, recursive=False)
        parent.log("Searching for {1} element with name matching {0}"
                    .format(name, cls.__name__), 5)
        for port in ports:
            if port.get('name') == name:
                return cls(port, parent)

    @property
    def schema(self):
        return self.__schema

    @property
    def name(self) -> str:
        return self.__bsElement.get('name')

    @property
    def parent(self):
        return self.__parent

    @property
    def bsElement(self) -> Tag:
        return self.__bsElement

    @property
    def tag(self) -> str:
        return self.__bsElement.name

    @property
    def children(self) -> tuple:
        try:
            return self.__children
        except AttributeError:
            children = list()
            for each in self.bsElement.children:
                if not isinstance(each, Tag): continue
                children.append(self.parent.typeFactory(each, self.schema))
            self.__children = tuple(children)
            return self.__children

    def __str__(self):
        return str(self.__bsElement)

    def log(self, message, tl):
        self.parent.log(message, tl)

    def __str__(self):
        return str(self.__bsElement)

    # TODO the below methods and properties should be moved to a different super class
    # Specifically for Type elements, that is shared between TypeElement and TypeContainer
    # For now, they are here, but are useless and confusing (during object introspection)
    # On Elements that are not in the soapy.wsdl.types library.

    def update(self, parent, parentUpdates=dict()):

        for child in self.children:
            if child is None: continue
            try:
                parentUpdates.update(self.updateParentElement(parent))
            except (TypeError, AttributeError):
                pass
            child.update(parent, parentUpdates)

        if isinstance(self, soapy.wsdl.types.TypeElement):
            for key, value in parentUpdates:
                self.bsElement[key] = value

    @property
    def elementChildren(self, childUpdates=dict()) -> tuple:
        try:
            return self.__elementChildren
        except AttributeError:
            self.log("In recursive process of isolating and updating TypeElement children", 5)
            children = list()
            try:
                cUpdate = self.updateChildElements()
                if cUpdate is not None:
                    self.log("Found update item(s) for Children: {0}".format(cUpdate), 4)
                    childUpdates.update(cUpdate)
            except AttributeError: 
                
                """ Do nothing, we are in a TypeElement object """

            for each in self.children:
                if isinstance(each, soapy.wsdl.types.TypeElement):
                    children.append(each)
                elif each is None:
                    continue
                else:
                    children.extend(each.elementChildren)
            self.log("All TypeElement children identified", 5)
            if len(childUpdates) > 0:
                self.log("Processing all parent-induced updates for all children", 5)
                for child in children:
                    for attr, value in childUpdates.items():
                        child.bsElement[attr] = value
            self.__elementChildren = tuple(children)
            return self.__elementChildren

    @property
    def namespace(self) -> Namespace:
        try:
            return self.__namespace
        except AttributeError:
            self.__namespace = Namespace(self.bsElement, self.log)
            return self.__namespace

# TODO probably need to move Schema to wsdl.__init__

class Schema(Element):
    """ Class that handles schema attributes and namespaces """

    @property
    def name(self) -> str:

        """ The name of a Schema is its targetNamespace, which is the closest thing to a QName a schema has """

        return self.bsElement['targetNamespace']

    @property
    def elementForm(self) -> str:
        
        return self.bsElement.get("elementFormDefault", "unqualified")

    @property
    def attributeForm(self) -> str:
        return self.bsElement.get("attributeFormDefault", "unqualified")
