#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib
import httplib
import json, codecs
import traceback
import random
import datetime
import time
import gzip
import re
import glob
import requests
try:
    # Python 3
    from urllib.parse import urlparse, parse_qs
except ImportError:
    # Python 2
    from urlparse import urlparse, parse_qs
import xml.etree.ElementTree as etree
from uuid import getnode as get_mac

_addon_ = xbmcaddon.Addon('plugin.video.o2tvgo')
_addon_this_ = xbmcaddon.Addon('plugin.video.o2tvgo.xmltv')
_scriptname_ = _addon_this_.getAddonInfo('name')

_addon_dir_ = xbmc.translatePath( _addon_.getAddonInfo('path') )
sys.path.append( os.path.join( _addon_dir_ ) )

from o2tvgo import O2TVGO
from o2tvgo import ChannelIsNotBroadcastingError
from o2tvgo import LiveChannel
#from player import MyPlayer
from addon import _deviceId, _randomHex16, logDbg, logErr, _fetchChannels, _fetchChannel, _reload_settings, _toString, _sendError
reload(sys)
sys.setdefaultencoding('utf-8')

params = False

try:
    ###############################################################################
    _COMMON_HEADERS = { "X-Nangu-App-Version" : "Android#1.2.9",
                        "X-Nangu-Device-Name" : "Nexus 7",
                        "User-Agent" : "Dalvik/2.1.0 (Linux; U; Android 5.1.1; Nexus 7 Build/LMY47V)",
                        "Accept-Encoding": "gzip",
                        "Connection" : "Keep-Alive" }

    def o2tvgo__init__(self, device_id, username, password):
        self.username = username
        self.password = password
        self._live_channels = {}
        self.access_token = None
        self.subscription_code = None
        self.locality = None
        self.offer = None
        self.device_id = device_id
        self.channel_key = None
        self.epg_id = None

    def channel_epg(self):
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        if not self.channel_key:
            return
        headers = _COMMON_HEADERS
        cookies = { "access_token": access_token, "deviceId": self.device_id }
        timestampNow = int(time.time())
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
        params = {"language": "slo",
            "channelKey": self.channel_key,
            "fromTimestamp": fromTimestamp,
            "toTimestamp": toTimestamp}
        req = requests.get('http://app.o2tv.cz/sws/server/tv/channel-programs.json', params=params, headers=headers, cookies=cookies)
        j = req.json()
        return j

    def current_programme(self):
        if not self.channel_key:
            return
        epg = O2TVGO.channel_epg(self)
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
        #j = req.json()
        #return j

    def live_channel__init__(self, o2tv, channel_key, name = None, logo_url = None, weight = None):
        self._o2tv = o2tv
        self.channel_key = channel_key
        self.name = name
        self.weight = weight
        self.logo_url = logo_url

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


    O2TVGO.__init__ = o2tvgo__init__
    O2TVGO.channel_epg = channel_epg
    O2TVGO.current_programme = current_programme
    O2TVGO.epg_detail = epg_detail
    O2TVGO.setWatchPosition = setWatchPosition
    LiveChannel.__init__ = live_channel__init__
    LiveChannel.urlStartover = urlStartover
    LiveChannel.urlTimeshift = urlTimeshift
    
    ###############################################################################
    # First run
    if not (_addon_.getSetting("settings_init_done") == 'true'):
        DEFAULT_SETTING_VALUES = { 'send_errors' : 'false' }
        for setting in DEFAULT_SETTING_VALUES.keys():
            val = _addon_.getSetting(setting)
            if not val:
                _addon_.setSetting(setting, DEFAULT_SETTING_VALUES[setting])
        _addon_.setSetting("settings_init_done", "true")

    _device_id_ = _addon_.getSetting("device_id")
    if not _device_id_:
        first_device_id = _deviceId()
        second_device_id = _deviceId()
        if first_device_id == second_device_id:
            _device_id_ = first_device_id
        else:
            if _device_name_:
                _device_id_ = _fromDeviceId()
            else:
                _device_id_ = _randomHex16()
        _addon_.setSetting("device_id", _device_id_)

    ###############################################################################
    _profile_ = xbmc.translatePath(_addon_.getAddonInfo('profile'))
    _lang_   = _addon_.getLocalizedString
    _first_error_ = (_addon_.getSetting('first_error') == "true")
    _send_errors_ = (_addon_.getSetting('send_errors') == "true")
    _version_ = _addon_.getAddonInfo('version')
    _username_ = _addon_.getSetting("username")
    _password_ = _addon_.getSetting("password")
    _format_ = 'video/' + _addon_.getSetting('format').lower()
    _icon_ = xbmc.translatePath( os.path.join(_addon_.getAddonInfo('path'), 'icon.png' ) )
    _handle_ = int(sys.argv[1])
    _baseurl_ = sys.argv[0]

    ###############################################################################
    _xmltv_ = xbmc.translatePath('special://home/o2tvgo-epg.xml')
    _xmltv_json_base_ = 'special://home/o2tvgo-epg-'
    _m3u_ = xbmc.translatePath('special://home/o2tvgo-prgs.m3u')
    _m3u_json_ = xbmc.translatePath('special://home/o2tvgo-prgs.json')
    _m3u_additional_ = xbmc.translatePath('special://home/o2tvgo-prgs-additional.m3u')
    _xmltv_additional_filelist_pattern_ = xbmc.translatePath('special://home/rytecxmltv*.gz')
    _xmltv_additional_ = xbmc.translatePath('special://home/merged_epg.xml')
    _xmltv_additional_gzip_ = xbmc.translatePath('special://home/merged_epg.xml.gz')
    _xmltv_test_output_file_ = xbmc.translatePath('special://home/merged_xml_test_out.xml')
    _epg_shift_ = 2 * 60 * 60

    _o2tvgo_ = O2TVGO(_device_id_, _username_, _password_)
    ###############################################################################
    def log(msg, level=xbmc.LOGDEBUG):
        if type(msg).__name__=='unicode':
            msg = msg.encode('utf-8')
        xbmc.log("[%s] %s"%(_scriptname_,msg.__str__()), level)

    def logNtc(msg):
        log(msg,level=xbmc.LOGNOTICE)
        
    def notificationInfo(msg, sound = False):
        d = xbmcgui.Dialog()
        d.notification(_scriptname_, msg, xbmcgui.NOTIFICATION_INFO, 5000, sound)

    def notificationWarning(msg, sound = True):
        d = xbmcgui.Dialog()
        d.notification(_scriptname_, msg, xbmcgui.NOTIFICATION_WARNING, 5000, sound)

    def notificationError(msg, sound = True):
        d = xbmcgui.Dialog()
        d.notification(_scriptname_, msg, xbmcgui.NOTIFICATION_ERROR, 5000, sound)
    ###############################################################################
    def _emptyFunction():
        logDbg("function was replaced with a dummy empty one")

    channelListing = _emptyFunction

    def _fetchCurrentEpg(channel_key, hoursToLoad = 24):
        global _o2tvgo_
        _o2tvgo_.channel_key = channel_key
        _o2tvgo_.hoursToLoad = hoursToLoad
        epg = _o2tvgo_.current_programme()
        return epg

    def _fetchEpg(channel_key, hoursToLoad = 24, hoursToLoadFrom = None):
        global _o2tvgo_
        _o2tvgo_.channel_key = channel_key
        _o2tvgo_.hoursToLoad = hoursToLoad
        if hoursToLoadFrom:
            _o2tvgo_.hoursToLoadFrom = hoursToLoadFrom
        epg_list = _o2tvgo_.channel_epg()
        return epg_list

    def _fetchEpgDetail(epg_id):
        global _o2tvgo_
        _o2tvgo_.epg_id = epg_id
        epg_detail = _o2tvgo_.epg_detail()
        return epg_detail

    def _fetchCurrentEpgWithDetailAndNext(channel_key, hoursToLoad = 24):
        global _o2tvgo_
        _o2tvgo_.channel_key = channel_key
        _o2tvgo_.hoursToLoad = hoursToLoad
        epg_list = _o2tvgo_.channel_epg()
        if not epg_list:
            logErr("no epg_list in _fetchCurrentEpgWithDetailAndNext")
            return
        epg_curr = epg_list[0]
        if not epg_curr:
            logErr("no epg_curr in _fetchCurrentEpgWithDetailAndNext")
            return
        epg_curr.items()
        _o2tvgo_.epg_id = epg_curr['epgId']
        epg_curr_detail = _o2tvgo_.epg_detail()
        if not epg_curr_detail:
            logErr("no epg_curr_detail in _fetchCurrentEpgWithDetailAndNext")
            return
        epg_next = epg_list[1:]
        if not epg_next:
            logErr("no epg_next in _fetchCurrentEpgWithDetailAndNext")
            return
        return epg_curr, epg_curr_detail, epg_next

    def getPlayingVideo():
        player = xbmc.Player()
        isPlaying = player.isPlayingVideo()
        if not isPlaying:
            return None, None
        playingNow = player.getPlayingFile()
        if not playingNow:
            return None, None
        aPlayingNow = playingNow.split('/')
        playingNowFileName = aPlayingNow[-1]
        logDbg(playingNowFileName)
        return playingNow, playingNowFileName

    def compareChannelHosts(ch1, ch2):
        aCh1 = ch1.split('/')
        aCh2 = ch2.split('/')
        return aCh1[3] == aCh2[3]

    def channelListing():
        channels = _fetchChannels()
        if not channels:
            logErr("no channels in channelListing")
            return
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        addDirectoryItem("CH+", _baseurl_+ "?playnext=1", image=_icon_, isFolder=False)
        addDirectoryItem("CH-", _baseurl_+ "?playprevious=1", image=_icon_, isFolder=False)
        addDirectoryItem("Show Info", _baseurl_+"?showinfo=1", image=_icon_, isFolder=False)
        for channel in channels_sorted:
            logNtc("getting epg for " + channel.name)
            #logNtc("getting channel url and epg for " + channel.name)
            #link = channel.url() ##TODO is this needed for anything?? If so, put it in a try/except wrapper
            epg = _fetchCurrentEpg(channel.channel_key)
            #logDbg(epg)
            channelName = channel.name
            if epg['name']:
                channelName += ": " + epg['name']
            timeCurrent = " [" + _timestampishToTime(epg['startTimestamp']) + "-" + _timestampishToTime(epg['endTimestamp']) + "]"
            channelName += timeCurrent
            #logDbg(channelName)
            #logDbg(_baseurl_+ "?play=" + urllib.quote_plus(channel.channel_key))
            addDirectoryItem(channelName, _baseurl_+ "?play=" + urllib.quote_plus(channel.channel_key), image=channel.logo_url, isFolder=False)
        addDirectoryItem("Refresh CH/EPG", _baseurl_+ "?refreshepg=1", image=_icon_, isFolder=False)
        addDirectoryItem("Save EPG", _baseurl_+"?saveepg=1", image=_icon_, isFolder=False)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False)

    def addDirectoryItem(label, url, plot=None, title=None, date=None, icon=_icon_, image=None, fanart=None, isFolder=True):
        li = xbmcgui.ListItem(label)
        if not title:
            title = label
        liVideo = {'title': title}
        if image:
            li.setThumbnailImage(image)
        li.setIconImage(icon)
        li.setInfo("video", liVideo)
        xbmcplugin.addDirectoryItem(handle=_handle_, url=url, listitem=li, isFolder=isFolder)

    def saveChannels(restartPVR = True, notification = True):
        logNtc("saveChannels() started")
        if os.path.exists(_m3u_):
            lastModTimeM3U = os.path.getmtime(_m3u_)
            timestampNow = int(time.time())
            if os.path.exists(_m3u_additional_):
                lastModTimeM3UAdditional = os.path.getmtime(_m3u_additional_)
                if (timestampNow - lastModTimeM3U) <= (50 * 60) and (lastModTimeM3U - lastModTimeM3UAdditional) >= 0:
                    logNtc("'"+_m3u_+"' file fresh enough and '"+_m3u_additional_+"' file old enough; not refreshing")
                    return False
            elif (timestampNow - lastModTimeM3U) < (50 * 60):
                logNtc("'"+_m3u_+"' file fresh enough; not refreshing")
                return False
        logNtc("Starting refreshing of channels")
        channels = _fetchChannels()
        if not channels:
            logErr("no channels in channelListing")
            return False
        if notification:
            notificationInfo("Refreshing list of channels")
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        channelIndexesByBaseNames = {}
        channelKeysByIndex = {}
        channelIndexesByKey = {}
        i = 0
        m3u = "#EXTM3U\n"
        for channel in channels_sorted:
            try:
                m3u += '#EXTINF:-1 tvg-id="'+channel.channel_key+'" tvg-name="'+channel.name+'" tvg-logo="'+channel.logo_url+'" group-title="O2TVGO"'+", "+channel.name+"\n"
                channel_url = channel.url()
                m3u += channel_url + "\n"
                
                aUrl = channel_url.split('/')
                sUrlFileName = aUrl[-1]
                aUrlFileName = sUrlFileName.split('.')
                channelUrlBaseName = aUrlFileName[0]
                channelIndexesByBaseNames[channelUrlBaseName] = i
                channelKeysByIndex[i] = channel.channel_key
                channelIndexesByKey[channel.channel_key] = i
                i += 1
            except ChannelIsNotBroadcastingError:
                logDbg("Channel "+channel.name+" is not broadcasting; skipping it")
                
        if os.path.exists(_m3u_additional_):
            additional_m3u = open(_m3u_additional_, 'r')
            if additional_m3u:
                additional_prgs = additional_m3u.read()
                additional_m3u.close()
                if additional_prgs:
                    m3u += additional_prgs
            else:
                logErr("Could not open 'o2tvgo-prgs-additional.m3u' for reading")
        m3u_file = open(_m3u_, 'w+')
        if m3u_file:
            m3u_file.write(m3u)
            m3u_file.close()
            logNtc("'"+_m3u_+"' file saved successfully")
            if restartPVR:
                _restartPVR()
        else:
            logErr("Could not open '"+_m3u_+"' for writing")
        channelsDict = {"indexesByBaseNames": channelIndexesByBaseNames, "keysByIndex": channelKeysByIndex, "indexesByKey": channelIndexesByKey}
        with open(_m3u_json_, 'wb') as f:
            json.dump(channelsDict, codecs.getwriter('utf-8')(f), ensure_ascii=False)
        return notification
        
    def saveEPG(restartPVR = True, notification = True):
        logNtc("saveEPG() started")
        if os.path.exists(_xmltv_):
            lastModTimeXML = os.path.getmtime(_xmltv_)
            timestampNow = int(time.time())
            if os.path.exists(_m3u_additional_):
                lastModTimeM3UAdditional = os.path.getmtime(_m3u_additional_)
                if (timestampNow - lastModTimeXML) <= (4 * 60 * 60) and (lastModTimeXML - lastModTimeM3UAdditional) >= 0:
                    logNtc("'"+_xmltv_+"' file fresh enough and '"+_m3u_additional_+"' file old enough; not refreshing")
                    return False
            elif (timestampNow - lastModTimeXML) <= (4 * 60 * 60):
                logNtc("'"+_xmltv_+"' file fresh enough; not refreshing")
                return False
        logNtc("Starting refreshing of EPG")
        channels = _fetchChannels()
        if not channels:
            logErr("no channels in channelListing")
            return False
        if notification:
            notificationInfo("Refreshing EPG")
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        i = 0
        et_tv = etree.Element("tv")
        for channel in channels_sorted:
            et_channel = etree.SubElement(et_tv, "channel", id=channel.channel_key)
            et_channel_display_name = etree.SubElement(et_channel, "display-name", lang="sk").text = channel.name
        for channel in channels_sorted:
            logNtc("Fetching and parsing EPG for channel "+channel.name)
            json_epg = None
            jsonEpgFilePath = _xmltv_json_base_ + str(i) + ".json"
            jsonEpgFile = xbmc.translatePath(jsonEpgFilePath)
            if os.path.exists(jsonEpgFile):
                with open(jsonEpgFile) as data_file:    
                    json_epg = json.load(data_file)
                timestampNow = int(time.time())
                for key in json_epg.keys():
                    if timestampNow - int(json_epg[key]["end"]) > (2*24*3600):
                        del json_epg[key]
            if not json_epg:
                json_epg = {}
            epg = _fetchEpg(channel.channel_key, 2 * 24, 2 * 24)
            for prg in epg:
                et_programme = etree.SubElement(et_tv, "programme", channel=channel.channel_key)
                et_programme.set("start", _timestampishToEpgTime(prg['startTimestamp']))
                et_programme.set("stop", _timestampishToEpgTime(prg['endTimestamp']))
                et_programme_title = etree.SubElement(et_programme, "title", lang="sk").text = prg['name']
                ###epg details
                epg_id = prg['epgId']
                prg_detail = _fetchEpgDetail(epg_id)
                et_programme_subtitle = etree.SubElement(et_programme, "sub-title", lang="sk").text = prg['shortDescription']
                et_programme_desc = etree.SubElement(et_programme, "desc", lang="sk").text = prg_detail['longDescription']
                if prg_detail['picture']:
                    imageUrl = "http://app.o2tv.cz" + prg_detail['picture']
                elif prg['picture']:
                    imageUrl = "http://app.o2tv.cz" + prg['picture']
                else:
                    imageUrl = None
                    fanart_image = ""
                if imageUrl:
                    fanart_image = imageUrl
                    et_programme_icon = etree.SubElement(et_programme, "icon")
                    et_programme_icon.set("src", imageUrl)
                start = _timestampishToTimestamp(prg['startTimestamp'])
                json_epg[start] = { "start": start,
                                    "end": _timestampishToTimestamp(prg['endTimestamp']),
                                    "startTimestamp": prg['startTimestamp'],
                                    "endTimestamp": prg['endTimestamp'],
                                    "epgId": prg["epgId"],
                                    "title": prg['name'],
                                    "fanart_image": fanart_image,
                                    "plotoutline": prg['shortDescription'],
                                    "plot": prg_detail['longDescription'] }
            with open(jsonEpgFile, 'wb') as f:
                json.dump(json_epg, codecs.getwriter('utf-8')(f), ensure_ascii=False)
            i += 1
        xmlElTree = etree.ElementTree(et_tv)
        xmlString = etree.tostring(et_tv, encoding='utf8')
        xmltv_file = open(_xmltv_, 'w+')
        if xmltv_file:
            xmltv_file.write(xmlString)
            xmltv_file.close()
            logNtc("'o2tvgo-epg.xml' file saved successfully with O2TV epg")
            if restartPVR:
                _restartPVR()
        et_tv = _merge_additional_epg_xml(et_tv)
        xmlElTree = etree.ElementTree(et_tv)
        xmlString = etree.tostring(et_tv, encoding='utf8')
        xmltv_file = open(_xmltv_, 'w+')
        if xmltv_file:
            xmltv_file.write(xmlString)
            xmltv_file.close()
            logNtc("'o2tvgo-epg.xml' file saved successfully with additional epg")
            if restartPVR:
                _restartPVR()
        return notification

    def _restartPVR():
        player = xbmc.Player()
        isPlaying = player.isPlayingVideo()
        if isPlaying:
            playingNow = player.getPlayingFile()
            if playingNow.startswith("pvr://"):
                logNtc("Player is currently playing a pvr channel, not restarting")
                return
        logNtc("Stopping PVR manager")
        xbmc.executebuiltin("StopPVRManager()")
        logNtc("(Re)Starting PVR manager")
        xbmc.executebuiltin("StartPVRManager()")
        logNtc("PVR manager restart done")
        notificationInfo("PVR manager was restarted")

    def _merge_additional_epg_xml(et_tv, test=False):
        logNtc("Starting merge of additional epg xml files to '"+_xmltv_+"'")
        if test:
            et_tv = etree.Element("tv")
            et_programme = etree.SubElement(et_tv, "programme", id="prg1")
            et_programme.set("start", "201701142000")
            et_programme.set("stop", "201701142100")
            et_programme_title = etree.SubElement(et_programme, "title", lang="sk").text = "title"
            logDbg(etree.tostring(et_tv, encoding='utf8'))
        #else:
            #return et_tv
        ##^temporary
        additional_xml_file_list = glob.glob(_xmltv_additional_filelist_pattern_)
        if additional_xml_file_list:
            #logDbg('Found the following additional epg xml files:')
            #logDbg(additional_xml_file_list)
            for filepath in additional_xml_file_list:
                additional_xml_file = gzip.open(filepath, 'r')
                additional_xml = additional_xml_file.read()
                additional_xml_file.close()
                if additional_xml:
                    logNtc("Starting merge of epg from file '"+filepath+"'")
                    et_tv = _merge_additional_epg_xml_from_filecontents(et_tv, additional_xml)
                else:
                    logErr("Could not open '"+filepath+"' for reading")
                    return et_tv
        else:
            additionalXML = False
            if os.path.exists(_xmltv_additional_):
                additional_xml_file = open(_xmltv_additional_, 'r')
                additional_xml = additional_xml_file.read()
                additional_xml_file.close()
                additionalXML = True
                filepath = _xmltv_additional_
            elif os.path.exists(_xmltv_additional_gzip_):
                additional_xml_file = gzip.open(_xmltv_additional_gzip_, 'r')
                additional_xml = additional_xml_file.read()
                additional_xml_file.close()
                additionalXML = True
                filepath = _xmltv_additional_gzip_
            if additionalXML:
                if additional_xml:
                    logNtc("Starting merge of epg from file '"+filepath+"'")
                    et_tv = _merge_additional_epg_xml_from_filecontents(et_tv, additional_xml)
                else:
                    logErr("Could not open '"+filepath+"' for reading")
                    return et_tv
        if test:
            xmlElTree = etree.ElementTree(et_tv)
            xmlString = etree.tostring(et_tv, encoding='utf8')
            xmltv_file = open(_xmltv_test_output_file_, 'w+')
            if xmltv_file:
                xmltv_file.write(xmlString)
                xmltv_file.close()
                logNtc("'"+_xmltv_test_output_file_+"' file saved successfully")
        return et_tv

    def _merge_additional_epg_xml_from_filecontents(et_tv, additional_xml):
        additional_channel_list = _getAdditionalChannelNames()
        #parser = etree.XMLParser(encoding="utf-8") #only in v >=2.7
        #additional_xml_root = etree.fromstring(additional_xml, parser=parser) #only in v >=2.7
        additional_xml_root = etree.fromstring(additional_xml)
        for channel_id in additional_channel_list:
            logNtc("Looking for 'channel' tag for '"+channel_id+"'")
            #channel_elem = additional_xml_root.find("channel[@id='"+channel_id+"']") #only in v >=2.7
            channel_elem = None
            channel_elems = additional_xml_root.findall("channel")
            for chelem in channel_elems:
                if chelem.attrib.get('id') == channel_id:
                    channel_elem = chelem
                    break
            if channel_elem:
                logNtc("Found 'channel' tag for '"+channel_id+"'")
                et_tv.append(channel_elem)
            logNtc("Looking for 'programme' tags for '"+channel_id+"'")
            #program_elems = additional_xml_root.findall("programme[@channel='"+channel_id+"']") #only in v >=2.7
            program_elems = additional_xml_root.findall("programme")
            if program_elems:
                logged = False
                for program_elem in program_elems:
                    if program_elem.attrib.get('channel') == channel_id:
                        if not logged:
                            logNtc("Found 'programme' tags for '"+channel_id+"'")
                            logged = True
                        et_tv.append(program_elem)
        return et_tv

    def _getAdditionalChannelNames():
        if os.path.exists(_m3u_additional_):
            additional_m3u = open(_m3u_additional_, 'r')
            if additional_m3u:
                additional_prgs = additional_m3u.read()
                additional_m3u.close()
            else:
                logErr("Could not open 'o2tvgo-prgs-additional.m3u' for reading")
                return []
        else:
            return []
        iterator = re.finditer('(?<=tvg-id=")[^"]*(?=")', additional_prgs, re.DOTALL | re.MULTILINE)
        return [additional_prgs[m.start():m.end()] for m in iterator]

    def _timestampishToEpgTime(timestamp):
        return datetime.datetime.fromtimestamp(
            _timestampishToTimestamp(timestamp)
        ).strftime('%Y%m%d%H%M%S')

    def _timestampishToTime(timestamp):
        return datetime.datetime.fromtimestamp(
            _timestampishToTimestamp(timestamp)
        ).strftime('%H:%M')

    def _timestampishToEpgHistoryTime(timestamp):
        return datetime.datetime.fromtimestamp(
            _timestampishToTimestamp(timestamp)
        ).strftime('%Y%m%dT%H%M%S')

    def _timestampishToTimestamp(timestamp):
        return int(timestamp)/1000

    def _setVideoInfo(channel_key, li, setThumbnailImage = False):
        epg, epg_detail, epg_next = _fetchCurrentEpgWithDetailAndNext(channel_key)
        if not epg_next:
            logErr("no epg_next in _setVideoInfo")
            return
        imageUrl = None
        if epg['picture']:
            imageUrl = "http://app.o2tv.cz" + epg['picture']
        elif epg_detail['picture']:
            imageUrl = "http://app.o2tv.cz" + epg_detail['picture']
        if imageUrl:
            if setThumbnailImage:
                li.setThumbnailImage(imageUrl)
            li.setProperty('fanart_image', imageUrl)
            #logDbg(imageUrl)
        videoinfo = {}
        if epg['name']:
            videoinfo['title'] = epg['name']
        else:
            videoinfo['title'] = ""
        timeCurrent = _timestampishToTime(epg['startTimestamp']) + "-" + _timestampishToTime(epg['endTimestamp']) + " "
        videoinfo['title'] += " [" + timeCurrent + "]"
        if epg['shortDescription']:
            videoinfo['plotoutline'] = epg['shortDescription']
        if epg_detail['longDescription']:
            videoinfo['plot'] = epg_detail['longDescription']
        else:
            videoinfo['plot'] = ""
        if epg_next and len(epg_next) > 0:
            videoinfo['plot'] += "\n\n\nNásledující pořady:\n\n".encode('utf-8')
            i = 0
            for program in epg_next:
                program.items()
                time = _timestampishToTime(program['startTimestamp']) + " - " + _timestampishToTime(program['endTimestamp']) + " "
                videoinfo['plot'] += time + program['name'] + "\n"
                if i > 10:
                    break
                i += 1
        videoinfo['duration'] = epg['endTimestamp']/1000 - epg['startTimestamp']/1000
        if epg_detail['series']:
            #if epg_detail['seriesName']:
                #videoinfo['title'] += ", series: " + epg_detail['seriesName']
            #if epg_detail['totalEpisodeNumber']:
                #videoinfo['title'] += " (" + str(epg_detail['totalEpisodeNumber']) + ")"
            if epg_detail['episodeName']:
                videoinfo['title'] += ", episode: " + epg_detail['episodeName']
            if epg_detail['season']:
                videoinfo['season'] = epg_detail['season']
            if epg_detail['episodeNumber']:
                videoinfo['episode'] = epg_detail['episodeNumber']
        if videoinfo['title']:
            #li.setLabel(videoinfo['title'])
            li.setLabel2(videoinfo['title'])
        li.setInfo('video', videoinfo)
        #logDbg(_toString(videoinfo))
        return li

    def playChannel(channel_key):
        r = _fetchChannel(channel_key)
        if not r:
            logErr("no channel in playChannel")
            return
        link, channel = r
        pl=xbmc.PlayList(1)
        pl.clear()
        li = xbmcgui.ListItem(channel.name)
        li.setThumbnailImage(channel.logo_url)
        li = _setVideoInfo(channel_key, li)
        xbmc.PlayList(1).add(link, li)
        xbmc.Player().play(pl)
        
    def getChannelKeyPvr(playingNow):
        #logDbg(playingNow)
        aPlayingNow = playingNow.split('/')
        sPlayingNowFileName = aPlayingNow[-1]
        aPlayingNowFileName = sPlayingNowFileName.split('.')
        channelIndex = aPlayingNowFileName[0]
        with open(_m3u_json_) as data_file:    
            channels = json.load(data_file)
        channelKey = channels["keysByIndex"][channelIndex]
        return channelIndex, channelKey
        
    def getChannelKeyVideo(playingNow):
        aPlayingNow = playingNow.split('/')
        sPlayingNowFileName = aPlayingNow[-1]
        aPlayingNowFileName = sPlayingNowFileName.split('.')
        sPlayingNowFileNameBase = aPlayingNowFileName[0]
        aParts = sPlayingNowFileNameBase.split('-')
        iCount = len(aParts)
        if iCount == 5:
            sChannelBaseName = sPlayingNowFileNameBase.rsplit('-', 2)[0]
        elif iCount == 4:
            sChannelBaseName = sPlayingNowFileNameBase.rpartition('-')[0]
        else:
            return None, None
        with open(_m3u_json_) as data_file:    
            channels = json.load(data_file)
        channelIndex = channels["indexesByBaseNames"][sChannelBaseName]
        channelKey = channels["keysByIndex"][channelIndex]
        return channelIndex, channelKey
    
    def getChannelIndexByKey(channelKey):
        with open(_m3u_json_) as data_file:    
            channels = json.load(data_file)
        channelIndex = channels["indexesByKey"][channelKey]
        return channelIndex
        
    def getChannelKeyByIndex(channelIndex):
        with open(_m3u_json_) as data_file:    
            channels = json.load(data_file)
        channelKey = channels["keysByIndex"][str(channelIndex)]
        #logNtc(channelKey)
        return channelKey

    def getEpgByChannelIndexAndTimestamp(channelIndex, timestamp):
        jsonEpgFilePath = _xmltv_json_base_ + str(channelIndex) + ".json"
        jsonEpgFile = xbmc.translatePath(jsonEpgFilePath)
        with open(jsonEpgFile) as data_file:    
            epg = json.load(data_file)
        
        epgNowKey = None
        epgNow = None
        startPos = None
        for key in sorted(epg.iterkeys()):
            if epg[key]["start"] == timestamp:
                epgNowKey = key
                epgNow = epg[key]
                startPos = timestamp - int(epg[key]["start"])
                return epgNowKey, epgNow, startPos
        if not epgNowKey or not epgNow or not startPos:
            for key in sorted(epg.iterkeys()):
                if epg[key]["start"] <= timestamp and timestamp <= epg[key]["end"]:
                    epgNowKey = key
                    epgNow = epg[key]
                    startPos = timestamp - int(epg[key]["start"])
                    return epgNowKey, epgNow, startPos
        return None, None, None
    
    def getChannelTimeshiftUrl(epg, channelKey, toTimestamp = None):
        global _o2tvgo_
        objChannel = LiveChannel(_o2tvgo_, channelKey)
        startTimestamp = epg["startTimestamp"]
        if not toTimestamp:
            toTimestamp = epg["endTimestamp"]

        channelUrlTimeshift = objChannel.urlTimeshift(startTimestamp, toTimestamp)
        logNtc("timeshift: " + channelUrlTimeshift)
        
        return channelUrlTimeshift
    
    def getChannelStartoverUrl(epg, channelKey):
        global _o2tvgo_
        objChannel = LiveChannel(_o2tvgo_, channelKey)
        startTimestamp = epg["startTimestamp"]

        channelUrlStartover = objChannel.urlStartover(startTimestamp)
        logNtc("startover: " + channelUrlStartover)
        
        return channelUrlStartover

    def setWatchPosition(epgId, watchPosition):
        global _o2tvgo_
        _o2tvgo_.setWatchPosition(epgId, watchPosition)
    
    def getTimestampFromDayTime(day, sTime):
        if len(day) == 3:
            days = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
        else:
            days = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
        dayWeekday = days[day]
        todayWeekday = datetime.datetime.today().weekday()
        if dayWeekday <= todayWeekday:
            diff = todayWeekday - dayWeekday
        else:
            dayWeekday -= 7
            diff = todayWeekday - dayWeekday
        date = datetime.datetime.today() - datetime.timedelta(days=diff)
        sDateTime = date.strftime('%Y%m%d')+" "+sTime
        try:
            dateTime = datetime.datetime.strptime(sDateTime, "%Y%m%d %H:%M")
        except TypeError:
            dateTime = datetime.datetime(*(time.strptime(sDateTime, "%Y%m%d %H:%M")[0:6]))
        timeDelta = (dateTime - datetime.datetime(1970, 1, 1))
        timestamp = timeDelta.total_seconds() - _epg_shift_
        return int(timestamp)
    
    def playChannelFromEpg(startTime, startDate, channelName, channelNumber, playingCurrently=False):
        player = xbmc.Player()

        logNtc("playing from epg")
        #logDbg(startDate)
        #logDbg(startTime)
        #logDbg(channelName)
        
        if playingCurrently:
            timestamp = int(time.time())
        else:
            timestamp = getTimestampFromDayTime(startDate, startTime)
        logDbg(timestamp)
        
        if not timestamp:
            msg = "Couldn't parse timestamp from startDate, startTime"
            notificationError(msg)
            logErr(msg)
            logDbg([startDate, startTime, channelName])
            return
        
        channelIndex = int(channelNumber) - 1
        channelKey = getChannelKeyByIndex(channelIndex)
        if not channelKey:
            channelKey = channelName
            channelIndex = getChannelIndexByKey(channelKey)
        
        if (not channelIndex and channelIndex != 0) or not channelKey:
            msg = "Couldn't get channel key or index"
            notificationError(msg)
            logErr(msg)
            return;
        
        epgKey, epg, startPos = getEpgByChannelIndexAndTimestamp(channelIndex, timestamp)
        if not epgKey or not epg or (not startPos and startPos != 0):
            msg = "EPG not found"
            notificationError(msg)
            logErr(msg)
            logDbg([channelIndex, timestamp, epgKey, epg, startPos])
            return
        
        timestampNow = int(time.time()) * 1000
        if timestampNow < epg["endTimestamp"]:
            if timestampNow < epg["startTimestamp"]:
                notificationWarning("Programme is in future!")
                return
            notificationWarning("Programme has not finished yet")
            return
            notificationInfo("Starting currently broadcasting programme from beginning")
            #endTimestamp = timestampNow
            #channelUrlNew = getChannelTimeshiftUrl(epg, channelKey, endTimestamp)
            channelUrlNew = getChannelStartoverUrl(epg, channelKey)
        else:
            notificationInfo("Starting past programme from beginning")
            endTimestamp = epg["endTimestamp"]
            channelUrlNew = getChannelTimeshiftUrl(epg, channelKey, endTimestamp)
        
        pl=xbmc.PlayList(1)
        pl.clear()
        li = xbmcgui.ListItem(epg["title"])

        if "fanart_image" in epg and epg["fanart_image"] and len(epg["fanart_image"]) > 0:
            li.setArt({
              'icon': epg["fanart_image"],
              "fanart": epg["fanart_image"],
              "poster": epg["fanart_image"]
            })
        videoinfo = {}
        if "plot" in epg and epg["plot"] and len(epg["plot"]) > 0:
            videoinfo['plot'] = epg['plot']
        if "plotoutline" in epg and epg["plotoutline"] and len(epg["plotoutline"]) > 0:
            videoinfo['plotoutline'] = epg['plotoutline']
        if len(videoinfo) > 0:
            li.setInfo('video', videoinfo)
        
        player.play(channelUrlNew, li)
        #setWatchPosition(epg["epgId"], startPos)

    def pausePlayer(channelNumber = None):
        logNtc("pausing")
        player = xbmc.Player()
        isPlaying = player.isPlayingVideo()
        if not isPlaying:
            logNtc("not playing: nothing to pause")
            return
        playingNow = player.getPlayingFile()
        channelIndex = None
        channelKey = None
        if playingNow.startswith("pvr://"):
            logNtc("playing pvr")
            if channelNumber:
                channelIndex = int(channelNumber) - 1
                channelKey = getChannelKeyByIndex(channelIndex)
            else:
                channelIndex, channelKey = getChannelKeyPvr(playingNow)
        elif playingNow.endswith("m3u8"):
            logNtc("not playing pvr")
            channelIndex, channelKey = getChannelKeyVideo(playingNow)
            if not channelKey:
                logErr("not playing O2TVGO stream")
                logDbg([playingNow, channelIndex, channelKey])
                return
        
        timestampNow = int(time.time())
        epgNowKey, epgNow, startPos = getEpgByChannelIndexAndTimestamp(channelIndex, timestampNow)
        if not epgNowKey or not epgNow or (not startPos and startPos != 0):
            msg = "EPG not found"
            notificationError(msg)
            logErr(msg)
            logDbg([channelIndex, timestampNow, epgNowKey, epgNow, startPos])
            return
        
        toTimestamp = timestampNow * 1000
        
        #channelUrlNew = getChannelTimeshiftUrl(epgNow, channelKey, toTimestamp)
        channelUrlNew = getChannelStartoverUrl(epgNow, channelKey)

        pl=xbmc.PlayList(1)
        pl.clear()
        li = xbmcgui.ListItem(epgNow["title"])

        player.play(channelUrlNew, li)
        setWatchPosition(epgNow["epgId"], startPos)

        player.pause()

    def logPlayingInfo():
        player = xbmc.Player()
        isPlaying = player.isPlayingVideo()
        if not isPlaying:
            logNtc("PlayingInfo: not playing")
            return
        playingNow = player.getPlayingFile()
        channelIndex = None
        channelKey = None
        if playingNow.startswith("pvr://"):
            logNtc("PlayingInfo: playing pvr")
            channelIndex, channelKey = getChannelKeyPvr(playingNow)
        elif playingNow.endswith("m3u8"):
            logNtc("PlayingInfo: playing m3u8 playlist file")
            channelIndex, channelKey = getChannelKeyVideo(playingNow)
            if not channelKey:
                logNtc("PlayingInfo: not playing an O2TVGO stream")
                logDbg(playingNow)
                return
        
        logNtc(channelIndex)
        logNtc(channelKey)
        return

    def refreshEpgForCurrentChannel():
        channel_key = getCurrentChannel()
        if not channel_key:
            logErr("no channel_key in refreshEpgForCurrentChannel")
            return
        playChannel(channel_key)

    def showInfo():
        channel_key = getCurrentChannel()
        if not channel_key:
            logErr("no channel_key in showInfo")
            return
        epg, epg_detail, epg_next = _fetchCurrentEpgWithDetailAndNext(channel_key)
        if not epg_next:
            logErr("no epg_next in _setVideoInfo")
            return
        imageUrl = None
        ###
        if epg['picture']:
            imageUrl = "http://app.o2tv.cz" + epg['picture']
        elif epg_detail['picture']:
            imageUrl = "http://app.o2tv.cz" + epg_detail['picture']
        ###
        if epg_detail['longDescription']:
            plot = epg_detail['longDescription']
        elif epg['shortDescription']:
            plot = epg['shortDescription']
        else:
            plot = ""
        ###
        if epg['name']:
            name = epg['name']
        else:
            name = ""
        ###
        timeCurrent = _timestampishToTime(epg['startTimestamp']) + "-" + _timestampishToTime(epg['endTimestamp']) + " "
        name += " [" + timeCurrent + "]"
        ###
        if epg_next and len(epg_next) > 0:
            plot += "\n\n\nNásledující pořady:\n\n".encode('utf-8')
            i = 0
            for program in epg_next:
                program.items()
                time = _timestampishToTime(program['startTimestamp']) + " - " + _timestampishToTime(program['endTimestamp']) + " "
                plot += time + program['name'] + "\n"
                if i > 10:
                    break
                i += 1
        ###
        duration = epg['endTimestamp']/1000 - epg['startTimestamp']/1000
        ###
        details = ""
        if epg_detail['series']:
            if epg_detail['seriesName']:
                details += "Název seriálu: " + epg_detail['seriesName'] + "\n"
            if epg_detail['season']:
                details += "Série: " + epg_detail['season'] + "\n"
            if epg_detail['episodeName']:
                details += "Název dílu: " + epg_detail['episodeName'] + "\n"
            if epg_detail['episodeNumber']:
                details += "Číslo dílu: " + epg_detail['episodeNumber'] + "\n"
            if epg_detail['totalEpisodeNumber']:
                details += "Celkem dílů: " + str(epg_detail['totalEpisodeNumber']) + "\n"
        if details:
            plot = details + "\n\n\n" + plot
        ###
        xbmc.executebuiltin("ActivateWindow(10147)")
        controller = xbmcgui.Window(10147)
        xbmc.sleep(500)
        controller.getControl(1).setLabel(name)
        controller.getControl(5).setText(plot)

    def getCurrentChannel(channels_sorted = None):
        pl = xbmc.PlayList(1)
        index = pl.getposition()
        itemLabel = pl[index].getLabel()
        if not itemLabel:
            logErr("no itemLabel in getCurrentChannel")
            return
        if not channels_sorted:
            channels = _fetchChannels()
            if not channels:
                logErr("no channels in getCurrentChannel")
                return
            channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        for channel in channels_sorted:
            if channel.name == itemLabel:
                return channel.channel_key
        logErr("no channel was matched to item label: " + _toString(itemLabel))
        return

    def playPreviousChannel():
        channels = _fetchChannels()
        if not channels:
            logErr("no channels in playPreviousChannel")
            return
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        channel_key = getCurrentChannel(channels_sorted)
        if not channel_key:
            logErr("no channel_key in playPreviousChannel")
            return
        prev_channel_key = None
        i = 0
        for channel in channels_sorted:
            if i == 0 and channel.channel_key == channel_key:
                #last one will be the previous
                i += 1
            elif channel.channel_key == channel_key:
                #end loop before prev_channel_key gets overwritten
                break
            else:
                i += 1
            prev_channel_key = channel.channel_key
        if not prev_channel_key:
            logErr("no prev_channel_key in playPreviousChannel")
            return
        playChannel(prev_channel_key)
        return

    def playNextChannel():
        channels = _fetchChannels()
        if not channels:
            logErr("no channels in playNextChannel")
            return
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        channel_key = getCurrentChannel(channels_sorted)
        if not channel_key:
            logErr("no channel_key in playNextChannel")
            return
        play_next_one = False
        i = 0
        for channel in channels_sorted:
            if channel.channel_key == channel_key:
                play_next_one = True
            elif play_next_one == True:
                playChannel(channel.channel_key)
                return
            elif i == 0:
                first_channel_key = channel.channel_key
            i += 1
        playChannel(first_channel_key)

    def _test():
        logNtc("Executing _test()")
        #_restartPVR()

    def get_params():
            param=[]
            paramstring=sys.argv[2]
            if len(paramstring)>=2:
                    params=sys.argv[2]
                    cleanedparams=params.replace('?','')
                    if (params[len(params)-1]=='/'):
                            params=params[0:len(params)-2]
                    pairsofparams=cleanedparams.split('&')
                    param={}
                    for i in range(len(pairsofparams)):
                            splitparams={}
                            splitparams=pairsofparams[i].split('=')
                            if (len(splitparams))==2:
                                    param[splitparams[0]]=splitparams[1]
            return param

    def assign_params(params):
        for param in params:
            try:
                globals()[param]=urllib.unquote_plus(params[param])
            except:
                pass

    play=None
    pause=None
    playnext=None
    playprevious=None
    refreshepg=None
    showinfo=None
    saveepg=None
    mergeepg=None
    get=None
    test=None
    showplayinginfo=None
    playfromepg=None
    starttime=None
    startdate=None
    channelname=None
    channelnumber=None
    playingcurrently=None
    params=get_params()
    assign_params(params)

    #logDbg(params)
    
    if play:
        playChannel(_toString(play))
    elif pause:
        pausePlayer(channelnumber)
    elif showplayinginfo:
        logPlayingInfo()
    elif playnext:
        playNextChannel()
    elif playprevious:
        playPreviousChannel()
    elif showinfo:
        showInfo()
    elif refreshepg:
        refreshEpgForCurrentChannel()
    elif saveepg:
        notified = saveChannels()
        notified = saveEPG()
    elif mergeepg:
        _merge_additional_epg_xml(None, True)
    elif playfromepg:
        playChannelFromEpg(starttime, startdate, channelname, channelnumber, playingcurrently)
    elif test:
        _test()
    else:
        channelListing()
except Exception as ex:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    xbmcgui.Dialog().notification(_scriptname_, _toString(exc_value), xbmcgui.NOTIFICATION_ERROR)
    logErr(_toString(exc_value))
    if not _first_error_:
        if xbmcgui.Dialog().yesno(_scriptname_, _lang_(30500), _lang_(30501)):
            _addon_.setSetting("send_errors", "true")
            _send_errors_ = (_addon_.getSetting('send_errors') == "true")
        _addon_.setSetting("first_error", "true")
        _first_error_ = (_addon_.getSetting('first_error') == "true")
