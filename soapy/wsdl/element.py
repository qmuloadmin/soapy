from bs4 import Tag

""" Elements defined in this module are used by both WSDL elements (model) and SOAP elements (types)
 NOTE: The exception is Schema. I do not like its implementation and plan to fix it at some point. For now it's here
 for lack of a better place. """


class Namespace:

    """ Contains mapping to name and definition and allows dictionary-like reference """

    def __init__(self, parent, log):
        self.__parent = parent
        self.log = log
        self.log("Initializing Namespace object for element {0}".format(parent.name), 5)

        # Values that are evaluated lazy
        self.__names = None

    @property
    def parent(self) -> Tag:
        return self.__parent

    @property
    def names(self) -> tuple:

        if self.__names is None:
            self.log("Initializing list of namespaces names for {0} element".format(self.parent.name), 5)
            attrs = list()
            for key in self.parent.attrs.keys():
                if key.startswith('xmlns'):
                    try:
                        attrs.append(key.split(":")[1])
                        self.log("Found namespace '{0}'"
                                 .format(key.split(":")[1]), 5)
                    except IndexError:
                        pass
            self.__names = tuple(attrs)
        return self.__names

    def resolve_namespace(self, ns) -> str:
        if ns in self.names:
            return self.parent.attrs["xmlns:" + ns]
        else:
            raise KeyError("No namespace defined in this element with name {0}".format(ns))


class Element:

    """ Base class for handling instantiation and name attribute for any WSDL element """

    def __init__(self, bs_element, wsdl, schema=None, is_local=True):

        """ Constructor: provide the BeautifulSoup tag object instance for the element and
        the soapy.Wsdl parent instance """

        self.__bs_element = bs_element
        self.__parent = wsdl
        self.__schema = schema
        self.__is_local = is_local
        self.log("Initialized {0} with name of {1}".format(
            self.__bs_element.name, self.name), 4)

        # Values that are evaluated lazy
        self.__namespace = None
        self.__children = None

        # Below is a provision utilized by TypeElements to prevent recursion on recursive XSD types
        # As bsElements are shared across TypeElements/Elements when they refer to the same element in the WSDL
        if self.bs_element.counter is None:
            self.bs_element.counter = 1
        else:
            self.bs_element.counter += 1

    @classmethod
    def from_name(cls, name, parent):

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
    def is_local(self):
        return self.__is_local

    @property
    def name(self) -> str:
        return self.__bs_element.get('name')

    @property
    def parent(self):
        return self.__parent

    @property
    def bs_element(self) -> Tag:
        return self.__bs_element

    @property
    def tag(self) -> str:
        return self.__bs_element.name

    @property
    def namespace(self) -> Namespace:
        if self.__namespace is None:
            self.__namespace = Namespace(self.bs_element, self.log)
        return self.__namespace

    @property
    def children(self) -> tuple:
        if self.__children is None:
            self.log("Retrieving list of children for Element {}".format(self.name), 5)
            children = list()
            for each in self.bs_element.children:
                if not isinstance(each, Tag):
                    continue
                children.append(self.parent.type_factory(each, self.schema))
            self.__children = tuple(children)
        return self.__children

    def __str__(self):
        return str(self.__bs_element)

    def log(self, message, tl):
        self.parent.log(message, tl)


class Schema(Element):
    """ Class that handles schema attributes and namespaces """

    @property
    def name(self) -> str:

        """ The name of a Schema is its targetNamespace, which is the closest thing to a QName a schema has """

        return self.bs_element.get('targetNamespace', None)

    @property
    def element_form(self) -> str:
        
        return self.bs_element.get("elementFormDefault", "unqualified")

    @property
    def attribute_form(self) -> str:
        return self.bs_element.get("attributeFormDefault", "unqualified")
