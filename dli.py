#!/usr/bin/python
import time,re,pycurl,BeautifulSoup,optparse

###############################################################
# Digital Loggers Web Power Switch management
###############################################################
# Version: 0.01
# Description: This is both a module and a script
#
#              The module provides a python class named
#              DLIPower that allows managing the web power
#              switch from python programs.
#
#              When run as a script this acts as a command
#              line utilty to manage the DLI Power switch.
# Author: Dwight Hubbard d@dhub.me
# Copyright: This module may be used for any use personal
#            or commercial as long as the author and copyright
#            notice are included in full.
###############################################################

# Global settings
# Timeout in seconds
TIMEOUT=5

class powerswitch:
    """ Manage the DLI Web power switch """
    def __init__(self,userid='admin',password='4321',hostname='192.168.0.100'):
        self.userid=userid
        self.password=password
        self.hostname=hostname
        self.contents=''
    def verify(self):
        """ Verify we can reach the switch, returns true if ok """
        return self.geturl()
    def body_callback(self,buf):
        self.contents=self.contents+buf
    def geturl(self,url='index.htm') :
        self.contents=''
        curl = pycurl.Curl()
        curl.setopt(curl.TIMEOUT,TIMEOUT)
        curl.setopt(curl.URL, 'http://%s:%s@%s/%s' % (self.userid,self.password,self.hostname,url))
        curl.setopt(curl.WRITEFUNCTION, self.body_callback)
        try:
            curl.perform()
            curl.close()
        except pycurl.error:
            raise Exception("Could not login to DLI Powerstrip %s@%s" % (self.userid, self.hostname))
            return None
        return self.contents
    def off(self,outlet=0):
        """ Turn off a power to an outlet """
        self.geturl(url= 'outlet?%d=OFF' % outlet)
    def on(self,outlet=0):
        """ Turn on power to an outlet """
        self.geturl(url= 'outlet?%d=ON' % outlet)
    def statuslist(self):
        """ Return the status of all outlets in a list,
        each item will contain 3 itmes plugnumber, hostname and state  """
        outlets=[]
        url=self.geturl('index.htm')
        if not url:
            return None
        soup=BeautifulSoup.BeautifulSoup(url)
        try:
            powertable=soup.findAll('table')[5]
        except IndexError:
            return None
        for temp in powertable.findAll('tr')[2:]:
            columns=temp.findAll('td')
            plugnumber=columns[0].string
            hostname=columns[1].string
            state=columns[2].find('font').string
            outlets.append([int(plugnumber),hostname,state])
        return outlets
    def printstatus(self):
        """ Print the status off all the outlets as a table to stdout """
        outlet_list = self.statuslist()
        if not outlet_list:
            print "Unable to communicte to the Web power switch at %s" % self.hostname
            return None
        print 'Outlet\t%-15.15s\tState' % 'Hostname'
        for item in outlet_list:
            print '%d\t%-15.15s\t%s' % (item[0],item[1],item[2])
    def status(self,outlet=1):
        """ Return the status of an outlet, returned value will be one of: On, Off, Unknown """
        outlets=self.statuslist()
        if outlet:
            for plug in outlets:
                if plug[0] == outlet:
                    return plug[2]
        return 'Unknown'



class DliPowerSwitch(powerswitch):
    """
    Inherit from the dli powerswitch class and add one more property - number of
    ports.  While this can be queried from the existing class, it requires a
    lengthy network transaction.  We know how many ports there are ahead of
    time.

    Also rename class interface to conform to Python naming convention so it
    matches the rest of our code.
    """
    def __init__(self, userid='admin', password='4321', hostname='192.168.0.100', num_ports=8):
        self.num_ports = num_ports
        powerswitch.__init__(self, userid, password, hostname)

    def status_list(self):
        return self.statuslist()

    def print_status(self):
        return self.printstatus()

    def get_num_ports(self):
        return self.num_ports



if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('--hostname',dest='hostname',default="10.0.54.120")
    parser.add_option('--user',    dest='user',    default="admin")
    parser.add_option('--password',dest='password',default="bsplab")
    (options, args) = parser.parse_args()

    switch=powerswitch(userid=options.user,password=options.password,hostname=options.hostname)
    if len(args):
        if len(args) == 2:
            if args[0].lower() in ['on','poweron']:
                switch.on(int(args[1]))
            if args[0].lower() in ['off','poweroff']:
                switch.off(int(args[1]))
            if args[0].lower() in ['status']:
                print switch.status(int(args[1]))
    else:
        switch.printstatus()
