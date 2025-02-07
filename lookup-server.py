#                             discord-ppa
#                  Copyright (C) 2020 - Javinator9889
#                  Copyright (C) 2025 - thetonk
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
#from daemonize import Daemonize
import logging
import sys
import time
import dotenv
import os
import urllib3
import distribution
from sched import scheduler
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile

dotenv.load_dotenv()

delay_secs = int(os.getenv("DELAY_SECONDS", 900))
user_agent = os.getenv("USER_AGENT", r"Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0")
github_access_token = os.getenv("GITHUB_TOKEN", None)
http_headers = {"User-Agent": user_agent}


discord_stable = distribution.DiscordDistribution("stable", r"https://discordapp.com/api/download?platform=linux&format=deb", http_headers)
discord_beta = distribution.DiscordDistribution("beta", r"https://discordapp.com/api/download/ptb?platform=linux&format=deb", http_headers)
discord_canary = distribution.DiscordDistribution("canary", r"https://discordapp.com/api/download/canary?platform=linux&format=deb", http_headers)
vesktop_stable = distribution.GithubDistribution("Vencord/Vesktop", "stable", github_access_token)

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


def update_reprepro(fp: NamedTemporaryFile, distro: distribution.Distribution):
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
    discord_packages = (discord_stable, discord_beta, discord_canary, vesktop_stable)
    for package in discord_packages:
        with NamedTemporaryFile(suffix=".deb") as tempfile:
            if package.is_package_new():
                package.download_latest_deb(tempfile)
                update_reprepro(tempfile, package)


#daemon = Daemonize(
#    app="discord-ppa", pid=pid, action=main, keep_fds=keep_fds, logger=logger
#)
#daemon.start()

if __name__ == "__main__":
    main()
