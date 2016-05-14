#!/usr/bin/python3

import time
import os
from bs4 import BeautifulSoup
from bs4.element import Tag
import requests

class Log:

	""" Basic trace-level based logging class """

	def __init__(self, tl):

		""" Provide tracelevel of -1 to not log anything """

		self.tl = tl
		self._log("Set instance tracelevel to {0}".format(tl),5)

	def _log(self,message,tl):

		prefix = str()

		if self.tl == -1: return
		elif tl == 0: prefix = "FATAL:	"
		elif tl == 1: prefix = "ERROR:	"
		elif tl == 2: prefix = "WARN:	"
		elif tl == 3: prefix = "NOTICE: "
		elif tl == 4: prefix = "INFO:	"
		elif tl == 5: prefix = "DEBUG:	"
		if tl <= self.tl:
			print(prefix+str(time.ctime())+" | "+message+" |")

class Element():
	
	""" Base class for handling instantiation and name attribute for any WSDL element """

	def __init__(self,bsElement,parent,schema=None):

		""" Constructor: provide the BeautifulSoup tag object instance for the element and 
		the soapy.Wsdl parent instance """

		self.__bsElement = bsElement
		self.__parent = parent
		self.__schema = schema
		self._log("Initialized {0} with name of {1}".format(
						self.__bsElement.name,self.name),4)

	@classmethod
	def fromName(cls,name,parent):

		""" Searches the wsdl for an element with matching name and tag, returns appropriate object """

		tag = cls.__name__
		tag = tag[:1].lower() + tag[1:]  ## Lowercase the first letter of the class name
		ports = parent.wsdl(tag,recursive=False)
		parent._log("Searching for {1} element with name matching {0}"
					.format(name,cls.__name__),5)
		for port in ports:
			if port.get('name') == name:
				return cls(port,parent)

	@property
	def schema(self):
		return self.__schema

	@property
	def name(self):
		return self.__bsElement.get('name')

	@property
	def parent(self):
		return self.__parent

	@property
	def bsElement(self):
		return self.__bsElement

	@property
	def tag(self):
		return self.__bsElement.name

	@property
	def children(self):
		try:
			return self.__children
		except:
			children = list()
			for each in self.bsElement.children:
				if not isinstance(each,Tag): continue
				children.append(self.parent.typeFactory(each,self.schema))
			self.__children = tuple(children)
			return self.__children

	@property
	def namespace(self):
		try:
			return self.__namespace
		except:
			self.__namespace = Namespace(self.bsElement,self._log)
			return self.__namespace

	def __str__(self):
		return str(self.__bsElement)

	def _log(self,message,tl):
		self.parent._log(message,tl)

class Namespace():

	""" Contains mapping to name and definition and allows dictionary-like reference """

	def __init__(self,parent,log):
		self.__parent = parent
		self._log = log
		self.log("Initializing Namespace object for element {0}".format(parent.name),5)
	
	@property
	def log(self):
		return self._log

	@property
	def parent(self):
		return self.__parent

	@property
	def names(self):
		try:
			return self.__names
		except:
			self.log("Initializing list of namespaces names for {0} element".format(self.parent.name),5)
			attrs = list()
			for key in self.parent.attrs.keys():
				if key.startswith('xmlns'):
					try:
						attrs.append(key.split(":")[1])
					except IndexError:
						pass
			self.__names = tuple(attrs)
			return self.__names

	def resolveNamespace(self,ns) -> str:
		if ns in self.names:
			return self.parent.attrs["xmlns:"+ns]
		else:
			raise KeyError("No namespace defined in this element with name {0}".format(ns))

class TypeContainer(Element):

	""" Any <tag> defined in a schema that is not an element. In other words, it contains or
	describes other elements. E.g, <sequence> or <complexType> """

	@property
	def parentAttributes(self):

		""" Returns the attributes defined within this tag, and any non-element children """

		try:
			return self.__parentAttributes
		except:
			attrs = list()
			self._log("In recursive process of consolidating attributes. Current object is '{0}' the {1}"
															.format(self.name,self.tag),5)
			attributes = self.bsElement('attribute',recursive=False)
			for attribute in attributes:
				attr = Attribute(attribute,self.parent)
				self._log("Created attribute {0}".format(attr),5)
				attrs.append(attr)
			for child in self.children:
				try:
					attrs.extend(child.parentAttributes)
				except:
					""" Do nothing, because this means it's an Element """

			self.__attributes = tuple(attrs)
			return self.__attributes

class TypeElement(Element):

	""" Class containing attributes and properties of an element in a Type definition """

	@property
	def attributes(self):
		try:
			return self.__attributes
		except:
			self._log("Initializing list of attributes for element {0}".format(self.name),5)
			attributes = self.bsElement('attribute',recursive=False)
			for attribute in attributes:
				attributes.append(Attribute(attribute,self.parent))
			for child in self.children:
				try:
					attributes.extend(child.parentAttributes)
				except AttributeError:
					""" Do nothing, because this means it's an Element """

			self.__attributes = tuple(attributes)
			return self.__attributes

	@property
	def nillable(self):
		return self.bsElement.get("nillable","false")
	@property
	def maxOccurs(self):
		return self.bsElement.get("maxOccurs","1")
	@property
	def minOccurs(self):
		return self.bsElement.get("minOccurs","1")

class Attribute(Element):

	""" Class containing properties of element attributes in a SOAP Envelope created from WSDL """

	@property
	def type(self):
		return self.bsElement['type'].split(":")[1]
	@property
	def ns(self):
		return self.bsElement['type'].split(":")[0]
	@property
	def default(self):
		return self.bsElement.get('default',None)

class ComplexType(TypeContainer):
	
	""" Class representing a dynamic container of simpler types """

class SequenceType(TypeContainer):

	""" Class representing an unnamed sequence of types """

	@property
	def name(self):
		return "anonymous"

class Schema(Element):
	
	""" Class that handles schema attributes and namespaces """

	@property
	def name(self):	
		return "anonymous"

	@property
	def parentNamespace(self):
		try:
			return self.__parentNamespace
		except AttributeError:
			self.__parentNamespace = Namespace(self.parent.wsdl,self._log)
			return self.__parentNamespace

class Wsdl(Log):
	
	""" Class reads in WSDL and forms various child objects held together by this parent class 
	Which essentially converts wsdl objects inside 'definitions' into Python native objects """

	def __init__(self,wsdl_location,tracelevel=1,**kArgs):

		""" wsdl_location is FQDN and URL of WSDL, must include protocol, e.g. http/file
		If caching behavior is desired (to load native python objects instead of parsing 
		the XML each time, then provide keyword args of cache=FH where FH is a file handle """
		
		super().__init__(tracelevel)

		#Determine how to load the WSDL, is it a web resource, or a local file?

		if wsdl_location.startswith("file://"):
			wsdl_location = wsdl_location.replace("file://","")
			with open(wsdl_location) as in_file:
				with open(self.wsdlFile,"w") as out_file:
					for line in in_file:
						out_file.write(line)
		else:
			self._log("Unsupported protocol for WSDL location: {0}".format(wsdl_location),0)
			raise ValueError("Unsupported protocol for WSDL location: {0}".format(wsdl_location))

		#TODO handle URLs with http/https


	@property
	def wsdl(self):
		try:
			return self.__wsdl
		except:
			self._log('Getting root definitions of WSDL',5)
			self.__wsdl = self.soup("definitions",recursive=False)[0]
			return self.__wsdl

	@property
	def soup(self):
		try:
			return self.__soup
		except:
			self._log("Parsing WSDL file and rendering Element Tree",5)
			with open(self.wsdlFile) as f:
				self.__soup = BeautifulSoup(f,"xml")
			os.remove(self.wsdlFile)
			return self.__soup

	@property
	def wsdlFile(self):

		""" Create a temporary file, handling overlap in the off chance it already exists """

		try: return self.__wsdlFile
		except:
			self._log("Initializing wsdl file cache",5)
			f = str(os.getpid())+".temp"
	
			if os.path.exists(f): 
				f = str(time.time())+f
			self._log("Set wsdlFile for instance to cache: {0}".format(f),4)
			self.__wsdlFile = f
			return self.__wsdlFile

	@property
	def services(self):
		
		""" The list of services available. The list will contain soapy.Service objects """

		try:
			return self.__services
		except:
			self._log("Initializing list of services with services defined in WSDL",5)
			services = list()
			for service in self.wsdl('service',recursive=False):
				services.append(Service(service,self))
			self.__services = tuple(services)
			return self.__services

	@property
	def schemas(self):
		try:
			return self.__schemas
		except AttributeError:
			types = self.wsdl('types',recursive=False)[0]
			schemas = list()
			for schema in types('schema',recursive=False):
				schemas.append(Schema(schema,self))
			self.__schemas = tuple(schemas)
			return self.__schemas

	@staticmethod
	def __downloadWsdl(url):

		""" Downloads a WSDL from a remote location, attempting to account for proxy,
		then saves it to the proper filename for reading """

	def __str__(self):
		return self.wsdl.prettify()

	def typeFactory(self,element,schema) -> Element:
		
		""" Factory that creates the appropriate EnvClass based on bsElement tag """

		if element.name == "element":
			return TypeElement(element,self,schema)
		elif element.name == "complexType":
			return ComplexType(element,self,schema)
		elif element.name == "sequence":
			return SequenceType(element,self,schema)
		elif element.name == "attribute":
			return None
		else:
			raise TypeError("XML Element Type <{0}> not yet implemented".format(element.name))

	def findTypeByName(self,name) -> Element:
		
		""" Given a name, find the type and schema object """

		t = self.wsdl('types',recursive=False)
		self._log("Searching all types for matching element with name {0}".format(name),5)
		for schema in self.schemas:
			tags = schema.bsElement("",{"name":name})
			if len(tags) > 0:
				return self.typeFactory(tags[0],schema)
		self._log("Unable to find Type based on name {0}".format(name),1)
		return None

class Service(Element):
	
	""" Simplified, native Python representation of Service definitions in WSDL
	Provides information on child (port) objects by name and service tag attribute information """

	@property
	def ports(self):
		try:
			return self.__ports
		except:
			self._log("Initializing list of ports defined for service {0}".format(self.name),5)
			ports = list()
			for port in self.bsElement('port',recursive=False):
				ports.append(Port(port,self.parent))
			self.__ports = tuple(ports)
			return self.__ports

class Port(Element):
	
	""" Simplified, native Python representation of ports as defined within services """

	@property
	def binding(self):
		try:
			return self.__binding
		except:
			self._log("Initializing binding attribute for port {0}".format(self.name),5)
			binding = self.bsElement['binding']
			(ns, name) = binding.split(':')
			self.__binding = Binding.fromName(name,self.parent)
			return self.__binding

	@property
	def location(self):
		try:
			return self.__location
		except:
			self._log("Initializing location of Port based on address element",5)
			self.__location = self.bsElement('address',recursive=False)[0]['location']
			self._log("Initialized location to {0}".format(self.__location),4)
			return self.__location

	@location.setter
	def location(self,location):
		self.__location = location

class Binding(Element):

	""" Simplified, native python representation of a binding definition
	Also provides enforcement that the style of the binding is document
	as this library does not (currently) support other styles """

	def __init__(self,bsElement,parent):
		super().__init__(bsElement,parent)
		#Validate that the binding style is 'document'
		soapBinding = bsElement('binding',recursive=False)[0]
		if not soapBinding['style'] == "document":
			self._log("Binding style not set to document. SoaPy can't handle non-document styles",0)
			raise TypeError("Binding style not set to document. SoaPy can't handle non-document styles")
	
	@property
	def type(self):
		try:
			return self.__type
		except:
			self._log("Initializing portType from binding {0}".format(self.name),5)
			(ns,name) = self.bsElement['type'].split(":")
			self.__type = PortType.fromName(name,self.parent)
			return self.__type

	def getSoapAction(self,opName) -> str:
		
		""" Given the name of an operation, return the soap action """

		operations = self.bsElement('operation',recursive=False)
		for operation in operations:
			if operation['name'] == opName:
				soapOp = operation('operation')[0]
				try:
					return soapOp['soapAction']
				except:
					self._log("Binding operation does not contain a soapAction element",2)
					return None

		self._log("Could not find matching operation, {0} in binding {1}".format(
													opName, self.name),2)

class PortType(Element):

	""" Simplified, native Python representation of portType definition in WSDL """

	@property
	def operations(self):
		try:
			return self.__operations
		except:
			self._log("Initializing operations for portType {0} from wsdl".format(self.name),5)
			operations = list()
			for operation in self.bsElement('operation',recursive=False):
				operations.append(Operation(operation,self.parent))
			self.__operations = tuple(operations)
			return self.__operations
	
	@property
	def methods(self):
		return self.operations

class Message(Element):

	@property
	def parts(self):
		try:
			return self.__parts
		except:
			self._log("Initializing parts for message {0}".format(self.name),5)
			parts = list()
			for part in self.bsElement('part',recursive=False):
				parts.append(Part(part,self.parent))
			self.__parts = tuple(parts)
			return self.__parts

class Part(Element):

	@property
	def type(self):
		try:
			return self.__type
		except:
			self.__type = self.parent.findTypeByName(self.bsElement['element'].split(':')[1])
			return self.__type

	@property
	def element(self):
		return self.type

	@property
	def ns(self):
		return self.bsElement['element'].split(':')[0]

	@property
	def namespace(self):
		return self.ns

class Operation(Element):
	
	""" Simplified, native Python representation of an operation definition in portType element group"""

	@property
	def input(self):
		try:
			return self.__input
		except:
			name = self.bsElement('input')[0].get('message').split(":")[1]
			self.__input = Message.fromName(name,self.parent)
			return self.__input

	@property
	def output(self):
		try: 
			return self.__output
		except:
			name = self.bsElement('output')[0].get('message').split(":")[1]
			self.__output = Message.fromName(name,self.parent)
			return self.__output

	@property
	def fault(self):
		try:
			return self.__fault
		except:
			searchResults = self.bsElement('fault')
			if len(searchResults) == 1:
				name = searchResults[0].get("message").split(":")[1]
				self.__fault = Message.fromName(name,self.parent)
				return self.__fault
			else:
				self._log("Operation has no fault message specified",2)
				self.__fault = None
				return self.__fault
