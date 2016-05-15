from soapy import Log
from bs4 import Tag

""" Elements defined in this module are used by both WSDL elements (model) and SOAP elements (types)
 NOTE: The exception is Schema. I do not like its implementation and plan to fix it at some point. For now it's here
 for lack of a better place. """

class Namespace():

    """ Contains mapping to name and definition and allows dictionary-like reference """

    def __init__(self, parent, log):
        self.__parent = parent
        self._log = log
        self.log("Initializing Namespace object for element {0}".format(parent.name), 5)

    @property
    def log(self) -> Log._log:
        return self._log

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
        self._log("Initialized {0} with name of {1}".format(
            self.__bsElement.name, self.name), 4)

    @classmethod
    def fromName(cls, name, parent):

        """ Searches the wsdl for an element with matching name and tag, returns appropriate object """

        tag = cls.__name__
        tag = tag[:1].lower() + tag[1:]  ## Lowercase the first letter of the class name
        ports = parent.wsdl(tag, recursive=False)
        parent._log("Searching for {1} element with name matching {0}"
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

    @property
    def namespace(self) -> Namespace:
        try:
            return self.__namespace
        except AttributeError:
            self.__namespace = Namespace(self.bsElement, self._log)
            return self.__namespace

    def __str__(self):
        return str(self.__bsElement)

    def _log(self, message, tl):
        self.parent._log(message, tl)


class Schema(Element):
    """ Class that handles schema attributes and namespaces """

    @property
    def name(self) -> str:

        """ The name of a Schema is its targetNamespace, which is the closest thing to a QName a schema has """

        return self.bsElement['targetNamespace']

