# this app uses selenium to go to url and then navitage to the page with the data. if the entry with name is not connected, disable, reload and enable to reconnect
# it uses selenium, with debug flag to use head, else use headless
import time
import os
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import requests
import hashlib
from xml.etree import ElementTree

# get env variables
g_ip = os.environ.get("ENV_IP")
g_user = os.environ.get("ENV_USER")
g_passw = os.environ.get("ENV_PASS")
g_connection_names = os.environ.get("ENV_VPN_NAMES").split(";")
# remove empty strings and strip whitespaces and quotes
g_connection_names = list(filter(lambda x: x.strip() != "", g_connection_names))
g_connection_names = list(map(lambda x: x.strip().strip('"'), g_connection_names))

g_loop_time = os.environ.get("ENV_LOOP_DELAY")  # in seconds
g_headless = os.environ.get("ENV_HEADLESS") in ["true", "TRUE", "True", 1]

g_log_entries = []  # connection_name, enabled/disabled, time


def get_chrome_webdriver(headless):
    # add options
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument('--no-sandbox')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver


def get_fritzbox_overview_data(ip, user, password):
    # Get the challenge from the FRITZ!Box
    response = requests.get(f'http://{ip}/login_sid.lua', verify=False)
    xml_root = ElementTree.fromstring(response.content)
    challenge = xml_root.find('Challenge').text

    # Create the response string with the challenge and the password
    # Convert the password to the correct encoding and get the MD5 hash
    cp_str = f'{challenge}-{password}'.encode('utf-16le')
    md5_hash = hashlib.md5(cp_str).hexdigest()
    response_str = f'{challenge}-{md5_hash}'

    # Build the URL parameters for the session login
    url_params = {'username': user, 'response': response_str}

    # Get the session ID
    response = requests.get(f'https://{ip}/login_sid.lua', params=url_params, verify=False)
    xml_root = ElementTree.fromstring(response.content)
    sid = xml_root.find('SID').text
    # If the SID is 0000000000000000, the login was not successful
    if sid == '0000000000000000':
        raise Exception('Login not successful')

    # Use the session ID to get the overview data
    overview_data_response = requests.post(
        f'https://{ip}/data.lua',
        data={'xhr': '1', 'sid': sid, 'lang': 'de', 'page': 'overview', 'xhrId': 'all', 'useajax': '1',
              'no_sidrenew': ''},
        verify=False
    )

    return sid, overview_data_response.json()


def get_connection_status(driver, connection_sid, ip):
    url = "http://" + ip + "/?sid=" + connection_sid + "&lp=shares"
    driver.get(url)
    time.sleep(1)
    # find id shareWireguard
    share_wireguard = driver.find_element(By.ID, "shareWireguard")
    share_wireguard.click()
    time.sleep(1)

    # find all entries
    table_body = driver.find_elements(By.CLASS_NAME, "flexTableBody")
    # find network-connections FlexTable1Group1
    network_connections_table = table_body[0].find_element(By.ID, "FlexTable1Group1")
    # find all entries by flexRow
    rows = network_connections_table.find_elements(By.CLASS_NAME, "flexRow")
    connections = []
    for row in rows:
        # name class: vpnName
        name = row.find_element(By.CLASS_NAME, "vpnName").text
        # status class: led (if class is grey, then it is not connected, green if it is)
        status = row.find_element(By.CLASS_NAME, "led")
        status = "green" in status.get_attribute("class")
        # checkbox by input
        checkbox = row.find_element(By.TAG_NAME, "input")
        # check if checkbox is checked
        checked = checkbox.get_attribute("checked") == "true"
        connections.append({"name": name, "status": status, "checked": checked, "checkbox": checkbox, "row": row})

    return connections


def main(log_entries=g_log_entries, loop_time=g_loop_time, connection_names=g_connection_names, ip=g_ip, user=g_user,
         passw=g_passw, headless=g_headless):

    connection_sid, _ = get_fritzbox_overview_data(ip, user, passw)
    driver = get_chrome_webdriver(headless)

    while True:
        # if all connection_names are listed in log_entries with enable and time in last 5 minutes, wait 30s
        if all([any([x[0] == connection_name and x[1] == "enable" and time.time() - x[2] < 300 for x in log_entries])
                for
                connection_name in connection_names]):
            time.sleep(30)
            continue

        connections = get_connection_status(driver, connection_sid, ip)

        # filter for connection_names
        connections = list(filter(lambda x: x["name"] in connection_names, connections))

        # print time, only connection name and status
        print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "All connections:",
              list(map(lambda x: {x["name"]: x["status"]}, connections)))

        # filter for not connected
        connections = list(filter(lambda x: not x["status"], connections))

        # print time, only connection name and status
        print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "To fix connections:",
              list(map(lambda x: {x["name"]: x["status"]}, connections)))

        # disable and enable
        for connection in connections:
            # check if checkbox is checked
            log_entries.append([connection["name"], "disable" if connection['checked'] else "enable", time.time()])
            print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "disable" if connection['checked'] else "enable"
                  , connection["name"])

            connections_instance = get_connection_status(driver, connection_sid, ip)
            connection_instance = list(filter(lambda x: x["name"] == connection["name"], connections_instance))[0]

            connection_instance["checkbox"].click()
            time.sleep(1)
            # press apply id uiMainApply
            apply = driver.find_element(By.ID, "uiMainApply")
            apply.click()
            loop_time_instance = 10  # set lower loop time to wait for reconnect
            time.sleep(1)

        time.sleep(loop_time_instance)
        loop_time_instance = loop_time  # reset loop time


# Example usage:
if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            # if ctrl+c, exit
            if e.__class__.__name__ == "KeyboardInterrupt":
                break
            print(e)
            time.sleep(10)
            pass
