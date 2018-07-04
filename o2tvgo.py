#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import time

__author__ = "charliecek"
__license__ = "MIT"
__version__ = "1.0.2"
__email__ = "charliecek@gmail.com"


_COMMON_HEADERS = { "X-Nangu-App-Version" : "Android#3.5.31.0-release",
                    "X-Nangu-Device-Name" : "Lenovo B6000-H",
                    "X-NanguTv-Device-size": "large", 
                    "X-NanguTv-Device-density": "213", 
                    "User-Agent" : "Dalvik/1.6.0 (Linux; U; Android 4.4.2; Lenovo B6000-H Build/KOT49H)",
                    "Accept-Encoding": "gzip",
                    "Connection" : "Keep-Alive" }

# Kanál
class LiveChannel:

    def __init__(self, o2tv, channel_key, name, logo_url, weight):
        self._o2tv = o2tv
        self.channel_key = channel_key
        self.name = name
        self.weight = weight
        self.logo_url = logo_url

    def url(self):
        if not self._o2tv.access_token:
            self._o2tv.refresh_access_token()
        access_token = self._o2tv.access_token
        if not self._o2tv.subscription_code:
            self._o2tv.refresh_configuration()
        subscription_code = self._o2tv.subscription_code
        playlist = None
        while access_token:
            params = {"serviceType":"LIVE_TV",
              "subscriptionCode":subscription_code,
              "channelKey": self.channel_key,
              "deviceType":"TABLET",
              "streamingProtocol":"HLS"}
            headers = _COMMON_HEADERS
            cookies = { "access_token": access_token, "deviceId": self._o2tv.device_id }
            req = requests.get('http://app.o2tv.cz/sws/server/streaming/uris.json', params=params, headers=headers, cookies=cookies)
            jsonData = req.json()
            access_token = None
            if 'statusMessage' in jsonData:
                status = jsonData['statusMessage']
                if status == 'bad-credentials':
                    access_token = self._o2tv.refresh_access_token()
                elif status == 'channel.not-found':
                    raise ChannelIsNotBroadcastingError()
                else:
                    raise Exception(status)
            else:
                playlist = jsonData["uris"][0]["uri"]
        return playlist

    ######## ADDED ########
    def urlStartover(self, fromTimestamp):
        if not self._o2tv.access_token:
            self._o2tv.refresh_access_token()
        access_token = self._o2tv.access_token
        if not self._o2tv.subscription_code:
            self._o2tv.refresh_configuration()
        subscription_code = self._o2tv.subscription_code
        playlist = None
        while access_token:
            params = {"serviceType":"STARTOVER_TV",
              "subscriptionCode": subscription_code,
              "channelKey": self.channel_key,
              "deviceType":"TABLET",
              "fromTimestamp": fromTimestamp,
              "streamingProtocol":"HLS"}
            headers = _COMMON_HEADERS
            cookies = { "access_token": access_token, "deviceId": self._o2tv.device_id }
            req = requests.get('http://app.o2tv.cz/sws/server/streaming/uris.json', params=params, headers=headers, cookies=cookies)
            jsonData = req.json()
            access_token = None
            if 'statusMessage' in jsonData:
                status = jsonData['statusMessage']
                if status == 'bad-credentials':
                    access_token = self._o2tv.refresh_access_token()
                elif status == 'channel.not-found':
                    raise ChannelIsNotBroadcastingError()
                else:
                    raise Exception(status)
            else:
                playlist = jsonData["uris"][0]["uri"]
        return playlist

    def urlTimeshift(self, fromTimestamp, toTimestamp):
        if not self._o2tv.access_token:
            self._o2tv.refresh_access_token()
        access_token = self._o2tv.access_token
        if not self._o2tv.subscription_code:
            self._o2tv.refresh_configuration()
        subscription_code = self._o2tv.subscription_code
        playlist = None
        while access_token:
            params = {"serviceType":"STARTOVER_TV",
              "subscriptionCode":subscription_code,
              "channelKey": self.channel_key,
              "deviceType":"TABLET",
              "fromTimestamp": fromTimestamp,
              "toTimestamp": toTimestamp,
              "streamingProtocol":"HLS"}
            #logDbg(params);
            headers = _COMMON_HEADERS
            cookies = { "access_token": access_token, "deviceId": self._o2tv.device_id }
            req = requests.get('http://app.o2tv.cz/sws/server/streaming/uris.json', params=params, headers=headers, cookies=cookies)
            jsonData = req.json()
            access_token = None
            if 'statusMessage' in jsonData:
                status = jsonData['statusMessage']
                if status == 'bad-credentials':
                    access_token = self._o2tv.refresh_access_token()
                elif status == 'channel.not-found':
                    raise ChannelIsNotBroadcastingError()
                else:
                    raise Exception(status)
            else:
                playlist = jsonData["uris"][0]["uri"]
        return playlist

class ChannelIsNotBroadcastingError(BaseException):
    pass

class AuthenticationError(BaseException):
    pass

class TooManyDevicesError(BaseException):
    pass

class O2TVGO:

    def __init__(self, device_id, username, password, logs = None,  scriptname = None):
        self.username = username
        self.password = password
        self._live_channels = {}
        self.access_token = None
        self.subscription_code = None
        self.locality = None
        self.offer = None
        self.device_id = device_id
        ######## ADDED ########
        self.channel_key = None
        self.epg_id = None
        self.forceFromTimestamp = None
        self.hoursToLoadFrom = None
        self.hoursToLoad = None
        if logs:
            self._logs_ = logs
        else:
            from logs import Logs
            self._logs_ = Logs(scriptname)

    def refresh_access_token(self):
        if not self.username or not self.password:
            raise AuthenticationError()
        headers = _COMMON_HEADERS
        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        data = {  'grant_type' : 'password',
                  'client_id' : 'tef-production-mobile',
                  'client_secret' : '627a4f43b2eea512702127e09c3921fc',
                  'username' : self.username,
                  'password' : self.password,
                  'platform_id' : '231a7d6678d00c65f6f3b2aaa699a0d0',
                  'language' : 'sk'}
        req = requests.post('https://oauth.o2tv.cz/oauth/token', data=data, headers=headers, verify=False)
        j = req.json()
        if 'error' in j:
            error = j['error']
            if error == 'authentication-failed':
                self._logs_.logErr(j)
                raise AuthenticationError()
            else:
                self._logs_.logErr(j)
                raise Exception(error)
        self.access_token = j["access_token"]
        self.expires_in = j["expires_in"]
        return self.access_token

    def refresh_configuration(self):
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        headers = _COMMON_HEADERS
        cookies = { "access_token": access_token, "deviceId": self.device_id }
        req = requests.get('http://app.o2tv.cz/sws/subscription/settings/subscription-configuration.json', headers=headers, cookies=cookies)
        j = req.json()
        if 'errorMessage' in j:
            errorMessage = j['errorMessage']
            statusMessage = j['statusMessage']
            if statusMessage == 'unauthorized-device':
                raise TooManyDevicesError()
            else:
                self._logs_.logErr(j)
                raise Exception(errorMessage)
        self.subscription_code = self._logs_._toString(j["subscription"])
        self.offer = j["billingParams"]["offers"]
        self.tariff = j["billingParams"]["tariff"]
        self.locality = j["locality"]

    def live_channels(self):
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        if not self.offer:
            self.refresh_configuration()
        offer = self.offer
        if not self.tariff:
            self.refresh_configuration()
        tariff = self.tariff
        if not self.locality:
            self.refresh_configuration()
        locality = self.locality
        if len(self._live_channels) == 0:
            headers = _COMMON_HEADERS
            cookies = { "access_token": access_token, "deviceId": self.device_id }
            params = { "locality": locality,
                "tariff": tariff,
                "isp": "3",
                "language": "slo",
                "deviceType": "MOBILE",
                "liveTvStreamingProtocol":"HLS",
                "offer": offer}
            req = requests.get('http://app.o2tv.cz/sws/server/tv/channels.json', params=params, headers=headers, cookies=cookies)
            j = req.json()
            if 'error' in j:
                self._logs_.logErr(j)
            purchased_channels = j['purchasedChannels']
            items = j['channels']
            for channel_id, item in items.iteritems():
                if channel_id in purchased_channels:
                    live = item['liveTvPlayable']
                    if live:
                        channel_key = self._logs_._toString(item['channelKey'])
                        logo = 'http://app.o2tv.cz' + self._logs_._toString(item['logo'])
                        name = self._logs_._toString(item['channelName'])
                        weight = item['weight']
                        self._live_channels[channel_key] = LiveChannel(self, channel_key, name, logo, weight)
            done = False
            offset = 0
            while not done:
                headers = _COMMON_HEADERS
                params = { "language": "slo",
                    "audience": "over_18",
                    "channelKey": self._live_channels.keys(),
                    "limit": 30,
                    "offset": offset}
                req = requests.get('http://www.o2tv.cz/mobile/tv/channels.json', params=params, headers=headers)
                j = req.json()
                items = j['channels']['items']
                for item in items:
                    item = item['channel']
                    channel_key = self._logs_._toString(item['channelKey'])
                    if 'logoUrl' in item.keys():
                        logo_url = "http://www.o2tv.cz" + item['logoUrl']
                        self._live_channels[channel_key].logo_url = logo_url
                offset += 30
                total_count = j['channels']['totalCount']
                if offset >= total_count:
                    done = True
        return self._live_channels

    ######## ADDED ########
    def channel_epg(self):
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        if not self.channel_key:
            return
        headers = _COMMON_HEADERS
        cookies = { "access_token": access_token, "deviceId": self.device_id }
        timestampNow = int(time.time())
        if self.forceFromTimestamp:
            fromTimestamp = int(self.forceFromTimestamp) * 1000
        else:
            if self.hoursToLoadFrom:
                secondsToLoadFrom = self.hoursToLoadFrom * 3600
            else:
                secondsToLoadFrom = 5 * 60
            fromTimestamp = ( timestampNow - secondsToLoadFrom ) * 1000

        if self.hoursToLoad:
            hoursToLoad = self.hoursToLoad
        else:
            hoursToLoad = 24
        toTimestamp = ( timestampNow + 3600 * hoursToLoad ) * 1000
        if fromTimestamp >= toTimestamp:
            self._logs_.logErr("O2TVGO.channel_epg(): fromTimestamp >= toTimestamp ("+str(fromTimestamp)+" >= "+str(toTimestamp)+")")
            return False
        params = {"language": "slo",
            "channelKey": self.channel_key,
            "fromTimestamp": fromTimestamp,
            "toTimestamp": toTimestamp}
        #logDbg(_toString(params))
        req = requests.get('http://app.o2tv.cz/sws/server/tv/channel-programs.json', params=params, headers=headers, cookies=cookies)
        j = req.json()
        return j

    def current_programme(self):
        if not self.channel_key:
            return
        epg = self.channel_epg()
        epg[0].items()
        return epg[0]

    def epg_detail(self):
        if not self.epg_id:
            return
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        headers = _COMMON_HEADERS
        cookies = { "access_token": access_token, "deviceId": self.device_id }
        params = {"language": "slo",
            "epgId": self.epg_id}
        req = requests.get('http://app.o2tv.cz/sws/server/tv/epg-detail.json', params=params, headers=headers, cookies=cookies)
        j = req.json()
        j.items()
        return j

    def setWatchPosition(self, epgId, watchPosition):
        #_origin=http://www.o2tv.sk
        #contentDataType=EPG
        #contentId=17322228
        #watchPosition=4650.983208

        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        if not self.channel_key:
            return
        headers = _COMMON_HEADERS
        cookies = { "access_token": access_token, "deviceId": self.device_id }
        params = {"_origin": "http://www.o2tv.sk",
            "contentDataType": "EPG",
            "contentId": epgId,
            "watchPosition": watchPosition}
        req = requests.get('http://app.o2tv.cz/sws/subscription/content/add-visited.json', params=params, headers=headers, cookies=cookies)
        j = req.json()
        return j
