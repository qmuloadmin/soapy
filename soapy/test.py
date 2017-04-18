from soapy.local_tests import *


class Config:
    """ Configuration constants """

    rtcp_host = "http://sfsvproxypreprod.opr.test.statefarm.org"
    rtcp_proxy = rtcp_host + ":3128"
    api_root = rtcp_host + ":7819/RTCP/rest/"
    ssl_proxy = rtcp_host + ":3199"


class VirtualServices(unittest.TestCase):
    """ Tests that rely on Rational Integration Tester virtualized services to test end-to-end behavior """

    def setUp(self):
        """ spin up virtual services """

        import requests
        from urllib.parse import urljoin
        from time import sleep

        # Get a list of domains, find the href for (ST) Systems Technology
        rolling_url = urljoin(Config.api_root, "domains/")
        response = requests.get(rolling_url)
        soup = BeautifulSoup(response.text, "xml")
        domains = soup("domain")
        for domain in domains:
            if "(ST)" in domain["name"]:
                rolling_url = urljoin(rolling_url, domain["href"])

        # Get a list of all environments inside ST domain
        response = requests.get(rolling_url)
        soup = BeautifulSoup(response.text, "xml")
        environments = soup("environment")
        for env in environments:
            if env["name"] == "soapy":
                rolling_url = urljoin(rolling_url, env["href"])

        # Parse out the environment and domain in expected format from url string provided from env href
        domain = rolling_url.split("/")[-3]
        env = rolling_url.split("/")[-2]

        # Build request string for all stubs for this environment
        rolling_url = Config.api_root + "stubs/?domain={}&env={}".format(domain, env)

        # Get list of all stubs and versions
        stub_versions = {}
        response = requests.get(rolling_url)
        soup = BeautifulSoup(response.text, "xml")
        stubs = soup("stub")

        # Iterate over all stubs. Versions should be in order, so the last occurrence with a given name will be
        # the latest version
        for stub in stubs:
            stub_versions[stub["name"]] = stub["href"]

        # POST to activate stubs
        for stub in stub_versions.values():
            stub_url = urljoin(rolling_url, stub)
            requests.post(stub_url, data="""<?xml version="1.0" encoding="UTF-8"?><start-stub />""",
                          headers={"Content-Type": "application/xml"})

        # Poll each instance until all are no longer PENDING
        def poll():
            for stub in stub_versions.values():
                stub_url = urljoin(rolling_url, stub + "instances/")
                response = requests.get(stub_url)
                soup = BeautifulSoup(response.text, "xml")
                instances = soup("instance")
                for instance in instances:
                    if instance["status"] != "RUNNING":
                        print("PENDING on {}".format(instance["id"]))
                        return True
            return False

        pending = poll()
        while pending:
            sleep(3)
            pending = poll()

    def validate_response(self, r, key_path: tuple, expected: str):
        self.assertTrue(r, "Response from virtual service for findActivity should be True")
        result = r.simple_outputs[key_path[0]]
        for key in key_path[1:]:
            result = result[key]
        self.assertEqual(result, expected, "Simple outputs should contain correct information from Response")

    def test_find_activities(self):
        c = Client("https://aceappserver/acedocs-public/wsdls/hpsm/SfHistoryManagement-v1.wsdl", 3, secure=False)
        c.operation = "findActivities"
        c.inputs[0].RecordType.value = "CHANGE_TASK"
        c.inputs[0].Activity.recordID.value = "T1341801"
        r = c(proxy_url=Config.rtcp_proxy)
        self.validate_response(r, ("activityDescription", "value", 0), '"Active" to "Closed"')

    def test_add_change_history(self):
        c = Client("https://aceappserver/acedocs-public/wsdls/mind/AddChangeHistory.wsdl", 3, "addChangeHistoryInfo",
                   secure=False)
        c.inputs[0].changeHistoryInput.newSignOnId.value = "QFLS"
        c.inputs[0].changeHistoryInput.newStAgntCode.value = "23-6105"
        c.inputs[0].changeHistoryInput.oldHostName.value = "ERBSVD"
        c.inputs[0].changeHistoryInput.type.value = "AGENT: MOVE/OFFICE CLOSING"
        c.inputs[0].changeHistoryInput.sfQChange.value = "C22053"
        c.inputs[0].changeHistoryInput.effectiveDate.value = "06/10/2016"
        # We need to set location because WSDL says location is localhost -- which doesn't try to use a proxy
        c.location = "http://sfsmint2.opr.statefarm.org:9093/sys/mindhistory/services/AddChangeHistory"
        r = c(proxy_url=Config.rtcp_proxy)
        self.validate_response(r, ('messageText', 'value'), "Test passed!")

    def test_retrieve_circuit_info(self):
        c = Client("https://aceappserver/acedocs-public/wsdls/mind/NetworkSolutions.wsdl", 3,
                   "retrieveEN4NetworkSolutionCiruitInfo", secure=False)
        c.inputs[0].networkSolutionInputTO.newHostName.value = "ERCCCCC"
        # We need to set location because WSDL says location is localhost -- which doesn't try to use a proxy
        c.location = "http://sfsmint2.opr.statefarm.org:9093/sys/netservice/services/NetworkSolutions"
        r = c(proxy_url=Config.rtcp_proxy)
        self.validate_response(r, ('peRouter', 'value'), "HS1TX302ME1")

    def test_send_manual_message(self):
        c = Client("http://sfsmint2.opr.statefarm.org:8080/webservices/wsdl/SfNotificationEngine-v1.wsdl", 3)
        c.service = "SfNotificationEngine_v1_2"
        c.operation = "sendManualMessage"
        c.inputs[0].Message.MessageText.value = "Testing soapy"
        c.inputs[0].Message.SenderAlias.value = "ace_int"
        c.inputs[0].Message.Subject.value = "Please Ignore"
        c.inputs[0].Message.Record.RecordID.value = 4
        c.inputs[0].Message.Record.RecordType.value = "CHANGE"
        c.inputs[0].Message.Recipients[0].Type.value = "GROUP"
        c.inputs[0].Message.Recipients[0].Code.value = "WG8902"
        c.inputs[0].Message.Recipients.append()
        c.inputs[0].Message.Recipients[1].Type.value = "GROUP"
        c.inputs[0].Message.Recipients[1].Code.value = "WG8903"
        r = c(proxy_url=Config.rtcp_proxy)
        self.validate_response(r, ("message", "value"), "The message was successfully added to the queue")

    def test_create_change(self):
        client = Client("https://aceappserver/acedocs-public/wsdls/hpsm/ChangeManagement-v3.wsdl", 3, "createChange",
                        secure=False)
        client.inputs[0].Category.value = "Standard Change"
        client.inputs[0].Template.value = "MAC - Agent (Circuit)"
        client.inputs[0].Change.briefDescription.value = \
            "R5;MAC;23-6105.Move/Office Closing//.2016-04-10 00:00:00.0."
        client.inputs[0].Change.agent.value = "lbhk"
        client.inputs[0].Change.impactedReceivers[0].value = "Agent-23-6105"
        client.inputs[0].Change.impactedReceivers.append("Agent-23-6106")
        client.inputs[0].Change.plannedStart.value = "2017-05-10T04:59:59"
        client.inputs[0].Change.targetDate.value = "2017-05-11T04:59:59"
        client.inputs[0].Change.plannedEnd.value = "2017-05-12T04:59:59"
        client.inputs[0].Change.changeRequester.value = "lbhk"
        r = client(proxy_url=Config.rtcp_proxy)
        self.validate_response(r, ('changeID', 'value'), 'C36412')

    def test_create_change_task(self):
        c = Client("https://aceappserver.opr.statefarm.org/acedocs-public/wsdls/hpsm/ChangeManagement-v3.wsdl", 3,
                   secure=False)
        c.operation = "createChangeTask"
        c.inputs[0].TaskType.value = "Build and Test"
        c.inputs[0].ParentChangeID.value = "C36412"
        c.inputs[0].ChangeTask.assignmentGroup.value = "WG1471"
        c.inputs[0].ChangeTask.scheduledStart.value = "2017-10-31T22:52:29+00:00"
        c.inputs[0].ChangeTask.scheduledEnd.value = "2017-11-30T22:52:29+00:00"
        c.inputs[0].ChangeTask.briefDescription.value = \
            "NFT: R5;MAC;23-6105.Move/Office Closing//.2016-04-10 00:00:00.0."
        c.inputs[0].ChangeTask.alteredCIs[0].value = "MACD"
        c.inputs[0].ChangeTask.alteredCIs.append("ERCCCCC")
        c.inputs[0].ChangeTask.installedOnCIs[0].value = "MACD"
        c.inputs[0].ChangeTask.taskInstructions.value = \
            "Please specify type of Netsol to be selected in task history - ETHERNET / MLPPP"
        r = c(proxy_url=Config.rtcp_proxy)
        self.validate_response(r, ('taskID', 'value'), 'T142945')

    def test_update_cucm_directory_number(self):
        c = Client(r'https://aceappserver.opr.statefarm.org/acedocs-public/wsdls/axl/AXLAPI.wsdl', -1, secure=False)
        c.operation = "updateLine"
        c.inputs[0].uuid.value = "{FA43F235-AB32-984B-5DG6-ABC321D18CE8}"
        c.inputs[0].newPattern.value = "5555432155"
        c.inputs[0].description.value = "R21-345; Test User - 555-543-2155; Stuff is fun"
        c.location = "http://sfsmint2.opr.statefarm.org:8080/axl/"
        r = c(proxy_url=Config.rtcp_proxy, secure=False)
        self.assertTrue(r)


class ComplexRender(unittest.TestCase):
    """ Tests for checking numerous advanced features of rendering behavior, dealing with Cisco AXL Web Services, and
     others """

    def setUp(self):
        self.client = Client(r'https://aceappserver.opr.statefarm.org/acedocs-public/wsdls/axl/AXLAPI.wsdl',
                             1,
                             secure=False)

    def test_options(self):
        """ Test to ensure the 'Options' type correctly sets child elements to minOccurs=0 """
        self.client.operation = "getGateway"
        self.client.inputs[0].uuid.value = "{FA43F235-AB32-984B-5DG6-ABC321D18CE8}"
        envelope = BeautifulSoup(str(self.client.request_envelope), "xml")
        control = BeautifulSoup("""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:tns="http://www.cisco.com/AXL/API/9.1">
        <soapenv:Header/>
        <soapenv:Body>
            <tns:getGateway>
                <uuid>{FA43F235-AB32-984B-5DG6-ABC321D18CE8}</uuid>
            </tns:getGateway>
        </soapenv:Body>
        </soapenv:Envelope>""", "xml")
        self.assertEqual(envelope("Envelope")[0]["xmlns:tns"], control("Envelope")[0]["xmlns:tns"],
                         "Cisco target namespace should match with control")
        self.assertEqual(envelope("uuid"), control("uuid"),
                         "Value for UUID should match with control")
        self.assertEqual(len(envelope("domainName")), 0,
                         "domainName should be omitted from rendered envelope when uuid is provided")

    def test_render_when_empty(self):
        """ Test to ensure configuring elements to render even when empty works properly """
        self.client.operation = "listGateway"
        self.client.inputs[0].returnedTags.description.render_empty()
        self.client.inputs[0].searchCriteria.domainName.value = "Test.domain.com"
        envelope = BeautifulSoup(str(self.client.request_envelope), "xml")
        control = BeautifulSoup("""<soapenv:Envelope xmlns:tns="http://www.cisco.com/AXL/API/9.1"
        xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
        <soapenv:Header/>
        <soapenv:Body>
            <tns:listGateway>
                <searchCriteria>
                    <domainName>Test.domain.com</domainName>
                </searchCriteria>
                <returnedTags>
                    <description/>
                </returnedTags>
            </tns:listGateway>
        </soapenv:Body>
        </soapenv:Envelope>""", "xml")
        self.assertEqual(envelope("domainName"), control("domainName"),
                         "Value for domainName should match control")
        self.assertEqual(len(envelope("description")), 1,
                         "description tag should be rendered even when empty when render_empty() is called")

    def test_render_attributes_and_order(self):
        self.client.operation = "updateDevicePool"
        self.client.inputs[0].uuid.value = "{FA43F235-AB32-984B-5DG6-ABC321D18CE8}"
        self.client.inputs[0].newName.value = "Something silly"
        self.client.inputs[0].mediaResourceListName['uuid'].value = \
            '{FA43F235-AB32-984B-5DG6-ABC321D18CE8}'
        self.client.inputs[0].mediaResourceListName.render_empty()
        envelope = BeautifulSoup(str(self.client.request_envelope), "xml")
        control = BeautifulSoup("""
        <soapenv:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:tns="http://www.cisco.com/AXL/API/9.1" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
        <soapenv:Header/>
        <soapenv:Body>
            <tns:updateDevicePool>
                <uuid>{FA43F235-AB32-984B-5DG6-ABC321D18CE8}</uuid>
                <newName>Something silly</newName>
                <mediaResourceListName uuid="{FA43F235-AB32-984B-5DG6-ABC321D18CE8}" xsi:nil="true"/>
            </tns:updateDevicePool>
        </soapenv:Body>
        </soapenv:Envelope>""", "xml")
        self.assertEqual(envelope("mediaResourceListName")[0]["uuid"], control("mediaResourceListName")[0]["uuid"],
                         "Attribute uuid should equal attribute value from control")
        self.assertEqual(str(envelope("Envelope")[0]).index("uuid"), str(control("Envelope")[0]).index("uuid"),
                         "uuid should render in the right place, before newName")
