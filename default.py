#!/usr/bin/env python
# -*- coding: utf-8 -*-

## START: Copied from the original plugin by Štěpán Ort ##
import sys
import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib
import json
import random
from uuid import getnode as get_mac
## END: Copied from the original plugin by Štěpán Ort ##
import codecs
import datetime
import time
import gzip
import re
import glob
try:
    # Python 3
    from urllib.parse import urlparse, parse_qs
except ImportError:
    # Python 2
    from urlparse import urlparse, parse_qs
import xml.etree.ElementTree as etree

from o2tvgo import O2TVGO,  LiveChannel,  AuthenticationError, ChannelIsNotBroadcastingError,  TooManyDevicesError
from logs import Logs
from jsonrpc import JsonRPC

reload(sys)
sys.setdefaultencoding('utf-8')

params = False

try:
    ###############################################################################
    _addon_ = xbmcaddon.Addon('plugin.video.o2tvgo.iptv.simple')
    _scriptname_ = _addon_.getAddonInfo('name')
    _logs_ = Logs(_scriptname_)
    _jsonRPC_ = JsonRPC(_logs_)

    def _isAddonInstalled(addonId):
        addons = _jsonRPC_._getAddons()
        if addons:
            for addon in addons:
                if addonId == addon["addonid"]:
                    return True
            return False
        else:
            # No/incorrect response from jsonrpc server
            return False

    ## START: Copied from the original plugin by Štěpán Ort ##
    def _deviceId():
        mac = get_mac()
        hexed = hex((mac*7919)%(2**64))
        return ('0000000000000000'+hexed[2:-1])[16:]

    def _randomHex16():
        return ''.join([random.choice('0123456789abcdef') for x in range(16)])

    ## First run ##
    ## START @ch ##
    if not (_addon_.getSetting("settings_init_done") == 'true'):
        SETTING_KEYS = ['username',  'password',  'send_errors', 'device_id',  'settings_init_done']
        o2tvGoAddonId = "plugin.video.o2tvgo"
        isO2TVGoInstalled = _isAddonInstalled(o2tvGoAddonId)
        if isO2TVGoInstalled:
            o2tvGoPluginDetails = _jsonRPC_._getAddonDetails(o2tvGoAddonId)
            if o2tvGoPluginDetails and "enabled" in o2tvGoPluginDetails:
                isO2TVGoEnabled = o2tvGoPluginDetails["enabled"]
                if isO2TVGoEnabled:
                    _addon_o2tvgo_ = xbmcaddon.Addon(o2tvGoAddonId)
                    for settingKey in SETTING_KEYS:
                        settingVal = _addon_o2tvgo_.getSetting(settingKey)
                        if settingVal:
                            _addon_.setSetting(settingKey, settingVal)
    ## END @ch ##
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
            _device_id_ = _randomHex16()
            ## START @ch ##
#            if _device_name_:
#                _device_id_ = _fromDeviceId()
#            else:
#                _device_id_ = _randomHex16()
            ## END @ch ##
        _addon_.setSetting("device_id", _device_id_)

    ###############################################################################
    _profile_ = xbmc.translatePath(_addon_.getAddonInfo('profile')).decode("utf-8")
    _lang_   = _addon_.getLocalizedString
#    _first_error_ = (_addon_.getSetting('first_error') == "true")
    _send_errors_ = (_addon_.getSetting('send_errors') == "true")
    _version_ = _addon_.getAddonInfo('version')
    _username_ = _addon_.getSetting("username")
    _password_ = _addon_.getSetting("password")
    _format_ = 'video/' + _addon_.getSetting('format').lower()
    _icon_ = xbmc.translatePath( os.path.join(_addon_.getAddonInfo('path'), 'icon.png' ) )
    _handle_ = int(sys.argv[1])
    _baseurl_ = sys.argv[0]

    _o2tvgo_ = O2TVGO(_device_id_, _username_, _password_, _logs_, _scriptname_)

    ###############################################################################
    def _fetchChannels():
        global _o2tvgo_
        channels = None
        ex = False
        while not channels:
            try:
                channels = _o2tvgo_.live_channels()
            except AuthenticationError:
                if ex:
                    return None
                ex = True
                d = xbmcgui.Dialog()
                d.notification(_scriptname_, _lang_(30003), xbmcgui.NOTIFICATION_ERROR)
                _reload_settings()
            except TooManyDevicesError:
                d = xbmcgui.Dialog()
                d.notification(_scriptname_, _lang_(30006), xbmcgui.NOTIFICATION_ERROR)
                return None
        return channels

    def _reload_settings():
        _addon_.openSettings()
#        global _first_error_
#        _first_error_ = (_addon_.getSetting('first_error') == "true")
        global _send_errors_
        _send_errors_ = (_addon_.getSetting('send_errors') == "true")
        global _username_
        _username_ = _addon_.getSetting("username")
        global _password_
        _password_ = _addon_.getSetting("password")
        global _o2tvgo_
        _o2tvgo_ = O2TVGO(_device_id_, _username_, _password_, _logs_, _scriptname_)


    ## END: Copied from the original plugin by Štěpán Ort ##

    ###############################################################################
    ## Logging, debugging, messages - just redeclaring the methods from Logging so I don't have to rewrite every occurence
    def _toString(text):
        return _logs_._toString(text)
    def log(msg, level=xbmc.LOGDEBUG):
        return _logs_.log(msg,  level)
    def logDbg(msg):
        return _logs_.logDbg(msg)
    def logNtc(msg):
        return _logs_.logNtc(msg)
    def logErr(msg):
        return _logs_.logErr(msg)
    def notificationInfo(msg, sound = False):
        return _logs_.notificationInfo(msg,  sound)
    def notificationWarning(msg, sound = True):
        return _logs_.notificationWarning(msg,  sound)
    def notificationError(msg, sound = True):
        return _logs_.notificationError(msg,  sound)

    ###############################################################################
    ## Globals ##
    _addon_pvrIptvSimple_ = None
    _xmltv_ = xbmc.translatePath('special://home/o2tvgo-epg.xml')
    _xmltv_json_base_ = _profile_+'o2tvgo-epg-'
    _m3u_ = xbmc.translatePath('special://home/o2tvgo-prgs.m3u')
    _m3u_json_ = _profile_+'o2tvgo-prgs.json'
    _m3u_additional_ = xbmc.translatePath('special://home/o2tvgo-prgs-additional.m3u')
    _xmltv_additional_filelist_pattern_ = xbmc.translatePath('special://home/rytecxmltv*.gz')
    _xmltv_additional_ = xbmc.translatePath('special://home/merged_epg.xml')
    _xmltv_additional_gzip_ = xbmc.translatePath('special://home/merged_epg.xml.gz')
    _xmltv_test_output_file_ = xbmc.translatePath('special://home/merged_xml_test_out.xml')
    _next_programme_ = _profile_+'o2tvgo-next_programme.json'
    _restart_ok_ = _profile_+'o2tvgo-restart_ok.txt'
    _save_epg_lock_file_ = _profile_+'o2tvgo-save_epg.lock'
    _epg_shift_ba_winter_ = -1
    _epg_shift_ba_summer_ = -2
    _epg_refresh_rate_ = (12 * 60 * 60) - (30 * 60)
    _epg_fetch_batch_limit_ = 10
    _epgLockTimeout_ = (10 * 60)
    _channel_refresh_rate_ = (4 * 60 * 60) - (30 * 60)

    ###############################################################################
    def _emptyFunction():
        logDbg("function was replaced with a dummy empty one")

    def _getPvrIptvSimpleEpgShift():
        global _addon_pvrIptvSimple_
        shift = None
        if not _addon_pvrIptvSimple_:
            pluginDetails = _jsonRPC_._getAddonDetails("pvr.iptvsimple")
            if pluginDetails:
                #logNtc("Response: "+_toString(pluginDetails))
                enabled = pluginDetails["enabled"]
                if enabled:
                    _addon_pvrIptvSimple_ = xbmcaddon.Addon('pvr.iptvsimple')
                else:
                    response = _jsonRPC_._setAddonEnabled("pvr.iptvsimple", True)
                    if response:
                        xbmc.sleep(1000)
                        _addon_pvrIptvSimple_ = xbmcaddon.Addon('pvr.iptvsimple')
        if _addon_pvrIptvSimple_:
            shift = _addon_pvrIptvSimple_.getSetting("epgTimeShift")
        if not shift:
            msg = "Couldn't get pvr.iptvsimple plugin's epgTimeShift setting; using winter time in BA: "+_epg_shift_ba_winter_
            notificationWarning(msg)
            logErr(msg)
            shift = _epg_shift_ba_winter_
        return float(shift) * 60 * 60

    def _fetchEpg(channel_key, hoursToLoad = 24, hoursToLoadFrom = None, forceFromTimestamp = None):
        global _o2tvgo_
        _o2tvgo_.channel_key = channel_key
        _o2tvgo_.hoursToLoad = hoursToLoad
        if forceFromTimestamp:
            _o2tvgo_.forceFromTimestamp = forceFromTimestamp
        elif hoursToLoadFrom:
            _o2tvgo_.hoursToLoadFrom = hoursToLoadFrom
        epg_list = _o2tvgo_.channel_epg()
        return epg_list

    def _fetchEpgDetail(epg_id):
        global _o2tvgo_
        _o2tvgo_.epg_id = epg_id
        epg_detail = _o2tvgo_.epg_detail()
        return epg_detail

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

#    def compareChannelHosts(ch1, ch2):
#        aCh1 = ch1.split('/')
#        aCh2 = ch2.split('/')
#        return aCh1[3] == aCh2[3]

    def dirListing():
        # This will give options to start saveEPG etc.
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

    def _maybeRestartPVR(refreshRate):
        if os.path.exists(_restart_ok_):
            lastRestartOK = os.path.getmtime(_restart_ok_)
            timestampNow = int(time.time())
            if (timestampNow - lastRestartOK) >= (refreshRate):
                _restartPVR()
        else:
            _restartPVR()

    def _is_saveEpg_running():
        if os.path.exists(_save_epg_lock_file_):
            mtime = os.path.getmtime(_save_epg_lock_file_)
            timestampNow = int(time.time())
            if (timestampNow - mtime) >= (_epgLockTimeout_):
                return False
            else:
                return True
        else:
            return False

    def _touch_saveEpgLockFile():
        epg_lock_file = open(_save_epg_lock_file_, 'w+')
        epg_lock_file.write("Locked for "+_toString(_epgLockTimeout_)+" seconds (from file's modification time)")
        epg_lock_file.close()

    def saveChannels(restartPVR = True, notification = True):
        logNtc("saveChannels() started")
        if os.path.exists(_m3u_):
            lastModTimeM3U = os.path.getmtime(_m3u_)
            timestampNow = int(time.time())
            if os.path.exists(_m3u_additional_):
                lastModTimeM3UAdditional = os.path.getmtime(_m3u_additional_)
                if (timestampNow - lastModTimeM3U) <= (_channel_refresh_rate_) and (lastModTimeM3U - lastModTimeM3UAdditional) >= 0:
                    logNtc("'"+_m3u_+"' file fresh enough and '"+_m3u_additional_+"' file old enough; not refreshing")
                    _maybeRestartPVR(_channel_refresh_rate_)
                    return False
            elif (timestampNow - lastModTimeM3U) < (_channel_refresh_rate_):
                logNtc("'"+_m3u_+"' file fresh enough; not refreshing")
                _maybeRestartPVR(_channel_refresh_rate_)
                return False
        logNtc("Starting refreshing of channels")
        channels = _fetchChannels()
        if not channels:
            logErr("no channels in channelListing")
            return False
        if notification:
            notificationInfo("Refreshing list of channels")
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        numberOfChannels = len(channels_sorted)
        channelIndexesByBaseNames = {}
        channelKeysByIndex = {} # cannot have skipped indexes - used to find channel in EPG
        channelIndexesByKey = {} # cannot have skipped indexes - used to find channel in EPG
        channelKeysByName = {}
        channelNamesByKey = {}
        channelJsonNumbersByIndex = {}
        channelList = {}
        i = 0
        iChannelJsonNumber = 0
        m3u = "#EXTM3U\n"
        for channel in channels_sorted:
            try:
                channel_url = channel.url()
                m3u += '#EXTINF:-1 tvg-id="'+channel.channel_key+'" tvg-name="'+channel.name+'" tvg-logo="'+channel.logo_url+'" group-title="O2TVGO"'+", "+channel.name+"\n"
                m3u += channel_url + "\n"

                aUrl = channel_url.split('/')
                sUrlFileName = aUrl[-1]
                aUrlFileName = sUrlFileName.split('.')
                channelUrlBaseName = aUrlFileName[0]
                channelIndexesByBaseNames[channelUrlBaseName] = i
                channelKeysByIndex[i] = channel.channel_key
                channelIndexesByKey[channel.channel_key] = i
                channelKeysByName[channel.name] = channel.channel_key
                channelNamesByKey[channel.channel_key] = channel.name
                channelJsonNumbersByIndex[i] = iChannelJsonNumber
                channelList[iChannelJsonNumber] = {
                  "name": channel.name,
                  "channel_key": channel.channel_key
                }
                i += 1
                iChannelJsonNumber += 1
            except ChannelIsNotBroadcastingError:
                logDbg("Channel "+channel.name+" ("+str(i+1)+"/"+str(numberOfChannels)+") is not broadcasting; skipping it")
                iChannelJsonNumber += 1 # Otherwise the EPG guides get mixed up!

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
        channelsDict = {"indexesByBaseNames": channelIndexesByBaseNames, "keysByIndex": channelKeysByIndex, "indexesByKey": channelIndexesByKey, "keysByName": channelKeysByName, "namesByKey": channelNamesByKey, "list": channelList, "chJsNumByIndex": channelJsonNumbersByIndex}
        with open(_m3u_json_, 'wb') as f:
            json.dump(channelsDict, codecs.getwriter('utf-8')(f), ensure_ascii=False)
        return notification

    def _getChannelsListDict():
        if os.path.exists(_m3u_):
            try:
                with open(_m3u_json_) as data_file:
                    channelsDict = json.load(data_file)
                if channelsDict and "list" in channelsDict:
                    channelList = channelsDict["list"]
                    if channelList:
                        logNtc("Reading channels from channel list")
                        return channelList
            except:
                logNtc("Exception while reading channels from json")
        else:
            channelsDict = {}
        if not channelsDict:
            channelsDict = {}
        i = 0
        channelList = {}
        logNtc("Fetching channels")
        channels = _fetchChannels()
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        for channel in channels_sorted:
            channelList[i] = {
              "name": channel.name,
              "channel_key": channel.channel_key
            }
            i += 1
        channelsDict["list"] = channelList
        with open(_m3u_json_, 'wb') as f:
            json.dump(channelsDict, codecs.getwriter('utf-8')(f), ensure_ascii=False)
        logNtc("Saved channel list")
        return channelList

    def saveEPG(restartPVR = True, notification = True):
        logNtc("saveEPG() started")

        if _is_saveEpg_running():
            logNtc("Another instance of saveEPG() is still running; not refreshing")
            _maybeRestartPVR(_epg_refresh_rate_)
            return False

        if os.path.exists(_xmltv_):
            lastModTimeXML = os.path.getmtime(_xmltv_)
            timestampNow = int(time.time())
            if os.path.exists(_m3u_additional_):
                lastModTimeM3UAdditional = os.path.getmtime(_m3u_additional_)
                if (timestampNow - lastModTimeXML) <= (_epg_refresh_rate_) and (lastModTimeXML - lastModTimeM3UAdditional) >= 0:
                    logNtc("'"+_xmltv_+"' file fresh enough and '"+_m3u_additional_+"' file old enough; not refreshing")
                    _maybeRestartPVR(_epg_refresh_rate_)
                    return False
            elif (timestampNow - lastModTimeXML) <= (_epg_refresh_rate_):
                logNtc("'"+_xmltv_+"' file fresh enough; not refreshing")
                _maybeRestartPVR(_epg_refresh_rate_)
                return False
        logNtc("Starting refreshing of EPG")
        channelsDict = _getChannelsListDict()
        if not channelsDict:
            logErr("no channels in channelListing")
            return False
        #logNtc(_toString(channelsDict))
        _touch_saveEpgLockFile()
        if notification:
            notificationInfo("Refreshing EPG")
        numberOfChannels = len(channelsDict)
        i = 0
        et_tv = etree.Element("tv")
        while i < numberOfChannels or str(i) in channelsDict:
            key = str(i)
            if not key in channelsDict:
                i += 1
                numberOfChannels += 1
                continue
            channel = channelsDict[key]
            et_channel = etree.SubElement(et_tv, "channel", id=channel["channel_key"])
            etree.SubElement(et_channel, "display-name", lang="sk").text = channel["name"]
            i += 1
        _touch_saveEpgLockFile()

        iFetchedChannel = 0
        i = 0
        while i < numberOfChannels or str(i) in channelsDict:
            key = str(i)
            if not key in channelsDict:
                logDbg("No channel at position "+str(i+1)+"/"+str(numberOfChannels)+"; skipping it")
                i += 1
                continue
            channel = channelsDict[key]
            # read the json file and delete old entries #
            json_epg = None
            useFromTimestamp = False
            useJson = False
            jsonEpgFilePath = _xmltv_json_base_ + str(i) + ".json"
            jsonEpgFile = xbmc.translatePath(jsonEpgFilePath)
            timestampNow = int(time.time())
            if os.path.exists(jsonEpgFile):
                lastModTimeJsonEpgFile = os.path.getmtime(jsonEpgFile)
                if (timestampNow - lastModTimeJsonEpgFile) <= _epg_refresh_rate_:
                    # use this instead of asking for the data #
                    useJson = True
                    #logNtc(channel["name"]+" 1")
                with open(jsonEpgFile) as data_file:
                    json_epg = json.load(data_file)
                for key in json_epg.keys():
                    if (int(timestampNow) - int(json_epg[key]["end"])) > (2*24*3600):
                        del json_epg[key]
            if not json_epg:
                # if there was no file read (or the dictionary is empty by now), just use an empty dictionary #
                json_epg = {}
                useJson = False
                #logNtc(channel["name"]+" 2")
            else:
                # check if the latest programme in the epg starts in the future #
                maxTimestamp = max(json_epg, key=int)
                if (int(maxTimestamp) - int(timestampNow)) < _epg_refresh_rate_:
                    # Data is not fresh enough, we need to load new data - enough to do so from the maxTimestamp #
                    useJson = False
                    useFromTimestamp = True
                    #logNtc(channel["name"]+" 3")
                    #logNtc("Age of latest programme in seconds: "+str(int(maxTimestamp) - int(timestampNow)))
                    #logNtc("Latest programme: "+str(maxTimestamp)+" => "+_toString(json_epg[maxTimestamp]))
            _touch_saveEpgLockFile()

            if useJson:
                logNtc("Using previously downloaded EPG for channel "+channel["name"]+" ("+str(i+1)+"/"+str(numberOfChannels)+")")
                # saving the file with the deleted old entries #
                with open(jsonEpgFile, 'wb') as f:
                    json.dump(json_epg, codecs.getwriter('utf-8')(f), ensure_ascii=False)
            else:
                if iFetchedChannel >= _epg_fetch_batch_limit_:
                    logNtc("Reached limit of fetched channels in one batch ("+str(_epg_fetch_batch_limit_)+"); stopping")
                    return notification
                logNtc("Fetching and parsing EPG for channel "+channel["name"]+" ("+str(i+1)+"/"+str(numberOfChannels)+")")
#                logNtc("DEVEL STOP")
#                return notification
                forceFromTimestamp = None
                if useFromTimestamp:
                    forceFromTimestamp = maxTimestamp
                epg = _fetchEpg(channel["channel_key"], 2 * 24, 2 * 24, forceFromTimestamp)
                if epg:
                    for prg in epg:
                        epg_id = prg['epgId']
                        prg_detail = _fetchEpgDetail(epg_id)
                        if prg_detail['picture']:
                            fanart_image = "http://app.o2tv.cz" + prg_detail['picture']
                        elif prg['picture']:
                            fanart_image = "http://app.o2tv.cz" + prg['picture']
                        else:
                            fanart_image = ""
                        genres = None
                        genre = None
                        if prg_detail['genres']:
                            genres = prg_detail['genres']
                            genre = "/".join(genres).replace('/', ' / ')
                        start = _timestampishToTimestamp(prg['startTimestamp'])
                        json_epg[start] = { "start": start,
                                            "end": _timestampishToTimestamp(prg['endTimestamp']),
                                            "startEpgTime": _timestampishToEpgTime(prg['startTimestamp']),
                                            "endEpgTime": _timestampishToEpgTime(prg['endTimestamp']),
                                            "startTimestamp": prg['startTimestamp'],
                                            "endTimestamp": prg['endTimestamp'],
                                            "epgId": prg["epgId"],
                                            "title": prg['name'],
                                            "fanart_image": fanart_image,
                                            "plotoutline": prg['shortDescription'],
                                            "plot": prg_detail['longDescription'],
                                            "genres": genres,
                                            "genre": genre }
                        _touch_saveEpgLockFile()
                else:
                    logErr("No epg was fetched: "+_toString(epg))
                with open(jsonEpgFile, 'wb') as f:
                    json.dump(json_epg, codecs.getwriter('utf-8')(f), ensure_ascii=False)
                iFetchedChannel += 1
                #logNtc("DEVEL STOP")
                #return notification
            _touch_saveEpgLockFile()

            # building the actual xml file #
            for json_epg_key in sorted(json_epg.iterkeys()):
                prg = json_epg[json_epg_key]
                et_programme = etree.SubElement(et_tv, "programme", channel=channel["channel_key"])
                if "startEpgTime" in prg:
                    et_programme.set("start", prg['startEpgTime'])
                    et_programme.set("stop", prg['endEpgTime'])
                else:
                    et_programme.set("start", _timestampishToEpgTime(prg['startTimestamp']))
                    et_programme.set("stop", _timestampishToEpgTime(prg['endTimestamp']))
                etree.SubElement(et_programme, "title", lang="sk").text = prg['title']
                etree.SubElement(et_programme, "sub-title", lang="sk").text = prg['plotoutline']
                etree.SubElement(et_programme, "desc", lang="sk").text = prg['plot']
                if "fanart_image" in prg and prg["fanart_image"]:
                    et_programme_icon = etree.SubElement(et_programme, "icon")
                    et_programme_icon.set("src", prg["fanart_image"])
                if "genre" in prg and prg["genre"]:
                    etree.SubElement(et_programme, "category", lang="sk").text = prg["genre"]
                _touch_saveEpgLockFile()
            i += 1
#        xmlElTree = etree.ElementTree(et_tv)
        xmlString = etree.tostring(et_tv, encoding='utf8')
        xmltv_file = open(_xmltv_, 'w+')
        if xmltv_file:
            xmltv_file.write(xmlString)
            xmltv_file.close()
            logNtc("'o2tvgo-epg.xml' file saved successfully with O2TV epg")
            if restartPVR:
                _restartPVR()
        _touch_saveEpgLockFile()
        needToRestart = False
        et_tv, needToRestart = _merge_additional_epg_xml(et_tv)
        if needToRestart:
#            xmlElTree = etree.ElementTree(et_tv)
            xmlString = etree.tostring(et_tv, encoding='utf8')
            xmltv_file = open(_xmltv_, 'w+')
            if xmltv_file:
                xmltv_file.write(xmlString)
                xmltv_file.close()
                logNtc("'o2tvgo-epg.xml' file saved successfully with additional epg")
                if restartPVR:
                    _restartPVR()
            _touch_saveEpgLockFile()
        return notification

    def _restartPVR():
        if os.path.exists(_restart_ok_):
            os.remove(_restart_ok_)

        player = xbmc.Player()
        isPlaying = player.isPlayingVideo()
        if isPlaying:
            playingNow = player.getPlayingFile()
            if playingNow.startswith("pvr://"):
                logNtc("Player is currently playing a pvr channel, not restarting")
                return

        #dialog_id = xbmcgui.getCurrentWindowId()
        #if dialog_id >= 10600 and dialog_id < 10800:
            #xbmc.executebuiltin("ActivateWindow(home)")
            #xbmc.sleep(1000)

        pluginDetails = _jsonRPC_._getAddonDetails("pvr.iptvsimple")
        if pluginDetails:
            #logDbg("Plugin details response: "+_toString(pluginDetails))
            enabled = pluginDetails["enabled"]
            if enabled:
                logNtc("Stopping IPTV Simple PVR manager")
                response = _jsonRPC_._setAddonEnabled("pvr.iptvsimple", False)
                if response:
                    logNtc("Starting IPTV Simple PVR manager")
                    response = _jsonRPC_._setAddonEnabled("pvr.iptvsimple", True)
                    if response:
                        logNtc("IPTV Simple PVR manager restart done")
                        notificationInfo("IPTV Simple PVR manager was restarted")
                        restart_ok_file = open(_restart_ok_, 'w+')
                        restart_ok_file.write("ok")
                        restart_ok_file.close()
                        return True
                    else:
                        # Couldn't enable the plugin
                        return False
                else:
                    # Couldn't disable the plugin
                    return False
            else:
                # plugin is disabled
                logNtc("Starting IPTV Simple PVR manager")
                response = _jsonRPC_._setAddonEnabled("pvr.iptvsimple", True)
                if response:
                    logNtc("IPTV Simple PVR manager start done")
                    notificationInfo("IPTV Simple PVR manager was started")
                    restart_ok_file = open(_restart_ok_, 'w+')
                    restart_ok_file.write("ok")
                    restart_ok_file.close()
                    return True
                else:
                    # Couldn't enable the plugin
                    return False
        else:
            # Couldn't get plugin details
            return False
        #logNtc("Stopping PVR manager")
        #xbmc.executebuiltin("StopPVRManager()")
        #logNtc("(Re)Starting PVR manager")
        #xbmc.executebuiltin("StartPVRManager()")
        #logNtc("PVR manager restart done")
        #notificationInfo("IPTV Simple PVR manager was restarted")
        #restart_ok_file = open(_restart_ok_, 'w+')
        #restart_ok_file.write("ok")
        #restart_ok_file.close()

    def _merge_additional_epg_xml(et_tv, test=False):
        logNtc("Starting merge of additional epg xml files to '"+_xmltv_+"'")
        if test:
            et_tv = etree.Element("tv")
            et_programme = etree.SubElement(et_tv, "programme", id="prg1")
            et_programme.set("start", "201701142000")
            et_programme.set("stop", "201701142100")
            etree.SubElement(et_programme, "title", lang="sk").text = "title"
            logDbg(etree.tostring(et_tv, encoding='utf8'))
        #else:
            #return et_tv, False
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
                    return et_tv, False
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
                    return et_tv, False
        if test:
#            xmlElTree = etree.ElementTree(et_tv)
            xmlString = etree.tostring(et_tv, encoding='utf8')
            xmltv_file = open(_xmltv_test_output_file_, 'w+')
            if xmltv_file:
                xmltv_file.write(xmlString)
                xmltv_file.close()
                logNtc("'"+_xmltv_test_output_file_+"' file saved successfully")
        return et_tv, True

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

    def getChannelNameByKey(channelKey):
        with open(_m3u_json_) as data_file:
            channels = json.load(data_file)
        channelName = channels["namesByKey"][channelKey]
        return channelName

    def getChannelKeyByName(channelName):
        with open(_m3u_json_) as data_file:
            channels = json.load(data_file)
        channelKey = channels["keysByName"][channelName]
        return channelKey

    def getChannelKeyByIndex(channelIndex):
        with open(_m3u_json_) as data_file:
            channels = json.load(data_file)
        channelKey = channels["keysByIndex"][str(channelIndex)]
        #logNtc(channelKey)
        return channelKey

    def getChannelJsonNumberByIndex(channelIndex):
        with open(_m3u_json_) as data_file:
            channels = json.load(data_file)
        if "chJsNumByIndex" in channels:
            channelJsonNumber = channels["chJsNumByIndex"][str(channelIndex)]
        else:
            channelJsonNumber = channelIndex
        #logNtc(channelJsonNumber)
        return channelJsonNumber

    def getEpgByChannelIndexAndTimestamp(channelIndex, timestamp):
        channelJsonNumber = getChannelJsonNumberByIndex(channelIndex)
        jsonEpgFilePath = _xmltv_json_base_ + str(channelJsonNumber) + ".json"
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
        objChannel = LiveChannel(_o2tvgo_, channelKey,  None,  None,  None)
        startTimestamp = epg["startTimestamp"]
        if not toTimestamp:
            toTimestamp = epg["endTimestamp"]

        channelUrlTimeshift = objChannel.urlTimeshift(startTimestamp, toTimestamp)
        logNtc("timeshift: " + channelUrlTimeshift)

        return channelUrlTimeshift

    def getChannelStartoverUrl(epg, channelKey):
        global _o2tvgo_
        objChannel = LiveChannel(_o2tvgo_, channelKey,  None,  None,  None)
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
        epgShift = _getPvrIptvSimpleEpgShift()
        timestamp = timeDelta.total_seconds() + epgShift
        return int(timestamp)

    def playChannelFromEpg(startTime, startDate, channelName, channelNumber, playingCurrently=False, startTimestamp=None, channelIndex=None):
        player = xbmc.Player()

        logNtc("playing from epg")
        #logDbg(startDate)
        #logDbg(startTime)
        #logDbg(channelName)

        if startTimestamp and (channelIndex or channelIndex == 0 or channelIndex == '0'):
            timestamp = int(startTimestamp)
            channelIndex = int(channelIndex)
        else:
            if playingCurrently:
                timestamp = int(time.time())
            else:
                timestamp = getTimestampFromDayTime(startDate, startTime)
                #logDbg(timestamp)

            if not timestamp:
                msg = "Couldn't parse timestamp from startDate, startTime"
                notificationError(msg)
                logErr(msg)
                logDbg([startDate, startTime, channelName])
                return

            channelIndex = int(channelNumber) - 1

        channelKey = getChannelKeyByIndex(channelIndex)
        if not channelKey and channelName:
            channelKey = getChannelKeyByName(channelName)
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

        timeShift = _getPvrIptvSimpleEpgShift()
        timestampNow = int(time.time()) * 1000
        if timestampNow < epg["endTimestamp"] + timeShift:
            if timestampNow < epg["startTimestamp"] + timeShift:
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
        if "genre" in epg and epg["genre"]:
            videoinfo['genre'] = epg["genre"]
        if len(videoinfo) > 0:
            li.setInfo('video', videoinfo)

        player.play(channelUrlNew, li)

        logDbg("Looking for next programme")
        timestampNext = int(epg["end"])+5
        epgKeyNext, epgNext, startPosNext = getEpgByChannelIndexAndTimestamp(channelIndex, timestampNext)

        nextProgramme = {}
        if not epgKeyNext or not epgNext or (not startPosNext and startPosNext != 0):
            nextProgramme["epgFound"] = False
            nextProgramme["used"] = False
            logErr("Didn't find next programme in epg")
            logDbg([channelIndex, timestamp, epgKey, epg, startPos])
            logDbg([channelIndex, timestampNext, epgKeyNext, epgNext, startPosNext])
        else:
            nextProgramme = epgNext
            nextProgramme["epgFound"] = True
            nextProgramme["used"] = False
            nextProgramme["channelKey"] = channelKey
            if channelName:
                nextProgramme["channelName"] = channelName
            else:
                nextProgramme["channelName"] = getChannelNameByKey(channelKey)
            nextProgramme["channelIndex"] = channelIndex
            nextProgramme["currentUrl"] = channelUrlNew

        # Save the next channel's epg and programme info #
        with open(_next_programme_, 'wb') as f:
            json.dump(nextProgramme, codecs.getwriter('utf-8')(f), ensure_ascii=False)
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

#        toTimestamp = timestampNow * 1000
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

    def _test():
        logNtc("Executing _test()")
        logNtc("Nothing to do defined in _test()")

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

    pause=None
    saveepg=None
    mergeepg=None
    test=None
    showplayinginfo=None
    playfromepg=None
    starttime=None
    startdate=None
    channelname=None
    channelnumber=None
    playingcurrently=None
    starttimestamp=None
    channelindex=None
    params=get_params()
    assign_params(params)

    #logDbg(params)

    if saveepg:
        notified = saveChannels()
        notified = saveEPG()
    elif playfromepg:
        playChannelFromEpg(starttime, startdate, channelname, channelnumber, playingcurrently, starttimestamp, channelindex)
    elif mergeepg:
        _merge_additional_epg_xml(None, True)
    elif pause:
        # Attempt to implement startover - not successful (yet)
        pausePlayer(channelnumber)
    elif showplayinginfo:
        logPlayingInfo()
    elif test:
        _test()
    else:
        dirListing()
except Exception as ex:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    _logs_ = Logs(_scriptname_)
    xbmcgui.Dialog().notification(_scriptname_, _logs_._toString(exc_value), xbmcgui.NOTIFICATION_ERROR)
    _logs_.logErr(_logs_._toString(exc_value))
#    if not _first_error_:
#        if xbmcgui.Dialog().yesno(_scriptname_, _lang_(30500), _lang_(30501)):
#            _addon_.setSetting("send_errors", "true")
#            _send_errors_ = (_addon_.getSetting('send_errors') == "true")
#        _addon_.setSetting("first_error", "true")
#        _first_error_ = (_addon_.getSetting('first_error') == "true")
#    if _send_errors_:
#        if _sendError(params, exc_type, exc_value, exc_traceback):
#            xbmcgui.Dialog().notification(_scriptname_, _lang_(30502), xbmcgui.NOTIFICATION_INFO)
#        else:
#            xbmcgui.Dialog().notification(_scriptname_, _lang_(30503), xbmcgui.NOTIFICATION_ERROR)
#            traceback.print_exception(exc_type, exc_value, exc_traceback)
