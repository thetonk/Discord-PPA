#                             discord-ppa
#                  Copyright (C) 2020 - Javinator9889
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#                   (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#               GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.

#from logging.handlers import RotatingFileHandler
#from pathlib import Path
#import os
#from daemonize import Daemonize
import logging
import sys
import time
from sched import scheduler
from email.utils import parsedate
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile

import urllib3

delay_secs = 900
http_headers = {"User-Agent": r"Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}

class DiscordDistribution():
    def __init__(self, distro_name: str, url: str, last_modified: int = 0) -> None:
        self.name = distro_name
        self.url = url
        self.last_modified = last_modified

discord_stable = DiscordDistribution("stable", r"https://discordapp.com/api/download?platform=linux&format=deb")
discord_beta = DiscordDistribution("beta", r"https://discordapp.com/api/download/ptb?platform=linux&format=deb")
discord_canary = DiscordDistribution("canary", r"https://discordapp.com/api/download/canary?platform=linux&format=deb")

try:
    ppa_path = sys.argv[1]
except IndexError:
    print("You must provide the PPA directory")
    exit(1)
reprepro_cmd = "reprepro -b {0} includedeb %dist% %file%".format(ppa_path)
http = urllib3.PoolManager()

#home = str(Path.home())
#pid = "discord-ppa.pid"
#try:
#    os.mkdir("{0}/discord-ppa".format(home))
#except FileExistsError:
#    pass

logger = logging.getLogger('lookup-server')
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(name)s - %(asctime)s | [%(levelname)s]: %(message)s")
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.setFormatter(fmt)
logger.addHandler(handler)

#file_handler = RotatingFileHandler(
#    "discord-ppa.log".format(home), "w", maxBytes=2 << 20, backupCount=2
#    )
#file_handler.setLevel(logging.INFO)
#file_handler.setFormatter(fmt)

#logger.addHandler(file_handler)
#keep_fds = [file_handler.stream.fileno()]


def main():
    sched = scheduler(time.time, time.sleep)
    run_update_process()
    try:
        while True:
            sched.enter(delay_secs, 0, run_update_process)
            sched.run()
    except InterruptedError:
        exit(0)


def is_package_new(distro: DiscordDistribution) -> bool:
    result = http.request("HEAD", distro.url, headers=http_headers, redirect=True)
    if result.status == 200 and "last-modified" in result.headers:
        logger.info(f"Got last modified date successfully for URL {distro.url}.")
        last_modified_header = result.headers["last-modified"]
        last_modified = int(time.mktime(parsedate(last_modified_header)))
        logger.info(f"Distribution '{distro.name}' got last modified on {last_modified_header}")
        if last_modified != distro.last_modified:
            distro.last_modified = last_modified
            return True
        return False
    else:
        logger.error(f"Could not get last modified date for URL {distro.url}! Status code: {result.status}")
        return None


def download_latest_deb(fp: NamedTemporaryFile, distro: DiscordDistribution):
    result = http.request("GET", distro.url, headers=http_headers, redirect=True)
    if result.status == 200:
        logger.info(f"Downloaded correctly Discord .deb file for distribution '{distro.name}'!")
        fp.write(result.data)
    else:
        logger.error(f"Discord .deb file for distribution '{distro.name}' could not be downloaded! Status code: {result.status}")


def update_reprepro(fp: NamedTemporaryFile, distro: DiscordDistribution):
    cmd = reprepro_cmd.replace("%dist%", distro.name).replace("%file%", fp.name).split()
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate()
    if proc.returncode != 0:
        error = err.decode("utf-8")
        logger.error(f"reprepro for distribution '{distro.name}' ended with an error - ret. code: {proc.returncode} | output:\n {error}")
    else:
        output = out.decode("utf-8") + "\n" + err.decode("utf-8")
        logger.info(f"reprepro for distribution {distro.name} finished OK | output:\n {output}")


def run_update_process():
    canary = NamedTemporaryFile(suffix=".deb")
    stable = NamedTemporaryFile(suffix=".deb")
    beta = NamedTemporaryFile(suffix=".deb")
    try:
        if is_package_new(discord_stable):
            download_latest_deb(stable, discord_stable.url)
            update_reprepro(stable, discord_stable.name)
        if is_package_new(discord_beta):
            download_latest_deb(beta, discord_beta.url)
            update_reprepro(beta, discord_beta.name)
        if is_package_new(discord_canary):
            download_latest_deb(canary, discord_canary.url)
            update_reprepro(canary, discord_canary.name)
    finally:
        stable.close()
        beta.close()
        canary.close()


#daemon = Daemonize(
#    app="discord-ppa", pid=pid, action=main, keep_fds=keep_fds, logger=logger
#)
#daemon.start()

if __name__ == "__main__":
    main()
