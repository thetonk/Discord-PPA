#!/usr/bin/env python3
import urllib3
from email.utils import parsedate
from tempfile import NamedTemporaryFile
import time
import logging

class Distribution():
    def __init__(self, name: str, url: str, headers: dict) -> None:
        self.name = name
        self.url = url
        self.http = urllib3.PoolManager()
        self.http_headers = headers
        self.logger = logging.getLogger(__name__)

    def _download_latest_deb(self, url: str, fp: NamedTemporaryFile):
        result = self.http.request("GET", url, headers=self.http_headers, redirect=True)
        if result.status == 200:
            self.logger.info(f"Downloaded correctly Discord .deb file for distribution '{self.name}'!")
            fp.write(result.data)
        else:
            self.logger.error(f"Discord .deb file for distribution '{self.name}' could not be downloaded! Status code: {result.status}")

    def is_package_new(self):
        raise NotImplementedError

class DiscordDistribution(Distribution):
    def __init__(self, distro_name: str, url: str, http_headers: dict = {}) -> None:
        super().__init__(distro_name, url, http_headers)
        self.last_modified = 0

    def is_package_new(self) -> bool:
        result = self.http.request("HEAD", self.url, headers=self.http_headers, redirect=True)
        if result.status == 200 and "last-modified" in result.headers:
            self.logger.info(f"Got last modified date successfully for URL {self.url}.")
            last_modified_header = result.headers["last-modified"]
            last_modified = int(time.mktime(parsedate(last_modified_header)))
            self.logger.info(f"Distribution '{self.name}' got last modified on {last_modified_header}")
            if last_modified != self.last_modified:
                self.last_modified = last_modified
                return True
            return False
        else:
            self.logger.error(f"Could not get last modified date for URL {self.url}! Status code: {result.status}")
            return False

    def download_latest_deb(self, fp: NamedTemporaryFile):
        return super()._download_latest_deb(self.url, fp)

class GithubDistribution(Distribution):
    def __init__(self, github_repo: str, distro_name: str, github_token: str | None = None, http_headers: dict = {}) -> None:
        url = f"https://api.github.com/repos/{github_repo}/releases"
        self.github_token = github_token
        self.latest_release = None
        self.repo = github_repo
        self.deb_package_url = None
        super().__init__(distro_name, url, http_headers)
        if self.github_token is not None:
            self.http_headers["Authorization"] = f"Bearer {self.github_token}"

    def is_package_new(self) -> bool:
        self.deb_package_url = None
        api_response = self.http.request("GET", self.url, headers=self.http_headers)
        assert api_response.status == 200
        api_json = api_response.json()
        if len(api_json) > 0:
            latest_release = api_json[0]
            latest_release_tag = latest_release["tag_name"]
            if self.latest_release != latest_release_tag:
                self.logger.info(f"New GitHub release found on {self.repo}! Version {latest_release_tag}")
                self.latest_release = latest_release_tag
                assets = latest_release["assets"]
                for asset in assets:
                    if asset["name"].endswith("amd64.deb"):
                        self.deb_package_url = asset["browser_download_url"]
                        return True
                self.logger.warning(f"Deb package for release {self.latest_release} not found!")
        else:
            self.logger.warning("Github API Releases array contains nothing!")
        return False

    def download_latest_deb(self, fp: NamedTemporaryFile):
        if self.deb_package_url is not None:
            return super()._download_latest_deb(self.deb_package_url, fp)
