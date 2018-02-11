#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function

import requests
from bs4 import BeautifulSoup
from getpass import getpass
import json
import argparse
import yaml
from slackclient import SlackClient
from datetime import datetime
from six.moves import input
import os


class SlackBackup(object):
    def __init__(self, conf,backup_dirname="backup"):
        self.set_login(conf)
        self.get_token_and_name()
        self.make_backup_directory(backup_dirname)
        self.sc = SlackClient(self.token)

    def make_backup_directory(self, backup_dirname):
        self.downloads_dir = backup_dirname + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir)
        print("Backup Directory:",self.downloads_dir)

    def set_login(self, conf):
        self.teamname = conf["teamname"] if "teamname" in conf else input("TeamName: ")
        self.email = conf["email"] if "email" in conf else input("E-mail: ")
        self.password = conf["password"] if "password" in conf else getpass("Password: ")
        self.baseurl = "https://" + self.teamname + ".slack.com/"

    def get_token_and_name(self):
        print("Get token...")
        try:
            s = requests.Session()
            r = s.get(self.baseurl)
            soup = BeautifulSoup(r.text, "lxml")
            formdata = soup.find("form", attrs={"id": "signin_form"})
            params = {"email": self.email, "password": self.password}
            for i in formdata.find_all("input", attrs={"type": "hidden"}):
                params[i["name"]] = i["value"]
            s.post(self.baseurl, data=params)
            messagehtml = s.get("https://api.slack.com/custom-integrations/legacy-tokens")
            messagesoup = BeautifulSoup(messagehtml.text, "lxml")
            self.token = messagesoup.find("input")["value"]
            userinfo = json.loads(
                s.post("https://slack.com/api/users.list", data={"token": self.token}).text)
            self.username = [user["name"] for user in userinfo["members"] if
                             "email" in user["profile"] and user["profile"]["email"] == self.email][0]

        except:
            print("You need to generate token")
            exit(1)

    def download_file(self, downfile):
        filedata = requests.get(downfile["url_private_download"], headers={"Authorization": "Bearer %s" % self.token},
                                stream=True)
        print("Downloading ...", downfile["name"])
        with open(os.path.join(self.downloads_dir,
                               datetime.fromtimestamp(int(downfile["timestamp"])).strftime("%Y%m%d_%H%M%S") + "_" +
                                       downfile["name"]), "wb") as f:
            for chunk in filedata.iter_content(chunk_size=1024):
                f.write(chunk)

    def run(self):
        fileslist = self.sc.api_call("files.list")
        fls = fileslist["files"][:5]
        for fl in fls:
            self.download_file(fl)
        maxpage = int(fileslist["paging"]["pages"])
        count = len(fileslist["files"])
        for i in range(2, maxpage + 1):
            ffl = self.sc.api_call("files.list", page=i)
            for fl in ffl["files"]:
                self.download_file(fl)
            count += len(ffl["files"])
        print(count)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Slack Files Backup Script")
    parser.add_argument("--backupdir", "-b", action="store", default="backup")
    parser.add_argument("--config", "-c", action="store")
    args = parser.parse_args()
    if args.config:
        with open(args.config) as f:
            config = yaml.load(f)
    else:
        config = {}
    slackbak = SlackBackup(config,backup_dirname=args.backupdir)
    slackbak.run()
