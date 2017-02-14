import unittest

from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError

from soapy.client import Client
from soapy.plugins import Doctor

""" The early beginnings of a test suite that doesn't use external resources """


class AuthTests(unittest.TestCase):

    """ Tests to validate the function of authentication options API"""

    def test_basic_auth(self):
        self.client = Client("file://sample.wsdl", 2, "getBank")
        self.client.username = "foo"
        self.client.password = "bar"
        self.assertEqual(type(self.client.auth), HTTPBasicAuth)


class InputTests(unittest.TestCase):

    """ Tests to validate the rendering and manipulation of inputs """

    def test_input_string(self):
        self.client = Client("file://sample.wsdl", 2, "getBank")
        self.assertEqual(str(self.client.inputs[0]), '<getBank >\r\n |   <blz >None</blz>\r\n</getBank>',
                         "InputFactory to-string should return correct null value representation")
        self.client.inputs[0].root_element.blz.value = "Foo"
        self.assertEqual(str(self.client.inputs[0]), '<getBank >\r\n |   <blz >Foo</blz>\r\n</getBank>',
                         "InputFactory to-string should return correct 'Foo' value representation")


class RenderTests(unittest.TestCase):

    """ Tests that verify envelopes are rendering consistently """

    v1 = """<soapenv:Envelope xmlns:tns="http://thomas-bayer.com/blz/"
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" >
<soapenv:Header/>
<soapenv:Body>
<tns:getBank>
<tns:blz>test</tns:blz>
</tns:getBank>
</soapenv:Body>
</soapenv:Envelope>"""

    v2 = """<soapenv:Envelope xmlns:tns="http://thomas-bayer.com/blz/"
    xmlns:soapenv="http://www.w3.org/2003/05/soap-envelope" >
<soapenv:Header/>
<soapenv:Body>
<tns:getBank>
<tns:blz>test</tns:blz>
</tns:getBank>
</soapenv:Body>
</soapenv:Envelope>"""

    def compare(self, version, control):
        version = str(version)
        self.client = Client("file://sample.wsdl", 2, "getBank", version=version)
        self.client.inputs[0].root_element.blz.value = "test"
        test_soup = BeautifulSoup(str(self.client.request_envelope), "xml")
        control_soup = BeautifulSoup(control, "xml")
        self.assertEqual(test_soup("Envelope")[0].attrs, control_soup("Envelope")[0].attrs,
                         "Envelope should use the correct namespace attributes for Version {}".format(version))
        self.assertEqual(test_soup("blz")[0].text, "test",
                         "Value for 'blz' should be set to correct value in envelope in Version {}".format(version))

    def test_version_one(self):
        self.compare(1.1, self.v1)

    def test_version_two(self):
        self.compare(1.2, self.v2)

    def test_wrong_version(self):
        """ This should raise an exception """
        with self.assertRaises(ValueError):
            self.compare(1.5, self.v2)
            self.compare("NaN", self.v1)
            self.compare(1.0, self.v2)


class PluginTests(unittest.TestCase):
    """ Test Various Features and Behavior of Plugins """

    def setUp(self):
        self.client = Client("file://sample.wsdl", 2, "getBank")
        self.client.inputs[0].root_element.blz.value = "test"
        self.client.location = "http://examplehost/fakeserver"

    location = "http://examplehost/service.asp"

    def failsafe(self, doc):
        try:
            self.client(doctors=(doc,))
        except ConnectionError:
            """ Do nothing, we only want to check the plugin behavior """

    class Echo(Doctor):

        """ A noop doctor """

        def __call__(self, client, xml, tl=-1):
            return xml

    class Loc(Doctor):

        """ A doctor that changes the location """

        def __call__(self, client, xml, tl=-1):
            client.location = PluginTests.location
            return xml

    def test_echo_plugin(self):
        init_xml = self.client.request_envelope
        doc = self.Echo()
        self.failsafe(doc)
        self.assertEqual(init_xml, self.client.request_envelope,
                         "XML should match before and after NO-OP Doctor plugin")

    def test_location_plugin(self):
        doc = self.Loc()
        self.failsafe(doc)
        self.assertEqual(self.client.location, self.location,
                         "Location should change correctly when Doctor plugin changes it")
