#!/usr/bin/python
"""
Author:  Nathan Crapo
Date:    7/30/12

Description: This is both a module and a script

The module provides a python class named StechPowerSwitch that allows managing
power for Server Tech Sentry Switched CDU ports.

When run as a script this acts as a command line utilty to manage the DLI Power
switch.  Can also be imported into another script for consumption within.

The interface is based on a dli.py script written by Dwight Hubbard.
"""

import re
import pycurl
import bs4
import BeautifulSoup
import optparse
import base64
import os
import urllib



# Global settings
# Timeout in seconds
TIMEOUT = 5
COOKIEFILE = os.path.expanduser('~/.pwr-cookies')
ACTION_NONE  = 0
ACTION_ON    = 1
ACTION_OFF   = 2
ACTION_RESET = 3



def _format_state(state):
    """ The DLI class uses all caps and no spaces """
    if state == "Off":
        return "OFF"
    else:
        return "ON"

def _get_control_list(actions, num_ports):
    """ Create a string descriptor for each control """
    post_fields = ''
    for port in range(1, num_ports + 1):
        if port > 1:
            post_fields = post_fields + '&'
        control = 'ControlAction%%3F%d=%d' % (int(port), actions[port - 1])
        post_fields = post_fields + control
    return post_fields



class StechPowerSwitch:
    """
    Sentry Switched CDU control class.  Based on the interface for the DLI power
    strip.
    """
    def __init__(self, userid='admin', password='4321', hostname='192.168.0.100', num_ports=8):
        self.userid = userid
        self.password = password
        self.hostname = hostname
        self.contents = ''
        self.num_ports = num_ports
        try:
            os.remove(COOKIEFILE)
        except OSError:
            pass

    def verify(self):
        """ Verify we can reach the switch, returns true if ok """
        return self.geturl()

    def body_callback(self, buf):
        """ Called by pycurl as it's reading data from the server """
        self.contents = self.contents + buf

    def geturl(self, url='outctrl.html'):
        """
        Get the HTML located at URL for the power switch.
        """
        self.contents = ''
        headers = { 'Authorization'   : 'Basic %s' % base64.b64encode("%s:%s" % (self.userid, self.password)) }

        curl = pycurl.Curl()
        curl.setopt(curl.TIMEOUT, TIMEOUT)
        curl.setopt(curl.URL, "http://%s/%s" % (self.hostname, url))
        curl.setopt(curl.HTTPHEADER, ["%s: %s" % t for t in headers.items()])
        curl.setopt(curl.WRITEFUNCTION, self.body_callback)
        curl.setopt(curl.COOKIEJAR, COOKIEFILE)
        curl.setopt(curl.COOKIEFILE, COOKIEFILE)
        try:
            curl.perform()
            curl.close()
        except pycurl.error:
            raise Exception("Could not login to Stech Powerstrip %s@%s" % (self.userid, self.hostname))
            return None
        return self.contents

    def off(self, outlet=0):
        """ Turn off a power to an outlet """
        if outlet < 1:
            return -1
        self.geturl() # Login and setup cookie
        actions = [ ACTION_NONE ] * self.num_ports
        actions[outlet - 1] = ACTION_OFF
        self._post_outlet_control(actions)

    def on(self, outlet=0):
        """ Turn on power to an outlet """
        if outlet < 1:
            return -1
        self.geturl() # Login and setup cookie
        actions = [ ACTION_NONE ] * self.num_ports
        actions[outlet - 1] = ACTION_ON
        self._post_outlet_control(actions)

    def _post_outlet_control(self, actions):
        """ Post a set of actions to the outlet control form """
        self.contents = ''
        post_fields = _get_control_list(actions, self.num_ports)
        curl = pycurl.Curl()
        headers = { 'Authorization'   : 'Basic %s' % base64.b64encode("%s:%s" % (self.userid, self.password)) }
        curl.setopt(curl.HTTPHEADER, ["%s: %s" % t for t in headers.items()])
        curl.setopt(curl.URL, 'http://%s/Forms/outctrl_1' % self.hostname)
        curl.setopt(curl.POSTFIELDS, post_fields)
        curl.setopt(curl.WRITEFUNCTION, self.body_callback)
        curl.setopt(curl.COOKIEJAR, COOKIEFILE)
        curl.setopt(curl.COOKIEFILE, COOKIEFILE)
        curl.perform()

    def status_list(self):
        """
        RETURN the status of all outlets in a list, each item will contain 3
        itmes plugnumber, hostname and state
        """
        outlets = []
        outlet_control_page = self.geturl('outctrl.html')
        if not outlet_control_page:
            return None
        soup = BeautifulSoup.BeautifulSoup(outlet_control_page)
        try:
            outlet_table = soup.find('table', cellpadding='1')
            rows = outlet_table.findAll('tr')[4:]
            for row in rows:
                columns = row.findAll('td', colspan=None)
                if len(columns) < 6:
                    break
                port_id = re.sub('&nbsp;', '', columns[1].font.string)
                hostname = re.sub('&nbsp;', '', columns[2].font.string)
                num = int(re.sub(r'A', r'', port_id))
                state = re.sub('&nbsp;', '', columns[3].font.string)
                state = _format_state(state)
                outlets.append([ num, hostname, state ])
        except IndexError:
            return None
        return outlets

    def print_status(self):
        """ Print the status off all the outlets as a table to stdout """
        outlet_list = self.status_list()
        if not outlet_list:
            print "Unable to communicte to the Web power switch at %s" % self.hostname
            return None
        print 'Outlet\t%-15.15s\tState' % 'Hostname'
        for item in outlet_list:
            print '%d\t%-15.15s\t%s' % (item[0], item[1], item[2])

    def get_num_ports(self):
        return self.num_ports

    def status(self, outlet=1):
        """ Return the status of an outlet, returned value will be one of: On, Off, Unknown """
        outlets = self.status_list()
        if outlet:
            for plug in outlets:
                if plug[0] == outlet:
                    return plug[2]
        return 'Unknown'



if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('--hostname', dest='hostname', default="10.0.54.123")
    parser.add_option('--user',     dest='user',     default="bsplab")
    parser.add_option('--password', dest='password', default="bsplab")
    (options, args) = parser.parse_args()

    switch = StechPowerSwitch(userid=options.user, password=options.password, hostname=options.hostname)
    if len(args):
        if len(args) == 2:
            if args[0].lower() in ['on', 'poweron']:
                switch.on(int(args[1]))
            if args[0].lower() in ['off', 'poweroff']:
                switch.off(int(args[1]))
            if args[0].lower() in ['status']:
                print switch.status(int(args[1]))
    else:
        switch.print_status()
